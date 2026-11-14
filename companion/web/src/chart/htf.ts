// The higher-timeframe column (TTFM style): the last few candles of the timeframe
// above, drawn to the right of a pane's own candles on the same price scale, each
// with hairlines at its high and low across the lower-timeframe bars it covers.
// Pure logic here; MarksPrimitive draws it.
import { formatPrice } from '../format';
import type { Candle, Mark } from '../wire';

/** One higher-timeframe candle in the column. */
export interface HtfBar {
  candle: Candle;
  /** Position in the column, 0 = leftmost (oldest). */
  slot: number;
  /** "C1", "C2", "C3" when the core numbered this candle, else "". */
  label: string;
  /** First and last lower-timeframe candle index it covers; null when none of them are loaded. */
  from: number | null;
  to: number | null;
}

export interface HtfColumn {
  timeframe: string;
  bars: HtfBar[];
}

/** Candles the column shows when none is numbered further back. */
export const COLUMN_COUNT = 4;
/** Never more than this many, even to reach a numbered candle. */
export const COLUMN_MAX = 6;
/** Lower-timeframe bars between the last candle and the column. */
export const COLUMN_GAP = 3;
/** Lower-timeframe bars per column candle. */
export const COLUMN_SLOT = 2.5;

/** Index of the first candle opening at or after `t` (candles sorted by `t`). */
function firstAtOrAfter(candles: readonly Candle[], t: number): number {
  let lo = 0;
  let hi = candles.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (candles[mid]!.t < t) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/**
 * Lower-timeframe candles inside one higher-timeframe candle: those opening at or after
 * its open and before the next one's (`end`), as indexes into `ltf`. Using the next
 * candle's open rather than open + length keeps weekends and session breaks inside the
 * candle they belong to.
 */
export function ltfSpan(ltf: readonly Candle[], start: number, end: number): { from: number; to: number } | null {
  const from = firstAtOrAfter(ltf, start);
  const to = firstAtOrAfter(ltf, end) - 1;
  return from <= to ? { from, to } : null;
}

/**
 * The core's numbered candles ("Bias Candle 1" .. "Bias Candle 3" markers on the
 * higher-timeframe chart) by candle index, with their short labels.
 */
export function numberedCandles(marks: readonly Mark[]): Map<number, string> {
  const out = new Map<number, string>();
  for (const m of marks) {
    if (m.kind !== 'marker' || m.start === null) continue;
    const n = /^Bias Candle (\d)$/.exec(m.title.trim());
    if (n) out.set(m.start, m.label || `C${n[1]}`);
  }
  return out;
}

/**
 * The column for a pane: the last `count` higher-timeframe candles (more, up to
 * COLUMN_MAX, so every numbered candle is in it), each with the lower-timeframe bars it
 * covers. The last candle covers everything from its open on.
 */
export function buildColumn(
  ltf: readonly Candle[],
  htf: readonly Candle[],
  timeframe: string,
  labels: ReadonlyMap<number, string> = new Map(),
  count = COLUMN_COUNT,
): HtfColumn {
  if (htf.length === 0 || ltf.length === 0) return { timeframe, bars: [] };
  let first = Math.max(0, htf.length - count);
  for (const i of labels.keys()) if (i >= 0 && i < htf.length) first = Math.min(first, i);
  first = Math.max(first, htf.length - COLUMN_MAX);
  const bars: HtfBar[] = [];
  for (let i = first; i < htf.length; i++) {
    const candle = htf[i]!;
    const next = htf[i + 1];
    const span = ltfSpan(ltf, candle.t, next ? next.t : Infinity);
    bars.push({ candle, slot: i - first, label: labels.get(i) ?? '', from: span?.from ?? null, to: span?.to ?? null });
  }
  return { timeframe, bars };
}

/** Logical index (in lower-timeframe bars) of the centre of column slot `slot`. */
export function slotLogical(lastIndex: number, slot: number, gap = COLUMN_GAP): number {
  return lastIndex + gap + COLUMN_SLOT * (slot + 0.5);
}

/** Bars of empty space the column needs right of the last candle. */
export function columnBars(column: HtfColumn | null, gap = COLUMN_GAP): number {
  if (!column || column.bars.length === 0) return 0;
  return gap + COLUMN_SLOT * column.bars.length + 1;
}

// ---------- the cap: a tall higher-timeframe candle must not squash the pane ----------

export interface Band {
  lo: number;
  hi: number;
}

/**
 * Prices the column may pull the scale out to: the lower-timeframe candles' range,
 * widened by `reach` of itself on each side (the same reach off-scale levels get). A daily wick past that is cut at the pane
 * edge instead of flattening the 1h candles.
 */
export function capBand(ltf: readonly Candle[], reach = 0.15): Band | null {
  if (ltf.length === 0) return null;
  let lo = Infinity;
  let hi = -Infinity;
  for (const c of ltf) {
    if (c.low < lo) lo = c.low;
    if (c.high > hi) hi = c.high;
  }
  const pad = Math.max(hi - lo, 1e-9) * reach;
  return { lo: lo - pad, hi: hi + pad };
}

/** The column's high and low, each held inside the band. */
export function cappedRange(column: HtfColumn, band: Band | null): Band | null {
  if (column.bars.length === 0) return null;
  let lo = Infinity;
  let hi = -Infinity;
  for (const { candle } of column.bars) {
    if (candle.low < lo) lo = candle.low;
    if (candle.high > hi) hi = candle.high;
  }
  if (!band) return { lo, hi };
  return { lo: Math.max(lo, band.lo), hi: Math.min(hi, band.hi) };
}

/** "1D high 25,612.50 and low 24,603.75 are past the scale", or "" when the column fits. */
export function columnNote(column: HtfColumn, band: Band | null, decimals = 2): string {
  if (!band || column.bars.length === 0) return '';
  let lo = Infinity;
  let hi = -Infinity;
  for (const { candle } of column.bars) {
    if (candle.low < lo) lo = candle.low;
    if (candle.high > hi) hi = candle.high;
  }
  const parts: string[] = [];
  if (hi > band.hi) parts.push(`high ${formatPrice(hi, decimals)}`);
  if (lo < band.lo) parts.push(`low ${formatPrice(lo, decimals)}`);
  if (!parts.length) return '';
  return `${column.timeframe} ${parts.join(' and ')} ${parts.length > 1 ? 'are' : 'is'} past the scale`;
}

/** Hover title of a column candle: "1D C2, Nov 18 (forming). H 25,361.25  L 24,743.50" */
export function barTitle(bar: HtfBar, timeframe: string, decimals = 2): string {
  const c = bar.candle;
  const name = [timeframe, bar.label].filter(Boolean).join(' ');
  const when = c.label ? `, ${c.label}` : '';
  const forming = c.forming ? ' (forming)' : '';
  return `${name}${when}${forming}. H ${formatPrice(c.high, decimals)}  L ${formatPrice(c.low, decimals)}`;
}
