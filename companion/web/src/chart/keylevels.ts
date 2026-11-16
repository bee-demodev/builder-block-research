// Higher-timeframe key levels, as a key-levels indicator draws them: the week's open and the
// previous week's high and low, the day's open and the previous day's high, low and
// equilibrium, the previous higher-timeframe candle's range on an intraday pane, and the
// Asia and London session ranges. Built here from the candles the core already sends; the
// core's own plain reference levels and session levels join them, so a price is drawn once.
// Pure logic; MarksPrimitive draws it.
import { formatPrice } from '../format';
import { isSessionRole } from '../display';
import { markTone } from '../tones';
import type { Candle, Direction, Mark } from '../wire';
import { firstAtOrAfter } from './htf';
import { overlaps, type Box } from './marks';

/** From the most senior down: the core's own levels, then week, day, the candle above, sessions. */
export type KeyFamily = 'core' | 'week' | 'day' | 'htf' | 'session';
const RANK: Record<KeyFamily, number> = { core: 0, week: 1, day: 2, htf: 3, session: 4 };

export interface KeyLevel {
  price: number;
  /** What the chart writes: "PDH", "Asia H". */
  short: string;
  /** What the hover says: "Previous day high". */
  name: string;
  family: KeyFamily;
  /** Pane candle index the line starts at; null when that is before the loaded candles. */
  start: number | null;
  /** Sent by the core (a session or reference mark) rather than computed here. */
  fromCore?: boolean;
  /** A level computed here that absorbed the core's reference copy of itself: it thins as a core level. */
  coreSent?: boolean;
}

/** Levels at one price (to the tick), drawn as one line with one label. */
export interface KeyGroup {
  price: number;
  /** Most senior first, one per wording. */
  levels: KeyLevel[];
  start: number | null;
}

/** A chart the levels are read from. */
export interface KeySource {
  timeframe: string;
  minutes: number;
  candles: readonly Candle[];
}

const HOUR = 3600;
const DAY = 86400;

/**
 * Trading day of a New York wall-clock time (as epoch seconds), as a day number: the
 * futures day opens at 18:00 the evening before, so 18:00 Sunday belongs to Monday.
 */
export function tradingDay(t: number): number {
  return Math.floor((t + 6 * HOUR) / DAY);
}

/** The Monday (day number) of the trading week `t` is in. */
export function tradingWeek(t: number): number {
  const d = tradingDay(t);
  const weekday = (d + 4) % 7; // 0 = Sunday; day 0 (1970-01-01) was a Thursday
  return d - ((weekday + 6) % 7);
}

/** Whether a daily candle is its week's Monday session (opened Sunday 18:00). */
function weekStart(t: number): boolean {
  return tradingDay(t) === tradingWeek(t);
}

/** Pane candle index a line starting at time `t` begins on; null when `t` is before the loaded candles. */
function startIndex(pane: readonly Candle[], t: number): number | null {
  if (pane.length === 0 || t < pane[0]!.t) return null;
  return Math.min(pane.length - 1, firstAtOrAfter(pane, t));
}

function range(candles: readonly Candle[]): { high: number; low: number } {
  let high = -Infinity;
  let low = Infinity;
  for (const c of candles) {
    if (c.high > high) high = c.high;
    if (c.low < low) low = c.low;
  }
  return { high, low };
}

/** Index of the last candle opening at or before `t`, or -1. */
function lastAtOrBefore(candles: readonly Candle[], t: number): number {
  return firstAtOrAfter(candles, t + 1) - 1;
}

/** Day open, PDH, PDL and the previous day's equilibrium, from daily candles. */
function dayLevels(pane: KeySource, daily: KeySource): KeyLevel[] {
  const last = pane.candles[pane.candles.length - 1]!;
  const i = lastAtOrBefore(daily.candles, last.t);
  if (i < 0) return [];
  const today = daily.candles[i]!;
  // The day the pane is in, or nothing: a daily chart missing today would shift every level a day.
  if (tradingDay(today.t) !== tradingDay(last.t)) return [];
  const start = startIndex(pane.candles, today.t);
  const out: KeyLevel[] = [{ price: today.open, short: 'Day open', name: 'Day open (18:00)', family: 'day', start }];
  const prev = daily.candles[i - 1];
  if (prev) {
    out.push(
      { price: prev.high, short: 'PDH', name: 'Previous day high', family: 'day', start },
      { price: prev.low, short: 'PDL', name: 'Previous day low', family: 'day', start },
      { price: (prev.high + prev.low) / 2, short: 'PD EQ', name: 'Previous day equilibrium', family: 'day', start },
    );
  }
  return out;
}

/** Week open, PWH and PWL: from weekly candles when there are some, else from daily candles grouped by trading week. */
function weekLevels(pane: KeySource, daily: KeySource | null, weekly: KeySource | null): KeyLevel[] {
  const last = pane.candles[pane.candles.length - 1]!;
  let open: { price: number; t: number } | null = null;
  let prev: { high: number; low: number } | null = null;
  if (weekly) {
    const i = lastAtOrBefore(weekly.candles, last.t);
    if (i < 0) return [];
    const w = weekly.candles[i]!;
    if (tradingWeek(w.t) !== tradingWeek(last.t)) return [];
    open = { price: w.open, t: w.t };
    const p = weekly.candles[i - 1];
    prev = p ? { high: p.high, low: p.low } : null;
  } else if (daily) {
    const i = lastAtOrBefore(daily.candles, last.t);
    if (i < 0) return [];
    const week = tradingWeek(daily.candles[i]!.t);
    // The pane's own week, or nothing: daily candles that stop last Friday would pass off last week as this one.
    if (week !== tradingWeek(last.t)) return [];
    let first = i;
    while (first > 0 && tradingWeek(daily.candles[first - 1]!.t) === week) first--;
    // The week's open only when its first day is known: the previous week's last candle is loaded too.
    // Loaded history that starts mid-week would otherwise call a Wednesday open the week's.
    // (A first loaded day that is the week's Monday is its first day too.)
    if (first === 0 && !weekStart(daily.candles[0]!.t)) return [];
    const w = daily.candles[first]!;
    open = { price: w.open, t: w.t };
    // The previous week, only when its first day is not the first daily candle loaded (it may be cut).
    const before = first - 1;
    if (before >= 0) {
      const pw = tradingWeek(daily.candles[before]!.t);
      let pf = before;
      while (pf > 0 && tradingWeek(daily.candles[pf - 1]!.t) === pw) pf--;
      if (pf > 0 || weekStart(daily.candles[pf]!.t)) prev = range(daily.candles.slice(pf, before + 1));
    }
  }
  if (!open) return [];
  const start = startIndex(pane.candles, open.t);
  const out: KeyLevel[] = [{ price: open.price, short: 'Wk open', name: 'Week open', family: 'week', start }];
  if (prev) {
    out.push(
      { price: prev.high, short: 'PWH', name: 'Previous week high', family: 'week', start },
      { price: prev.low, short: 'PWL', name: 'Previous week low', family: 'week', start },
    );
  }
  return out;
}

/** The previous candle of the timeframe above an intraday pane (not daily: the day levels are that). */
function htfLevels(pane: KeySource, above: KeySource): KeyLevel[] {
  const last = pane.candles[pane.candles.length - 1]!;
  const i = lastAtOrBefore(above.candles, last.t);
  if (i < 0) return [];
  const now = above.candles[i]!;
  // The candle the pane's last bar is in, or nothing: between snapshots a tick can cross into the
  // next hour before the chart above has it, and "previous" would then name the wrong candle.
  if (last.t >= now.t + above.minutes * 60) return [];
  const prev = above.candles[i - 1];
  const tf = above.timeframe;
  const start = startIndex(pane.candles, now.t);
  const out: KeyLevel[] = [{ price: now.open, short: `${tf} open`, name: `${tf} candle open`, family: 'htf', start }];
  if (prev) {
    out.push(
      { price: prev.high, short: `Prev ${tf} H`, name: `Previous ${tf} candle high`, family: 'htf', start },
      { price: prev.low, short: `Prev ${tf} L`, name: `Previous ${tf} candle low`, family: 'htf', start },
      { price: (prev.high + prev.low) / 2, short: `Prev ${tf} EQ`, name: `Previous ${tf} candle equilibrium`, family: 'htf', start },
    );
  }
  return out;
}

/** The trading day's sessions, New York clock hours from midnight (Asia opens 18:00 the evening before). */
export const SESSIONS = [
  { name: 'Asia', begin: -6, end: 0 },
  { name: 'London', begin: 2, end: 5 },
] as const;

/**
 * Whether a source's candles hold the whole window [begin, end): one opens at or before `begin`,
 * and the window's last candle has closed (a later one has opened, or the last one is closed and
 * ends at or after `end`). A source that stops early would give a range cut short.
 */
export function covers(src: KeySource, begin: number, end: number): boolean {
  const cs = src.candles;
  if (cs.length === 0 || cs[0]!.t > begin) return false;
  const last = cs[cs.length - 1]!;
  if (last.t >= end) return true;
  return !last.forming && last.t + src.minutes * 60 >= end;
}

/**
 * The core's session levels, only while they are of the pane's trading day: the marks come with a
 * snapshot, and ticks after the 18:00 roll keep them until the next one, so `marksDay` (the trading
 * day of the pane's last candle when the marks came) must still be the day of `lastT`.
 */
export function currentSessionMarks<M extends { role: string }>(marks: readonly M[], marksDay: number | null, lastT: number | null): M[] {
  const fresh = marksDay !== null && lastT !== null && tradingDay(lastT) === marksDay;
  return fresh ? [...marks] : marks.filter((m) => !isSessionRole(m.role));
}

/**
 * Asia and London high and low of the pane's trading day, once each window has closed (a
 * pane candle has opened at or after its end), from the first intraday source whose
 * candles cover the whole window. The same windows as the core's session levels.
 */
function sessionLevels(pane: KeySource, sources: readonly (KeySource | null)[]): KeyLevel[] {
  const last = pane.candles[pane.candles.length - 1]!;
  const midnight = tradingDay(last.t) * DAY;
  const out: KeyLevel[] = [];
  for (const s of SESSIONS) {
    const begin = midnight + s.begin * HOUR;
    const end = midnight + s.end * HOUR;
    if (last.t < end) continue;
    const src = sources.find((k) => k && k.minutes <= 60 && covers(k, begin, end));
    if (!src) continue;
    const inside = src.candles.slice(firstAtOrAfter(src.candles, begin), firstAtOrAfter(src.candles, end));
    if (inside.length === 0) continue;
    const { high, low } = range(inside);
    const start = startIndex(pane.candles, begin);
    out.push(
      { price: high, short: `${s.name} H`, name: `${s.name} session high`, family: 'session', start },
      { price: low, short: `${s.name} L`, name: `${s.name} session low`, family: 'session', start },
    );
  }
  return out;
}

/**
 * Daily candles built from an intraday chart of a stack that has no daily one (4h /
 * 15m / 1m, 1W / 4h / 15m), grouped by trading day. The first day loaded may be cut, so it is
 * left out; null when fewer than two whole days remain.
 */
export function derivedDaily(charts: readonly KeySource[]): KeySource | null {
  // The coarsest first: 4h bars roll at 18:00 like the day, so they give the same open, high and
  // low as finer bars, over many more days (the week levels need the week before).
  const intraday = charts.filter((c) => c.minutes < 1440 && c.candles.length > 0).sort((a, b) => b.minutes - a.minutes);
  for (const src of intraday) {
    const days: Candle[] = [];
    let day = NaN;
    for (const c of src.candles) {
      const d = tradingDay(c.t);
      const cur = days[days.length - 1];
      if (d !== day || !cur) {
        day = d;
        days.push({ ...c, label: '' });
        continue;
      }
      cur.high = Math.max(cur.high, c.high);
      cur.low = Math.min(cur.low, c.low);
      cur.close = c.close;
      cur.forming = c.forming;
    }
    const whole = days.slice(1);
    if (whole.length >= 2) return { timeframe: '1D', minutes: 1440, candles: whole };
  }
  return null;
}

/**
 * Every key level for a pane, from the charts of its stack: `above` is the timeframe drawn in
 * its column, `charts` all of the stack's charts (daily or weekly ones give the day and week
 * levels). Each family is left out on a pane at or above its own timeframe.
 */
export function keyLevels(pane: KeySource, above: KeySource | null, charts: readonly KeySource[]): KeyLevel[] {
  if (pane.candles.length === 0) return [];
  const daily = charts.find((c) => c.minutes === 1440 && c.candles.length > 0) ?? derivedDaily(charts);
  const weekly = charts.find((c) => c.minutes === 10080 && c.candles.length > 0) ?? null;
  const out: KeyLevel[] = [];
  if (pane.minutes < 10080 && (daily || weekly)) out.push(...weekLevels(pane, daily, weekly));
  if (pane.minutes < 1440 && daily) out.push(...dayLevels(pane, daily));
  if (above && above.minutes < 1440 && above.minutes > pane.minutes && above.candles.length) out.push(...htfLevels(pane, above));
  if (pane.minutes <= 60) out.push(...sessionLevels(pane, [pane, above]));
  return out;
}

/**
 * Whether the key levels layer draws this core mark instead of the marks pass: a session level,
 * or a plain reference level (no meaning colour). Such a level never widens the price scale and
 * is never listed as off the scale; past the prices shown it gets an edge chip.
 */
export function takenByKeys(mark: Mark, direction: Direction): boolean {
  // a level that ends part way (`end`) stays with the marks pass, which draws it to its end
  return (
    mark.kind === 'level' &&
    mark.price !== null &&
    mark.end === null &&
    (isSessionRole(mark.role) || markTone(mark.role, direction) === 'muted')
  );
}

/** A core mark the key layer takes over: a session level (PDH and session ranges) or a plain reference level. */
export function fromMark(mark: Mark): KeyLevel | null {
  if (mark.kind !== 'level' || mark.price === null) return null;
  const session = isSessionRole(mark.role);
  const family: KeyFamily = !session ? 'core' : /previous day/i.test(mark.title) ? 'day' : 'session';
  return { price: mark.price, short: mark.label || mark.title, name: mark.title || mark.label, family, start: mark.start, fromCore: true };
}

/**
 * What a level is, from its wording, when it is one of the previous-candle or open levels that both
 * the core and this module name: "prev:4h:high" for "Prev 4h high", "Prev 4h H" and the like,
 * "prev:1d:eq" for "1D EQ" and "PD EQ", "prev:1w:low" for "PWL". A previous-bias-candle level whose
 * wording gives no timeframe ("EQ") gets "?" for it. Undefined for anything else.
 */
export function levelKey(short: string, name = ''): string | undefined {
  const s = short.trim();
  const kind = (w: string) => ({ h: 'high', high: 'high', l: 'low', low: 'low', eq: 'eq' })[w.toLowerCase()];
  let m: RegExpExecArray | null;
  if (/^PDH$/i.test(s) || /^previous day high$/i.test(name)) return 'prev:1d:high';
  if (/^PDL$/i.test(s) || /^previous day low$/i.test(name)) return 'prev:1d:low';
  if (/^PD EQ$/i.test(s)) return 'prev:1d:eq';
  if (/^PWH$/i.test(s)) return 'prev:1w:high';
  if (/^PWL$/i.test(s)) return 'prev:1w:low';
  if ((m = /^Prev (\S+) (high|low|H|L|EQ)$/i.exec(s))) return `prev:${m[1]!.toLowerCase()}:${kind(m[2]!)}`;
  if ((m = /^(\S+) EQ$/i.exec(s))) return `prev:${m[1]!.toLowerCase()}:eq`;
  if ((m = /^previous bias candle (high|low|equilibrium)$/i.exec(name.split('; ')[0] ?? ''))) {
    return `prev:?:${m[1]!.toLowerCase() === 'equilibrium' ? 'eq' : m[1]!.toLowerCase()}`;
  }
  return undefined;
}

/** Whether two levels at one price are the same level worded differently (an unknown timeframe matches any). */
function sameLevel(a: KeyLevel, b: KeyLevel): boolean {
  const ka = levelKey(a.short, a.name);
  const kb = levelKey(b.short, b.name);
  if (!ka || !kb) return false;
  const [, ta, wa] = ka.split(':');
  const [, tb, wb] = kb.split(':');
  return wa === wb && (ta === tb || ta === '?' || tb === '?');
}

/**
 * Levels sharing a price (to `decimals`) as one group, most senior first, each wording once;
 * the line starts where its earliest level does. Groups come back sorted by price, high first.
 */
export function groupKeyLevels(levels: readonly KeyLevel[], decimals: number): KeyGroup[] {
  const groups = new Map<string, KeyGroup>();
  // the core's levels first, whatever order they came in: a computed level then always finds the
  // core's copy of itself already there to absorb (its wording, family and start win; coreSent set)
  const ordered = [...levels.filter((l) => l.fromCore), ...levels.filter((l) => !l.fromCore)];
  for (const l of ordered) {
    if (!Number.isFinite(l.price)) continue;
    const key = l.price.toFixed(decimals);
    const g = groups.get(key);
    if (!g) {
      groups.set(key, { price: l.price, levels: [{ ...l }], start: l.start });
      continue;
    }
    // One wording per label; the hover keeps every name (the core's "Respect level" and the day's EQ).
    // The same level worded two ways ("Prev 4h high" from the core, "Prev 4h H" here) is one level.
    const same = g.levels.find((m) => m.short === l.short || sameLevel(m, l));
    if (!same) g.levels.push({ ...l });
    else {
      // the computed wording, so a label reads like its siblings ("Prev 4h H" beside "Prev 4h L")
      if (same.family === 'core' && l.family !== 'core') same.short = l.short;
      // the more descriptive name of a computed level first ("Previous day equilibrium; Respect level ...")
      if (!same.name.split('; ').includes(l.name)) same.name = same.family === 'core' && l.family !== 'core' ? `${l.name}; ${same.name}` : `${same.name}; ${l.name}`;
      // where the line starts: this layer's start when it absorbs the core's copy of the same level (so
      // PDH starts at today's open on every pane, sent by the core or not); else the earlier of the two
      if (same.fromCore && !l.fromCore) {
        same.start = l.start;
        same.fromCore = false;
        // a reference level the core drew (the setup's respect level): a computed level never thins it
        // out (the core's session levels are information, and rank as their family)
        same.coreSent = same.family === 'core';
        // and its family, so it is dashed, zoomed and ranked like its siblings (a column candle's dots)
        if (sameLevel(same, l) || same.short === l.short) same.family = l.family;
      } else if (!(l.fromCore && !same.fromCore) && same.start !== null && (l.start === null || l.start < same.start)) same.start = l.start;
    }
  }
  const out = [...groups.values()];
  // the line starts with its earliest level
  for (const g of out) g.start = g.levels.some((l) => l.start === null) ? null : Math.min(...g.levels.map((l) => l.start!));
  for (const g of out) g.levels.sort((a, b) => RANK[a.family] - RANK[b.family]);
  return out.sort((a, b) => b.price - a.price);
}

/**
 * Whether a family is worth drawing when the pane shows `spanMinutes` of time: zoomed out,
 * the finer levels go first (a previous-hour level means nothing across a week of bars).
 */
export function familyShown(family: KeyFamily, spanMinutes: number, htfMinutes: number): boolean {
  switch (family) {
    case 'core':
    case 'week':
      return true;
    case 'day':
      return spanMinutes <= 30 * 1440;
    case 'session':
      return spanMinutes <= 1440;
    case 'htf':
      return spanMinutes <= 16 * Math.max(htfMinutes, 1);
  }
}

/** The group's levels worth drawing at this zoom; empty when none. */
export function shownLevels(g: KeyGroup, spanMinutes: number, htfMinutes: number): KeyLevel[] {
  return g.levels.filter((l) => familyShown(l.family, spanMinutes, htfMinutes));
}

/** The label's wordings, fullest first: every name, then the most senior one alone. */
export function groupTexts(levels: readonly KeyLevel[]): string[] {
  if (levels.length === 0) return [];
  const all = levels.map((l) => l.short).join(' · ');
  return levels.length > 1 ? [all, `${levels[0]!.short} +${levels.length - 1}`, levels[0]!.short] : [all];
}

/** Hover title: "Previous day high, Asia session high at 24,743.50". */
export function groupTitle(levels: readonly KeyLevel[], price: number, decimals: number): string {
  return `${levels.map((l) => l.name).join(', ')} at ${formatPrice(price, decimals)}`;
}

/**
 * Lines to draw from those on the visible prices (each with its y, in any order). The most
 * senior are kept first, ties going to the one nearer `ref` (the last close); a level closer
 * than `gap` pixels to one already kept is left out, so two labels never fight for one strip.
 * What was left out is listed under the kept level it gave way to (`near`), for its hover.
 */
export function thinByGap<T extends { y: number; levels: readonly KeyLevel[]; group: { price: number } }>(
  on: readonly T[],
  gap: number,
  ref: number | null = null,
): { kept: T[]; near: Map<T, T[]> } {
  const dist = (t: T) => (ref === null ? 0 : Math.abs(t.group.price - ref));
  // a level the core sent (alone or merged into a computed one) ranks as core: it never gives way to a computed one
  const rank = (t: T) => (t.levels.some((l) => l.family === 'core' || l.coreSent) ? RANK.core : RANK[t.levels[0]!.family]);
  const ranked = [...on].sort((a, b) => rank(a) - rank(b) || dist(a) - dist(b));
  const kept: T[] = [];
  const near = new Map<T, T[]>();
  for (const k of ranked) {
    const blocker = kept.find((m) => Math.abs(m.y - k.y) < gap);
    if (!blocker) kept.push(k);
    else near.set(blocker, [...(near.get(blocker) ?? []), k]);
  }
  return { kept, near };
}

/**
 * The levels above `price` and below it (at or on it counts as neither), nearest first, at most
 * `n` a side: the candidates for the one price tag each side gets (the next stands in when the
 * nearest one's tag has no room).
 */
export function nearestAround<G extends { price: number }>(groups: readonly G[], price: number, n = 2): { up: G[]; down: G[] } {
  const up = groups.filter((g) => g.price > price).sort((a, b) => a.price - b.price).slice(0, n);
  const down = groups.filter((g) => g.price < price).sort((a, b) => b.price - a.price).slice(0, n);
  return { up, down };
}

/**
 * Levels past the visible prices, for the edge chips: the nearest `max` above the top and
 * below the bottom, nearest first.
 */
export function edgeGroups<G extends { price: number }>(groups: readonly G[], top: number, bottom: number, max = 2): { above: G[]; below: G[] } {
  const above = groups.filter((g) => g.price > top).sort((a, b) => a.price - b.price).slice(0, max);
  const below = groups.filter((g) => g.price < bottom).sort((a, b) => b.price - a.price).slice(0, max);
  return { above, below };
}

/**
 * The levels of a group that have begun by the right edge of what is shown: `xOf` gives a start's
 * x. Judged per level, so one merged at an older level's price is not named before it began.
 */
export function begunLevels(levels: readonly KeyLevel[], xOf: (start: number) => number, right: number): KeyLevel[] {
  return levels.filter((l) => l.start === null || xOf(l.start) < right);
}

/**
 * Edge chip places. `widths` are the chips' widths, nearest level first; `slotY(n)` is the top of
 * slot n counted from the edge (null past the plot). A chip sits right-aligned at `right` and never
 * on a box in `blocks` (candles, lines on screen): it slides left past what it hits, else takes the
 * next slot. The nearest levels get places first (as many as fit), stacked with the farthest at the
 * edge so the stack reads in price order. Returned in the order given; null for a chip with no place.
 */
export function stackChips(
  widths: readonly number[],
  slotY: (n: number) => number | null,
  right: number,
  height: number,
  blocks: readonly Box[],
  maxSlots: number,
): (Box | null)[] {
  const fit = (w: number, n: number): Box | null => {
    const y = slotY(n);
    if (y === null) return null;
    let box: Box = { x: right - w, y, w, h: height };
    for (let tries = 0; tries < 3; tries++) {
      const hit = blocks.filter((b) => overlaps(b, box));
      if (hit.length === 0) return box;
      box = { ...box, x: Math.min(...hit.map((b) => b.x)) - w - 4 };
      if (box.x < 4) return null;
    }
    return null;
  };
  for (let n = widths.length; n > 0; n--) {
    const boxes: Box[] = [];
    let slot = 0;
    for (const w of widths.slice(0, n).reverse()) {
      let box: Box | null = null;
      while (slot < maxSlots && !(box = fit(w, slot))) slot++;
      if (!box) break;
      boxes.push(box);
      slot++;
    }
    if (boxes.length === n) {
      const out: (Box | null)[] = widths.map(() => null);
      boxes.reverse().forEach((b, i) => (out[i] = b));
      return out;
    }
  }
  return widths.map(() => null);
}

/**
 * Leaves out the lines `drop` picks, each listed under the nearest line kept (by y) in `near`,
 * together with whatever was already listed under it, so no level ever leaves the hovers. Returns
 * the lines kept; `near` is updated in place.
 */
export function foldInto<T extends { y: number }>(lines: readonly T[], near: Map<T, T[]>, drop: (line: T) => boolean): T[] {
  const dropped = lines.filter(drop);
  const kept = lines.filter((l) => !dropped.includes(l));
  for (const d of dropped) {
    const carried = [d, ...(near.get(d) ?? [])];
    near.delete(d);
    const host = kept.reduce<T | null>((best, k) => (!best || Math.abs(k.y - d.y) < Math.abs(best.y - d.y) ? k : best), null);
    if (host) near.set(host, [...(near.get(host) ?? []), ...carried]);
  }
  return kept;
}

/**
 * Where a key level's name of width `w` may go, best first: above its line when the line is above
 * the last close, else below (`below`), at the line's right end, then further left along it in
 * half-name steps; the other side only when its strip has room for two names or the preferred side
 * is off the plot; last, for every line, a lead-in just left of where it starts, centred on it
 * (sliding past `blocks` only while it stays within one label height of the start). Spots stay on
 * the line (never left of its start) except that a line shorter than its name keeps it at its right
 * end, reaching left. No spot crosses another key line (`others`, each with its start x), so a name
 * always sits in its own line's strip. `line.x` is where the line starts, `right` where names end.
 */
export function keyNameSpots(
  line: { x: number; y: number },
  others: readonly { x: number; y: number }[],
  w: number,
  right: number,
  lh: number,
  plotH: number,
  below: boolean,
  blocks: readonly Box[] = [],
): Box[] {
  const { x, y } = line;
  const side = (lx: number, up: boolean): Box => (up ? { x: lx, y: y - 3 - lh, w, h: lh } : { x: lx, y: y + 3, w, h: lh });
  // along the line from its right end leftwards in half-name steps, then at its start
  const steps: number[] = [];
  for (let lx = right - w; lx >= x + 2 && steps.length < 40; lx -= Math.max(8, w / 2)) steps.push(lx);
  const on = [...steps, x + 4].filter((lx) => lx >= x + 2 && lx + w <= right);
  const xs = on.length ? on : [right - w];
  const roomy = (up: boolean) => others.every((o) => (up ? o.y > y || y - o.y >= 2 * lh + 6 : o.y < y || o.y - y >= 2 * lh + 6));
  const offPlot = xs.every((lx) => {
    const b = side(lx, !below);
    return b.y < 0 || b.y + b.h > plotH;
  });
  const flipped = roomy(below) || offPlot ? xs.map((lx) => side(lx, below)) : [];
  // The lead-in, for every line: just left of where it starts, centred on it, sliding further left
  // past whatever in `blocks` (candles) it would cover, but only while its right end stays within one
  // label height of the line's start: a name further off would read as no line's (it gives way).
  let leadBox: Box | null = { x: x - w - 4, y: y - lh / 2, w, h: lh };
  for (let tries = 0; leadBox && tries < 4; tries++) {
    const hit = blocks.filter((b) => overlaps(b, leadBox!));
    if (hit.length === 0) break;
    leadBox = { ...leadBox, x: Math.min(...hit.map((b) => b.x)) - w - 4 };
    if (tries === 3) leadBox = null;
  }
  const near = (b: Box) => b.x + b.w >= x - lh;
  const lead: Box[] = leadBox && leadBox.x >= 4 && near(leadBox) && !blocks.some((b) => overlaps(b, leadBox!)) ? [leadBox] : [];
  // a spot never crosses another key line, and keeps 6 px from the next line on its own side, so a
  // name sits nearer its own line than any other (a close pair splits to opposite sides)
  const clear = (b: Box) =>
    others.every((o) => {
      if (b.x + b.w <= o.x) return true;
      const centred = b.y < y && b.y + b.h > y;
      if (centred) return o.y < b.y - 1 || o.y > b.y + b.h + 1;
      return b.y >= y ? o.y <= y || o.y > b.y + b.h + 6 : o.y >= y || o.y < b.y - 6;
    });
  return [...xs.map((lx) => side(lx, !below)), ...flipped, ...lead].filter(clear);
}

/**
 * Whether a week, day or core line whose name found no clear spot may still take `box` (its
 * right-end spot) over candles: only while its period has just begun (the line, `lineLength` px,
 * is shorter than three of its names, `nameW`) yet long enough to be seen as a line (at least a
 * label height, `lh`), with `box` inside the plot and clear of `blocks` (other labels, chips, trade
 * lines). Far zoomed out a line is a stub: its name gives way rather than cover the newest candles.
 */
export function justBegunSpot(lineLength: number, nameW: number, lh: number, box: Box, plot: { w: number; h: number }, blocks: readonly Box[]): boolean {
  if (lineLength < lh || lineLength >= 3 * nameW) return false;
  if (box.x < 0 || box.y < 0 || box.x + box.w > plot.w || box.y + box.h > plot.h) return false;
  return !blocks.some((b) => overlaps(b, box));
}

/**
 * The spots clear of every column hairline except those at the line's own `price` (to `decimals`):
 * whether that one is drawn depends on whether this line is, so ignoring it gives the same answer
 * from any history.
 */
export function clearOfSpans<B extends Box>(spots: readonly B[], spans: readonly (Box & { price: number })[], price: number, decimals: number): B[] {
  const own = price.toFixed(decimals);
  const bars = spans.filter((s) => s.price.toFixed(decimals) !== own);
  return spots.filter((b) => !bars.some((s) => overlaps(s, b)));
}

/**
 * Among `candidates` inside the plot and clear of `blocks`, the one covering the least candle area
 * (`candles`), with that area; null when none is clear.
 */
export function leastCoverSpot(candidates: readonly Box[], plot: { w: number; h: number }, blocks: readonly Box[], candles: readonly Box[]): { box: Box; cover: number } | null {
  const area = (b: Box, c: Box) => Math.max(0, Math.min(b.x + b.w, c.x + c.w) - Math.max(b.x, c.x)) * Math.max(0, Math.min(b.y + b.h, c.y + c.h) - Math.max(b.y, c.y));
  let best: { box: Box; cover: number } | null = null;
  for (const b of candidates) {
    if (b.x < 0 || b.y < 0 || b.x + b.w > plot.w || b.y + b.h > plot.h || blocks.some((k) => overlaps(k, b))) continue;
    const cover = candles.reduce((sum, c) => sum + area(b, c), 0);
    if (!best || cover < best.cover) best = { box: b, cover };
  }
  return best;
}

/** Whether a name's candle cover is slight: under 15% of its box. */
export function slightCover(spot: { box: Box; cover: number }): boolean {
  return spot.cover <= 0.15 * spot.box.w * spot.box.h;
}

/**
 * The just-begun fallback's spot for a senior name, or null: the least candle-covering clear spot
 * (leastCoverSpot), taken only while the line is short but visible (justBegunSpot's length rule)
 * and either the period has run at most a quarter of its length (`elapsed` of `period`, in
 * minutes: 42 hours of a week, 6 of a day) or the cover is slight: a name never sits over a run of
 * today's candles.
 */
export function bestJustBegunSpot(
  lineLength: number,
  nameW: number,
  lh: number,
  candidates: readonly Box[],
  plot: { w: number; h: number },
  blocks: readonly Box[],
  candles: readonly Box[],
  elapsed: number,
  period: number,
): Box | null {
  if (lineLength < lh || lineLength >= 3 * nameW) return null;
  const best = leastCoverSpot(candidates, plot, blocks, candles);
  if (!best) return null;
  return elapsed <= 0.25 * period || slightCover(best) ? best.box : null;
}

/**
 * The stored answer for each line of `all` that `eligible` picks (fine lines, short senior stubs):
 * named when the label pass placed its name (`placed`), else unnamed, including a line the passes
 * dropped before the last one, so an earlier answer never outlives the geometry it came from.
 */
export function nameAnswers<T>(all: readonly T[], placed: ReadonlySet<T>, eligible: (line: T) => boolean): Map<T, boolean> {
  const out = new Map<T, boolean>();
  for (const line of all) if (eligible(line)) out.set(line, placed.has(line));
  return out;
}
