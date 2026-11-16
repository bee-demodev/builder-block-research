// Bar replay, as in TradingView: pick a start bar on a chart, then play the bars after it
// one at a time. The core does the work. The client only sends `set when` plus `check`
// (the cut) and `step +1` (each next bar), and never sends a step before the snapshot of
// the last one has arrived. So every bar is a real check of that moment, the verdict and
// the levels included, and no later bar reaches the screen early. The fastest speed is
// therefore one check per bar.
import { wallClock } from './format';
import type { Candle, ServerState } from './wire';

/** Bars per second, as TradingView words its replay speeds (1x is one bar a second). */
export const SPEEDS = [
  { key: '0.1x', ms: 10_000 },
  { key: '0.3x', ms: 3_000 },
  { key: '0.5x', ms: 2_000 },
  { key: '1x', ms: 1_000 },
  { key: '3x', ms: 333 },
  { key: '5x', ms: 200 },
  { key: '10x', ms: 100 },
] as const;
export type SpeedKey = (typeof SPEEDS)[number]['key'];
export const DEFAULT_SPEED: SpeedKey = '1x';

export const speedMs = (key: SpeedKey): number => SPEEDS.find((s) => s.key === key)?.ms ?? 1000;
export const isSpeed = (v: unknown): v is SpeedKey => SPEEDS.some((s) => s.key === v);

/**
 * off: no replay. select: the next click on a chart picks the start bar. paused / playing:
 * a start is picked (or the trader stepped back) and the bars after it can be played.
 */
export type ReplayMode = 'off' | 'select' | 'paused' | 'playing';

export interface Replay {
  mode: ReplayMode;
  speed: SpeedKey;
  /** Snapshot seq when the last cut or step went out; the next step waits for a later snapshot. */
  awaiting: number | null;
  /** Where Esc in select mode goes back to. */
  before: 'off' | 'paused';
}

export const initialReplay = (speed: SpeedKey = DEFAULT_SPEED): Replay => ({ mode: 'off', speed, awaiting: null, before: 'off' });

export type ReplayAction =
  /** The Replay button: choose a start bar. */
  | { type: 'open' }
  /** Select bar again while replaying. */
  | { type: 'select' }
  /** Esc or Select bar pressed again: back to where select mode began. */
  | { type: 'cancelSelect' }
  /** A start bar was clicked and sent; `seq` is the snapshot seq at that moment. */
  | { type: 'cut'; seq: number }
  | { type: 'play' }
  | { type: 'pause' }
  | { type: 'toggle' }
  | { type: 'speed'; speed: SpeedKey }
  /** A step went out while playing. */
  | { type: 'stepped'; seq: number }
  /** A snapshot arrived. */
  | { type: 'snapshot'; seq: number }
  /** An error came back, or there is nothing left to play: pause. */
  | { type: 'stop' }
  /** Back to real time, or the selection changed: replay ends. */
  | { type: 'close' };

export function reduceReplay(r: Replay, a: ReplayAction): Replay {
  switch (a.type) {
    case 'open':
      return r.mode === 'off' ? { ...r, mode: 'select', before: 'off', awaiting: null } : r;
    case 'select':
      if (r.mode === 'off' || r.mode === 'select') return r;
      return { ...r, mode: 'select', before: 'paused', awaiting: null };
    case 'cancelSelect':
      return r.mode === 'select' ? { ...r, mode: r.before } : r;
    case 'cut':
      return { ...r, mode: 'paused', awaiting: a.seq };
    case 'play':
      return r.mode === 'paused' ? { ...r, mode: 'playing' } : r;
    case 'pause':
      return r.mode === 'playing' ? { ...r, mode: 'paused', awaiting: null } : r;
    case 'stop':
      // also drops a cut's wait: a refused cut sends no snapshot
      if (r.mode !== 'playing' && r.awaiting === null) return r;
      return { ...r, mode: r.mode === 'playing' ? 'paused' : r.mode, awaiting: null };
    case 'toggle':
      if (r.mode === 'playing') return { ...r, mode: 'paused', awaiting: null };
      return r.mode === 'paused' ? { ...r, mode: 'playing' } : r;
    case 'speed':
      return { ...r, speed: a.speed };
    case 'stepped':
      return r.mode === 'playing' ? { ...r, awaiting: a.seq } : r;
    case 'snapshot':
      return r.awaiting !== null && a.seq > r.awaiting ? { ...r, awaiting: null } : r;
    case 'close':
      return { ...initialReplay(r.speed) };
  }
}

/** Playing, and the last step's snapshot is in: the next step may go out after the speed's wait. */
export const readyForNext = (r: Replay): boolean => r.mode === 'playing' && r.awaiting === null;

/**
 * Live and on the last closed bar: there is nothing later to step to. Saved history has no
 * "now" (the core keeps `follow` set there); its end is the core's "end of the data" reply.
 */
export const atLatest = (s: ServerState | null): boolean => s !== null && s.live && s.follow;

/**
 * The `when` a click on `candle` cuts at: its close, as New York wall time
 * ("YYYY-MM-DD HH:MM"), so the clicked candle is the last one shown, as in TradingView.
 * A candle's `t` is its New York wall-clock open expressed as if UTC.
 */
export function cutWhen(candle: Pick<Candle, 't'>, minutes: number): string {
  const iso = new Date((candle.t + minutes * 60) * 1000).toISOString();
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`;
}

/** "Fri 13 Mar 2026 09:30" for the replay bar, from the core's `when`; "" when unreadable. */
export function replayClock(when: string): string {
  const c = wallClock(when);
  return c ? `${c.date} ${c.time}` : '';
}
