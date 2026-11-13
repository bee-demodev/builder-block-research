// SAMPLE DATA GENERATOR for demo mode. Nothing here is market data.
// Candles follow a seeded random walk steered through hand-picked waypoints, so
// fixtures can place levels and sweeps on known candles without pasting arrays.
import type { Candle } from '../wire';

/** mulberry32: small, fast, deterministic. */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const TICK = 0.25;
export const roundTick = (p: number) => Math.round(p / TICK) * TICK;

const pad = (n: number) => String(n).padStart(2, '0');

/** 2026 US daylight time runs 8 Mar to 1 Nov. Good enough for sample timestamps. */
function nyOffset(t: number): string {
  const d = new Date(t * 1000);
  const md = (d.getUTCMonth() + 1) * 100 + d.getUTCDate();
  return md >= 308 && md < 1101 ? '-04:00' : '-05:00';
}

/** ISO-8601 with New York offset, from a wall-clock-as-UTC epoch. */
export function isoNY(t: number): string {
  const d = new Date(t * 1000);
  return (
    `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}` +
    `T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:00${nyOffset(t)}`
  );
}

/** Wall-clock New York time as epoch seconds "as if UTC". */
export const wall = (y: number, mo: number, d: number, h = 0, mi = 0) => Date.UTC(y, mo - 1, d, h, mi) / 1000;

/** Open times for `count` bars of `minutes`, ending at `lastOpen`, skipping weekends (and the 17:00 hour for intraday). */
export function barTimes(lastOpen: number, minutes: number, count: number): number[] {
  const out: number[] = [];
  let t = lastOpen;
  while (out.length < count) {
    const d = new Date(t * 1000);
    const dow = d.getUTCDay();
    const skip = dow === 0 || dow === 6 || (minutes < 1440 && d.getUTCHours() === 17);
    if (!skip) out.push(t);
    t -= minutes * 60;
  }
  return out.reverse();
}

export interface Waypoint {
  /** Bar index the walk should reach. */
  at: number;
  price: number;
}

export interface WalkSpec {
  seed: number;
  times: number[];
  waypoints: Waypoint[]; // sorted by `at`, first at 0
  /** Typical bar range, in points. */
  noise: number;
  /** Last candle is still forming. */
  forming?: boolean;
  label?: (t: number) => string;
}

export function walk(spec: WalkSpec): Candle[] {
  const r = rng(spec.seed);
  const n = spec.times.length;
  const target = (i: number): number => {
    const wps = spec.waypoints;
    for (let k = 1; k < wps.length; k++) {
      const a = wps[k - 1]!;
      const b = wps[k]!;
      if (i <= b.at) return a.price + ((b.price - a.price) * (i - a.at)) / Math.max(1, b.at - a.at);
    }
    return wps[wps.length - 1]!.price;
  };
  const candles: Candle[] = [];
  let prevClose = target(0);
  for (let i = 0; i < n; i++) {
    const t = spec.times[i]!;
    const open = roundTick(prevClose + (r() - 0.5) * spec.noise * 0.15);
    const close = roundTick(target(i) + (r() - 0.5) * spec.noise * 0.9);
    const high = roundTick(Math.max(open, close) + r() * spec.noise * 0.45);
    const low = roundTick(Math.min(open, close) - r() * spec.noise * 0.45);
    candles.push({
      time: isoNY(t),
      t,
      open,
      high,
      low,
      close,
      forming: Boolean(spec.forming) && i === n - 1,
      label: spec.label ? spec.label(t) : isoNY(t).slice(0, 16).replace('T', ' '),
    });
    prevClose = close;
  }
  return candles;
}

/** Force a candle to touch exact prices, keeping it a valid OHLC bar. */
export function pin(candles: Candle[], index: number, patch: Partial<Pick<Candle, 'open' | 'high' | 'low' | 'close'>>): void {
  const c = candles[index];
  if (!c) throw new Error(`pin: no candle ${index}`);
  const next = { ...c, ...patch };
  next.high = Math.max(next.high, next.open, next.close);
  next.low = Math.min(next.low, next.open, next.close);
  candles[index] = next;
  const after = candles[index + 1];
  if (after && patch.close !== undefined) {
    candles[index + 1] = { ...after, open: patch.close, high: Math.max(after.high, patch.close), low: Math.min(after.low, patch.close) };
  }
}
