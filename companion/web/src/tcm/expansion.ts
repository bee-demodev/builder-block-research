// TCM Expansions: the expansion -> range -> CSD process from the TCM Core call
// "Revisiting Expansions" (rules and timestamps in knowledge/tcm/revisiting_expansions.md).
//
// An expansion is two or more candles of one colour, each closing beyond the one before
// (down candles closing below each other). The first candle that does not close beyond
// ends it and confirms the range: the expansion's high and low, and EQ, its 50% line.
// A down expansion gives a long idea (and an up expansion a short one) once price shows:
// a candle closing above 50% of the last expansion candle (enough to participate), then
// CSD, a close above that candle's open. The CSD candle's wick says where to buy, a close
// above EQ says the trade may be held, and the range high is the target.
//
// Everything here is pure: it reads closed bars up to a cursor (a replay can stop
// anywhere) and returns what each rule says at that moment. An up expansion is read by
// mirroring prices, so the rules are written once, for the down case.

export interface Bar {
  /** Open time, epoch seconds (the companion's New York wall clock written as UTC). */
  t: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

/** The expansion's direction: "down" candles closing below each other, or "up". */
export type ExpansionDir = 'down' | 'up';
export type Idea = 'long' | 'short';

export interface Range {
  dir: ExpansionDir;
  /** First and last expansion candle (bar indexes). */
  start: number;
  end: number;
  high: number;
  low: number;
  /** Equilibrium: 50% of the range. */
  eq: number;
  /** 50% of the last expansion candle. */
  half: number;
  /** The open of the last expansion candle: closing through it is CSD. */
  csd: number;
}

/** Fewest candles that make an expansion; one big candle is "not an expansion" (40:55). */
export const MIN_RUN = 2;
/** An upper wick (lower, for a short) at least this share of the CSD candle is a "big wick". */
export const BIG_WICK = 0.3;

export type StepStatus = 'pass' | 'fail' | 'waiting' | 'na';
export type StepKey = 'expansion' | 'range' | 'size' | 'olr' | 'half' | 'csd' | 'entry' | 'eq' | 'target' | 'void';

export interface Step {
  key: StepKey;
  title: string;
  status: StepStatus;
  detail: string;
  /** The bar the step was decided on, if any. */
  at: number | null;
  /** Where the video says it, "mm:ss". */
  ref: string;
  optional?: boolean;
}

export type LevelKey = 'high' | 'low' | 'eq' | 'half' | 'csd' | 'entry' | 'stop';

export interface Level {
  key: LevelKey;
  label: string;
  price: number;
  /** The bar the level starts at; it runs to the right edge. */
  from: number;
}

export type EventKey = 'confirm' | 'olr' | 'half' | 'csd' | 'fill' | 'eq' | 'target' | 'void';

export interface RangeEvent {
  key: EventKey;
  index: number;
  label: string;
  /** Drawn above the candle (else below). */
  above: boolean;
}

export type VerdictTone = 'long' | 'short' | 'watch' | 'muted' | 'bear';

export interface Reading {
  range: Range;
  idea: Idea;
  size: number;
  steps: Step[];
  levels: Level[];
  events: RangeEvent[];
  entry: number | null;
  stop: number | null;
  risk: number | null;
  /** Bar where a close beyond the range's far side ended it. */
  voidAt: number | null;
  verdict: { word: string; tone: VerdictTone; detail: string };
}

export interface ReadOptions {
  /** Smallest range worth a scalp, in price units (the video's example: 30 points). */
  minSize: number;
  decimals: number;
  /** How a bar is named in the text, e.g. "09:55". */
  barName?: (bar: Bar, index: number) => string;
  /** The trader set the range's candles by hand, so they need not follow the rule. */
  manual?: boolean;
}

// ---------- finding the expansion ----------

function colour(b: Bar): ExpansionDir | null {
  return b.close < b.open ? 'down' : b.close > b.open ? 'up' : null;
}

/** Bar i is the expansion's colour and closes beyond the bar before it. */
function continues(bars: readonly Bar[], i: number, dir: ExpansionDir): boolean {
  const b = bars[i];
  const prev = bars[i - 1];
  if (!b || !prev || colour(b) !== dir) return false;
  return dir === 'down' ? b.close < prev.close : b.close > prev.close;
}

/** The range of candles start..end read as an expansion in `dir`. */
export function rangeOf(bars: readonly Bar[], start: number, end: number, dir: ExpansionDir): Range {
  let high = -Infinity;
  let low = Infinity;
  for (let i = start; i <= end; i++) {
    high = Math.max(high, bars[i]!.high);
    low = Math.min(low, bars[i]!.low);
  }
  const last = bars[end]!;
  return { dir, start, end, high, low, eq: (high + low) / 2, half: (last.high + last.low) / 2, csd: last.open };
}

/**
 * The expansion that candle `at` belongs to, using bars up to `limit` only (a replay
 * does not see the future). Null when `at` is a doji or its run is shorter than MIN_RUN.
 */
export function detectRange(bars: readonly Bar[], at: number, limit = bars.length - 1): Range | null {
  const bar = bars[at];
  if (!bar || at > limit) return null;
  const dir = colour(bar);
  if (!dir) return null;
  let start = at;
  while (start > 0 && continues(bars, start, dir) && colour(bars[start - 1]!) === dir) start--;
  let end = at;
  while (end + 1 <= limit && continues(bars, end + 1, dir)) end++;
  if (end - start + 1 < MIN_RUN) return null;
  return rangeOf(bars, start, end, dir);
}

/**
 * The most recent confirmed expansion at or before `limit` whose range is at least
 * `minSize`. `alive`: skip ranges a later close (up to `limit`) has already gone through.
 */
export function latestRange(bars: readonly Bar[], limit = bars.length - 1, minSize = 0, alive = false): Range | null {
  for (let i = limit - 1; i >= 1; i--) {
    const r = detectRange(bars, i, limit);
    if (!r || r.end !== i || r.high - r.low < minSize) continue;
    if (alive && isVoid(bars, r, limit)) continue;
    return r;
  }
  return null;
}

function isVoid(bars: readonly Bar[], r: Range, limit: number): boolean {
  for (let k = r.end + 1; k <= limit; k++) {
    const c = bars[k]!.close;
    if (r.dir === 'down' ? c < r.low : c > r.high) return true;
  }
  return false;
}

/**
 * How the tab picks the range it reads. One function for the tab and the shadow, so a shadow
 * branch is read on the very range the tab would show once that candle printed.
 *  - latest: live with nothing pinned; the newest confirmed range still in play, big enough if one is;
 *  - anchor: a candle of the expansion was picked (a click, or a lesson's own expansion);
 *  - manual: the trader set the range's first and last candle by hand.
 * Indexes are bar indexes; a shadow adds its ghost on the end, so they stay valid.
 */
export type RangePick =
  | { kind: 'latest'; minSize: number }
  | { kind: 'anchor'; at: number }
  | { kind: 'manual'; start: number; end: number; dir: ExpansionDir };

export function pickRange(bars: readonly Bar[], cursor: number, pick: RangePick): Range | null {
  switch (pick.kind) {
    case 'latest':
      return latestRange(bars, cursor, pick.minSize, true) ?? latestRange(bars, cursor, 0, true);
    case 'anchor':
      return pick.at <= cursor ? detectRange(bars, pick.at, cursor) : null;
    case 'manual':
      return pick.start >= 0 && pick.start < pick.end && pick.end <= cursor ? rangeOf(bars, pick.start, pick.end, pick.dir) : null;
  }
}

// ---------- reading the range, candle by candle ----------

const flipBar = (b: Bar): Bar => ({ t: b.t, open: -b.open, close: -b.close, high: -b.low, low: -b.high });
const flipRange = (r: Range): Range => ({ ...r, dir: 'down', high: -r.low, low: -r.high, eq: -r.eq, half: -r.half, csd: -r.csd });

/** Words for the real direction; the rules are written for a down expansion (long idea). */
interface Words {
  idea: Idea;
  run: string; // "down candles"
  beyond: string; // "below"
  through: string; // "above" (the way back)
  far: string; // "low"
  near: string; // "high"
  opposite: string; // "green"
  wickSide: string; // "upper"
}

const DOWN_WORDS: Words = { idea: 'long', run: 'down candles', beyond: 'below', through: 'above', far: 'low', near: 'high', opposite: 'green', wickSide: 'upper' };
const UP_WORDS: Words = { idea: 'short', run: 'up candles', beyond: 'above', through: 'below', far: 'high', near: 'low', opposite: 'red', wickSide: 'lower' };

const defaultBarName = (bar: Bar): string => {
  const d = new Date(bar.t * 1000);
  return `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
};

/**
 * What each rule says about `range` as of bar `cursor`. Bars after the cursor are not read.
 */
export function readRange(bars: readonly Bar[], range: Range, cursor: number, opts: ReadOptions): Reading {
  const up = range.dir === 'up';
  const w = up ? UP_WORDS : DOWN_WORDS;
  const fb = up ? bars.map(flipBar) : bars;
  const r = up ? flipRange(range) : range;
  const real = (p: number) => (up ? -p : p);
  const px = (p: number) => fmt(real(p), opts.decimals);
  const pts = (n: number) => fmt(Math.abs(n), opts.decimals);
  const name = (i: number) => (opts.barName ?? defaultBarName)(bars[i]!, i);
  const last = Math.min(cursor, bars.length - 1);
  const size = r.high - r.low;

  // One pass over the candles after the expansion, stopping where the range dies.
  const confirmAt = r.end + 1 <= last ? r.end + 1 : null;
  let voidAt: number | null = null;
  let sweepAt: number | null = null;
  let halfAt: number | null = null;
  let csdAt: number | null = null;
  for (let k = r.end + 1; k <= last; k++) {
    const b = fb[k]!;
    if (b.close < r.low) {
      voidAt = k;
      break;
    }
    if (csdAt !== null) continue;
    if (sweepAt === null && b.low < r.low) sweepAt = k;
    if (halfAt === null && b.close > b.open && b.close > r.half) halfAt = k;
    if (b.close > r.csd) {
      csdAt = k;
      halfAt ??= k;
    }
  }
  const stopAt = voidAt === null ? last : voidAt - 1;

  // After CSD: the entry from the wick read, the EQ close, the targets.
  let entry: number | null = null;
  let stop: number | null = null;
  let bigWick = false;
  let wickShare = 0;
  let fillAt: number | null = null;
  let noDipAt: number | null = null;
  let holdAt: number | null = null;
  let lostAt: number | null = null;
  let eqTouchAt: number | null = null;
  let targetAt: number | null = null;
  if (csdAt !== null) {
    const c = fb[csdAt]!;
    entry = c.close;
    const span = c.high - c.low;
    wickShare = span > 0 ? (c.high - Math.max(c.open, c.close)) / span : 0;
    bigWick = wickShare >= BIG_WICK;
    stop = Infinity;
    for (let i = r.start; i <= csdAt; i++) stop = Math.min(stop, fb[i]!.low);
    if (csdAt + 1 <= stopAt && fb[csdAt + 1]!.low >= entry) noDipAt = csdAt + 1;
    for (let k = csdAt; k <= stopAt; k++) {
      const b = fb[k]!;
      if (k > csdAt && fillAt === null && b.low < entry) fillAt = k;
      if (holdAt === null && lostAt === null) {
        // A close past EQ counts only from a candle that traded through it: a gap past EQ is not a close above it (71:27).
        if (b.close > r.eq && b.low < r.eq) holdAt = k;
        else if (k > csdAt && b.close < r.csd) lostAt = k;
      }
      if (k > csdAt && eqTouchAt === null && b.high >= r.eq) eqTouchAt = k;
      if (k > csdAt && targetAt === null && b.high >= r.high) targetAt = k;
    }
  }
  const risk = entry !== null && stop !== null ? entry - stop : null;

  // ---------- the steps, in the order the video walks them ----------
  const runLen = r.end - r.start + 1;
  const steps: Step[] = [];
  const dead = voidAt !== null;
  const pending = (s: Omit<Step, 'status'> & { status: StepStatus }): Step => (dead && s.status === 'waiting' ? { ...s, status: 'na' } : s);

  steps.push({
    key: 'expansion',
    title: 'Expansion',
    status: 'pass',
    detail: opts.manual
      ? `Set by hand: ${runLen} candles, ${name(r.start)} to ${name(r.end)}.`
      : `${runLen} ${w.run} closing ${w.beyond} each other, ${name(r.start)} to ${name(r.end)}.`,
    at: r.end,
    ref: '05:52',
  });
  steps.push(
    pending({
      key: 'range',
      title: 'Range confirmed',
      status: confirmAt !== null ? 'pass' : 'waiting',
      detail:
        confirmAt !== null
          ? `${name(confirmAt)} did not close ${w.beyond} ${px(fb[r.end]!.close)}, so the expansion stopped. Range ${w.near} ${px(r.high)}, ${w.far} ${px(r.low)}, EQ ${px(r.eq)}.`
          : `Waiting for a candle that does not close ${w.beyond} ${px(fb[r.end]!.close)}.`,
      at: confirmAt,
      ref: '06:23',
    }),
  );
  steps.push({
    key: 'size',
    title: 'Range big enough to trade',
    status: size >= opts.minSize ? 'pass' : 'fail',
    detail:
      size >= opts.minSize
        ? `${pts(size)} points (your minimum ${pts(opts.minSize)}). Room for a scalp.`
        : `${pts(size)} points, under your minimum ${pts(opts.minSize)}. A tight range needs a perfect entry and may never reach its ${w.near}.`,
    at: r.end,
    ref: '07:25',
  });
  steps.push(
    pending({
      key: 'olr',
      title: `Range ${w.far} swept (OLR)`,
      optional: true,
      status: sweepAt !== null ? 'pass' : csdAt !== null ? 'na' : 'waiting',
      detail:
        sweepAt !== null
          ? `${name(sweepAt)} ran the range ${w.far} and closed back inside: the opposing liquidity run.`
          : csdAt !== null
            ? `CSD came without a sweep of the ${w.far}. Optional, not required.`
            : `Optional: a run past the range ${w.far} that closes back inside, before CSD.`,
      at: sweepAt,
      ref: '42:50',
    }),
  );
  steps.push(
    pending({
      key: 'half',
      title: `Close ${w.through} 50% of the last candle`,
      status: halfAt !== null ? 'pass' : 'waiting',
      detail:
        halfAt !== null
          ? `${name(halfAt)} closed ${w.through} ${px(r.half)}. Enough to participate, not yet strength.`
          : `Waiting for a ${w.opposite} candle closing ${w.through} ${px(r.half)}.`,
      at: halfAt,
      ref: '09:32',
    }),
  );
  steps.push(
    pending({
      key: 'csd',
      title: 'CSD',
      status: csdAt !== null ? 'pass' : 'waiting',
      detail:
        csdAt !== null
          ? `${name(csdAt)} closed ${w.through} ${px(r.csd)}, the open of the last expansion candle. The state of delivery changed.`
          : `Waiting for a close ${w.through} ${px(r.csd)}, the open of the last expansion candle.`,
      at: csdAt,
      ref: '55:51',
    }),
  );

  let entryDetail: string;
  if (csdAt === null || entry === null) {
    entryDetail = 'Read the CSD candle’s wick once it closes.';
  } else {
    const share = `${Math.round(wickShare * 100)}%`;
    const read = bigWick
      ? `Big ${w.wickSide} wick (${share} of the candle): expect the next candle to trade back ${w.beyond} the close ${px(entry)}. Get in ${w.beyond} it; the bigger the wick, the deeper.`
      : `Small ${w.wickSide} wick (${share}): no deep pullback expected. Get in just ${w.beyond} the close ${px(entry)}.`;
    const tail =
      fillAt !== null
        ? ` Filled at ${name(fillAt)}.`
        : noDipAt !== null
          ? ` ${name(noDipAt)} did not come back: plan versus reality, do not chase.`
          : '';
    entryDetail = read + tail;
  }
  steps.push(
    pending({
      key: 'entry',
      title: 'Entry from the wick',
      status: fillAt !== null ? 'pass' : 'waiting',
      detail: entryDetail,
      at: fillAt,
      ref: bigWick ? '10:41' : '26:33',
    }),
  );
  steps.push(
    pending({
      key: 'eq',
      title: `Close ${w.through} EQ to hold`,
      status: holdAt !== null ? 'pass' : lostAt !== null ? 'fail' : 'waiting',
      detail:
        holdAt !== null
          ? `${name(holdAt)} closed ${w.through} EQ ${px(r.eq)}: holding is allowed, aim for the range ${w.near}.`
          : lostAt !== null
            ? `${name(lostAt)} closed back ${w.beyond} the CSD level before EQ: a scalp only, manage at EQ ${px(r.eq)}.`
            : `Until a close ${w.through} EQ ${px(r.eq)}, treat it as a scalp and manage at EQ.`,
      at: holdAt ?? lostAt,
      ref: '13:48',
    }),
  );
  steps.push(
    pending({
      key: 'target',
      title: `Targets: EQ, then range ${w.near}`,
      status: targetAt !== null ? 'pass' : 'waiting',
      detail:
        targetAt !== null
          ? `${name(targetAt)} reached the range ${w.near} ${px(r.high)}.`
          : eqTouchAt !== null
            ? `EQ ${px(r.eq)} reached at ${name(eqTouchAt)}; the range ${w.near} ${px(r.high)} is next.`
            : `EQ ${px(r.eq)} first, then the range ${w.near} ${px(r.high)}.`,
      at: targetAt ?? eqTouchAt,
      ref: '22:02',
    }),
  );
  if (voidAt !== null) {
    steps.push({
      key: 'void',
      title: 'Range void',
      status: 'fail',
      detail: `${name(voidAt)} closed ${w.beyond} the range ${w.far} ${px(r.low)}: this range is done and a new expansion is forming. Click its last candle.`,
      at: voidAt,
      ref: '20:41',
    });
  }

  // ---------- levels and chart events, in real prices ----------
  const levels: Level[] = [
    { key: 'high', label: up ? 'Range low' : 'Range high', price: real(r.high), from: r.start },
    { key: 'low', label: up ? 'Range high' : 'Range low', price: real(r.low), from: r.start },
    { key: 'eq', label: 'EQ', price: real(r.eq), from: r.start },
    { key: 'half', label: '50% last', price: real(r.half), from: r.end },
    { key: 'csd', label: 'CSD', price: real(r.csd), from: r.end },
  ];
  if (entry !== null && csdAt !== null) levels.push({ key: 'entry', label: 'Entry', price: real(entry), from: csdAt });
  if (stop !== null && csdAt !== null) levels.push({ key: 'stop', label: 'Stop', price: real(stop), from: csdAt });

  // "above" in flipped prices is "below" for real when the expansion went up.
  const ev = (key: EventKey, index: number | null, label: string, aboveDown: boolean): RangeEvent[] =>
    index === null ? [] : [{ key, index, label, above: up ? !aboveDown : aboveDown }];
  const events = [
    ...ev('confirm', confirmAt, 'Range', false),
    ...ev('olr', sweepAt, 'OLR', false),
    ...(halfAt !== null && halfAt === csdAt ? [] : ev('half', halfAt, '50%', true)),
    ...ev('csd', csdAt, halfAt === csdAt ? '50% + CSD' : 'CSD', true),
    ...ev('fill', fillAt, 'Fill', false),
    ...ev('eq', holdAt, 'EQ close', true),
    ...ev('target', targetAt, 'Target', true),
    ...ev('void', voidAt, 'Void', false),
  ];

  return {
    range,
    idea: w.idea,
    size,
    steps,
    levels,
    events,
    entry: entry === null ? null : real(entry),
    stop: stop === null ? null : real(stop),
    risk,
    voidAt,
    verdict: verdict(),
  };

  function verdict(): Reading['verdict'] {
    const side = w.idea === 'long' ? 'long' : 'short';
    const Side = w.idea === 'long' ? 'Long' : 'Short';
    if (voidAt !== null) return { word: 'Range void', tone: 'bear', detail: `The range ${w.far} closed through. Find the new expansion.` };
    if (confirmAt === null) return { word: 'Expansion running', tone: 'watch', detail: `No range until a candle stops closing ${w.beyond}.` };
    if (size < opts.minSize) return { word: 'Range too small', tone: 'muted', detail: `${pts(size)} points: watch it, do not force a scalp.` };
    if (csdAt === null || entry === null) {
      return halfAt === null
        ? { word: `Watch, ${side}`, tone: 'watch', detail: `Wait for a close ${w.through} 50% of the last candle (${px(r.half)}).` }
        : { word: `Watch, ${side}`, tone: 'watch', detail: `Wait for CSD: a close ${w.through} ${px(r.csd)}.` };
    }
    if (fillAt === null) {
      return noDipAt !== null
        ? { word: `${Side} idea`, tone: w.idea, detail: `No pullback ${w.beyond} ${px(entry)} yet: do not chase. Wait for it; stop past ${px(stop!)}.` }
        : { word: `${Side} idea`, tone: w.idea, detail: `Get in ${w.beyond} ${px(entry)}. Stop past ${px(stop!)}.` };
    }
    if (targetAt !== null) return { word: 'Target reached', tone: w.idea, detail: `Range ${w.near} ${px(r.high)} traded.` };
    if (lostAt !== null) return { word: 'Scalp only', tone: 'watch', detail: `No close ${w.through} EQ. Manage at EQ ${px(r.eq)}.` };
    if (holdAt !== null) return { word: `${Side}, hold`, tone: w.idea, detail: `Closed ${w.through} EQ. Aim for the range ${w.near} ${px(r.high)}.` };
    return { word: `${Side} scalp`, tone: w.idea, detail: `In. Manage at EQ ${px(r.eq)} until a close ${w.through} it.` };
  }
}

function fmt(value: number, decimals: number): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
