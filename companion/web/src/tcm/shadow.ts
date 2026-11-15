// Shadow: the two ways the next candle can go at the decision pending now, drawn as a
// ghost candle in the empty slot right of the last candle. "A" settles the decision the
// way the idea needs; "B" does not. Each ghost is an illustration: its size comes from
// the range's own levels and the recent candle size, and is not a forecast. What it would
// mean is never written by hand: `after` is the rules' read (readRange) with the ghost
// added, and the caption is that read's verdict.
import { pickRange, readRange, type Bar, type RangePick, type Range, type ReadOptions, type Reading, type StepKey, type StepStatus } from './expansion';
import type { Semantic } from '../tones';

export type ShadowKey = 'A' | 'B';
/** How a branch is coloured: on plan, against it, or neither (an expansion running on). */
export type ShadowTone = 'good' | 'bad' | 'neutral';
/** The one place a branch's tone becomes a colour: the switch, the caption and the chip all use it. */
export const SHADOW_SEMANTIC: Record<ShadowTone, Semantic> = { good: 'bull', bad: 'bear', neutral: 'muted' };

export interface ShadowBranch {
  key: ShadowKey;
  /** Short name for the switch, at most about 12 characters: "Above 50%". */
  short: string;
  /** The condition, as a clause: "If it closes above 50%". */
  title: string;
  /** The ghost candle, in real prices, one bar after the last candle shown. */
  candle: Bar;
  /** The rules' read with the ghost candle added: the caption is its verdict. */
  after: Reading;
  tone: ShadowTone;
}

/** The decisions a single next candle settles, in the order the rules meet them. */
export type ShadowDecision = Extract<StepKey, 'range' | 'half' | 'csd' | 'entry' | 'eq'>;
const DECISIONS: readonly ShadowDecision[] = ['range', 'half', 'csd', 'entry', 'eq'];

export interface Shadow {
  /** The decision the next candle settles. */
  decision: ShadowDecision;
  /** The rules' read now, without a ghost: a branch that leaves it as it is says so. */
  now: Reading;
  /** "Next candle at 50% (21,449)". */
  question: string;
  a: ShadowBranch;
  b: ShadowBranch;
}

interface Raw {
  open: number;
  high: number;
  low: number;
  close: number;
}

/** Typical candle size near the cursor: the mean range of the last five candles. */
function unit(bars: readonly Bar[], cursor: number): number {
  const from = Math.max(0, cursor - 4);
  let sum = 0;
  for (let i = from; i <= cursor; i++) sum += bars[i]!.high - bars[i]!.low;
  return Math.max(sum / (cursor - from + 1), 1e-9);
}

/** A candle opening at `open` and closing at `close`, its wicks a share of the unit past the body. */
function candle(open: number, close: number, u: number, up = 0.12, down = 0.12): Raw {
  return { open, close, high: Math.max(open, close) + up * u, low: Math.min(open, close) - down * u };
}

/**
 * A price strictly below `ref` and strictly above `floor` when there is room: `ref` less
 * `want`, but never more than halfway down to the floor.
 */
function below(ref: number, floor: number, want: number): number {
  const room = ref - floor;
  return room > 0 ? ref - Math.min(want, room / 2) : ref;
}

const flip = (c: Raw): Raw => ({ open: -c.open, close: -c.close, high: -c.low, low: -c.high });

const stepOf = (r: Reading, key: StepKey): StepStatus | undefined => r.steps.find((x) => x.key === key)?.status;

/**
 * The two branches at the cursor, or null when nothing is pending: no range yet, the
 * range is void or too small, the target has traded (filled or not), or the idea is held
 * and only the target is left.
 */
export function shadowAt(bars: readonly Bar[], range: Range, cursor: number, opts: ReadOptions, pick: RangePick): Shadow | null {
  return explainShadow(bars, range, cursor, opts, pick).shadow;
}

/** Why there is no shadow, for the switch's tooltip and screen readers. */
export type ShadowOff = 'nothing' | 'void' | 'small' | 'target' | 'held' | 'manual' | 'past-target' | 'switch' | 'room';

export const SHADOW_OFF_TEXT: Record<ShadowOff, string> = {
  nothing: 'No shadow: no decision is pending at this candle.',
  void: 'No shadow: this range is void.',
  small: 'No shadow: the range is below your minimum size.',
  target: 'No shadow: the target has traded.',
  held: 'No shadow: the idea is held; only the target is left.',
  manual: 'No shadow here: the next candle confirms a hand-set range either way.',
  'past-target': 'No shadow: price is already past the target.',
  switch: 'No shadow here: the next candle could start a newer range, which the tab would follow. Click a candle to pin this one.',
  room: 'No shadow here: the levels sit too close to draw an honest candle between them.',
};

/** The shadow at the cursor, or why there is none. */
export function explainShadow(bars: readonly Bar[], range: Range, cursor: number, opts: ReadOptions, pick: RangePick): { shadow: Shadow | null; off: ShadowOff | null } {
  const none = (off: ShadowOff) => ({ shadow: null, off });
  const now = readRange(bars, range, cursor, opts);
  const status = (k: StepKey) => stepOf(now, k);
  if (now.voidAt !== null) return none('void');
  if (now.size < opts.minSize) return none('small');
  if (status('target') === 'pass') return none('target');
  const decision = DECISIONS.find((k) => status(k) === 'waiting');
  if (!decision) return none(status('eq') === 'pass' ? 'held' : 'nothing');
  // A range set by hand keeps its end, so the next candle confirms it (or voids it) whatever it does:
  // there is no honest "Extends", and the tab would not show one. No shadow at that decision.
  if (decision === 'range' && pick.kind === 'manual') return none('manual');

  // Work in "down expansion" prices (a long idea), as the rules do; mirror at the end.
  const up = range.dir === 'up';
  const s = up ? -1 : 1;
  const lo = up ? -range.high : range.low;
  const hi = up ? -range.low : range.high;
  const eq = range.eq * s;
  const half = range.half * s;
  const csd = range.csd * s;
  const last = bars[cursor]!;
  const c0 = last.close * s;
  // Price already at or past the target (a CSD candle that closed through it): nothing honest to draw.
  if (c0 >= hi) return none('past-target');
  const u = unit(bars, cursor);
  const entry = now.entry === null ? c0 : now.entry * s;
  const stop = now.stop === null ? lo : now.stop * s;
  const fmt = (p: number) => (p * s).toLocaleString('en-US', { minimumFractionDigits: opts.decimals, maximumFractionDigits: opts.decimals });
  const through = up ? 'below' : 'above';
  const back = up ? 'above' : 'below';
  /** The nearest of `levels` strictly past `from`, or the target: where an A close must stay short of. */
  const next = (from: number, levels: readonly number[]) => Math.min(hi, ...levels.filter((l) => l > from));
  /** A close past `from` and short of `limit`: `want` past it, at most halfway. Null when there is no room. */
  const between = (from: number, limit: number, want: number) => (limit > from ? from + Math.min(want, (limit - from) / 2) : null);

  let a: Raw | null;
  let b: Raw;
  let question: string;
  let words: { a: [string, string]; b: [string, string] };
  let bTone: ShadowTone = 'bad';
  switch (decision) {
    case 'range': {
      // A stops the run: a small candle the other way, short of 50% of the last candle (and so of CSD,
      // EQ and the target). When the last candle already closed in its far half, any candle the other
      // way would be the 50% close: a doji instead, which ends the run without counting. B runs on.
      const close = half > c0 ? between(c0, next(c0, [half, csd, eq]), 0.35 * u) : null;
      a = close !== null ? candle(c0, close, u) : candle(c0, c0, u, 0.25, 0.25);
      b = candle(c0, c0 - 0.8 * u, u, 0.1, 0.15);
      question = 'Next candle after the expansion';
      words = {
        a: ['Stops', `If it stops closing ${up ? 'above' : 'below'} ${fmt(c0)}`],
        b: ['Extends', `If it closes ${up ? 'above' : 'below'} ${fmt(c0)} again`],
      };
      bTone = 'neutral';
      break;
    }
    case 'half': {
      // A closes past 50% (and past the last close: a candle the other way), short of CSD, EQ and the
      // target where they lie further on. B tags 50% and closes back under it.
      const from = Math.max(half, c0);
      const close = between(from, next(from, [csd, eq]), 0.3 * u);
      a = close === null ? null : candle(c0, close, u);
      if (a && eq <= from && c0 >= eq) a.low = Math.max(a.low, eq); // already past EQ: do not trade back through it
      const bClose = below(Math.min(c0, half), lo, 0.35 * u);
      b = { open: c0, close: bClose, high: Math.max(c0, half), low: bClose - 0.1 * u };
      question = `Next candle at 50% (${fmt(half)})`;
      words = { a: [`${cap(through)} 50%`, `If it closes ${through} 50%`], b: ['Rejects 50%', 'If it rejects 50%'] };
      break;
    }
    case 'csd': {
      // A closes past CSD, short of EQ and the target where they lie further on. When CSD sits past EQ
      // (after a gap) and price is already past EQ, its wick stays on that side of EQ; when price is still
      // short of EQ, any close past CSD crosses it and the rules rightly count the EQ close too.
      const from = Math.max(csd, c0);
      const close = between(from, next(from, [eq]), 0.3 * u);
      a = close === null ? null : candle(c0, close, u);
      if (a && eq <= csd && c0 >= eq) a.low = Math.max(a.low, eq);
      const bClose = below(Math.min(half, csd), lo, 0.25 * u);
      b = { open: c0, close: bClose, high: Math.max(c0, bClose, Math.min(csd, c0 + 0.3 * u)), low: Math.min(c0, bClose) - 0.1 * u };
      question = `Next candle at CSD (${fmt(csd)})`;
      words = { a: [`${cap(through)} CSD`, `If it closes ${through} CSD (${fmt(csd)})`], b: ['Fails CSD', 'If it fails at CSD'] };
      break;
    }
    case 'entry': {
      // A trades back past the CSD close (the fill), never as far as the stop, and does not earn the EQ
      // hold: past EQ already, its wick stays on that side of EQ; short of EQ, it closes short of it.
      const floor = eq < entry ? Math.max(stop, eq) : stop;
      const close = eq === entry ? entry : between(entry, next(entry, [eq]), 0.25 * u);
      a = close === null ? null : { open: c0, close, high: Math.max(c0, close) + 0.1 * u, low: below(entry, floor, 0.3 * u) };
      // B may run past EQ on its way (only the target bounds it): price leaving without you, past EQ, is
      // a fair picture of what goes wrong here, and the verdict for an unfilled entry ignores the hold.
      const runFrom = Math.max(c0, entry);
      const bClose = between(runFrom, hi, 0.7 * u) ?? runFrom;
      b = { open: c0, close: bClose, high: bClose + 0.1 * u, low: runFrom };
      question = 'Next candle after CSD';
      words = { a: ['Pulls back', `If it pulls back ${up ? 'above' : 'below'} ${fmt(entry)}`], b: ['Runs', 'If it runs without a pullback'] };
      break;
    }
    case 'eq':
    default: {
      // A trades through EQ and closes past it, short of the target (a gap past EQ does not count). B closes
      // back past CSD and stays short of EQ, whichever of the two is nearer (after a gap CSD can sit past EQ).
      const from = Math.max(eq, c0);
      const close = between(from, hi, 0.25 * u);
      a = close === null ? null : { open: c0, close, high: close + 0.1 * u, low: below(Math.min(c0, eq), stop, 0.1 * u) };
      const bClose = below(Math.min(csd, eq), lo, 0.3 * u);
      b = { open: c0, close: bClose, high: Math.max(c0, bClose) + 0.1 * u, low: Math.min(c0, bClose) - 0.1 * u };
      question = `Next candle at EQ (${fmt(eq)})`;
      words = { a: [`${cap(through)} EQ`, `If it closes ${through} EQ`], b: [`${cap(back)} CSD`, `If it closes back ${back} CSD`] };
      break;
    }
  }
  if (!a) return none('room'); // no room for an honest A: a level sits right on the next one

  // Every ghost's wicks stay inside the range: short of the untraded target, and never past the range's far
  // side (they may end on it, which is not a sweep), so an invented wick never trades the target or counts
  // as an OLR. The one ghost meant to run past the far side is "Extends".
  const inside = (c: Raw): Raw => {
    const top = Math.max(c.open, c.close);
    const bot = Math.min(c.open, c.close);
    const high = c.high >= hi && top < hi ? top + (hi - top) / 2 : c.high;
    const low = c.low <= lo ? (bot > lo ? lo + Math.min(0.05 * u, (bot - lo) / 2) : bot) : c.low;
    return { ...c, high, low };
  };
  a = inside(a);
  if (decision !== 'range') b = inside(b);

  const step = cursor > 0 ? last.t - bars[cursor - 1]!.t : 300;
  const t = last.t + step;
  const real = (c: Raw): Bar => ({ t, ...(up ? flip(c) : c) });
  let lost = false;
  const branch = (key: ShadowKey, raw: Raw, [short, title]: [string, string], tone: ShadowTone): ShadowBranch => {
    const ghost = real(raw);
    const ext = [...bars.slice(0, cursor + 1), ghost];
    // Read on the range the tab would pick once this candle printed, by its own `pick`.
    const r = pickRange(ext, cursor + 1, pick);
    if (!r) lost = true;
    return { key, short, title, candle: ghost, after: readRange(ext, r ?? range, cursor + 1, opts), tone };
  };
  const shadow: Shadow = { decision, now, question, a: branch('A', a, words.a, 'good'), b: branch('B', b, words.b, bTone) };
  if (lost) return none('switch');
  const verdict = honest(shadow);
  return verdict === true ? { shadow, off: null } : none(verdict);
}

/**
 * The last word before a shadow is shown: each branch does what its name says (A settles the decision,
 * B does not) and nothing it must not (void the range, trade the target, count as an OLR, sit on or past
 * the stop). Where a chart's levels leave no room for that, the shadow is off rather than wrong.
 */
function honest(sh: Shadow): true | 'switch' | 'room' {
  const check = (br: ShadowBranch, settles: boolean): true | 'switch' | 'room' => {
    const st = (k: StepKey) => stepOf(br.after, k);
    // never a different range: the tab must still show this one (only "Extends" grows its end)
    const r = br.after.range;
    if (r.start !== sh.now.range.start || r.dir !== sh.now.range.dir) return 'switch';
    if (r.end !== sh.now.range.end && !(sh.decision === 'range' && !settles)) return 'switch';
    if ((st(sh.decision) === 'pass') !== settles) return 'room';
    if (sh.decision === 'range' && !settles) return true; // "Extends" runs past the low on purpose
    if (br.after.voidAt !== null || st('target') === 'pass') return 'room';
    if (stepOf(sh.now, 'olr') !== 'pass' && st('olr') === 'pass') return 'room';
    const stop = br.after.stop;
    if (stop === null) return true;
    return (br.after.range.dir === 'down' ? br.candle.low > stop : br.candle.high < stop) || 'room';
  };
  const a = check(sh.a, true);
  return a !== true ? a : check(sh.b, false);
}

/**
 * The caption's consequence: what the rules would say with the ghost added. When that is
 * what they say already, it says so ("No change: still Watch, long. ...").
 */
export function consequence(shadow: Shadow, branch: ShadowBranch): string {
  const v = branch.after.verdict;
  const r = branch.after.range;
  const same = v.word === shadow.now.verdict.word && v.detail === shadow.now.verdict.detail && r.start === shadow.now.range.start && r.end === shadow.now.range.end;
  return same ? `No change: still ${v.word}. ${v.detail}` : `${v.word}. ${v.detail}`;
}

/** The hover text: the question, the branch, its consequence, and what a ghost is. */
export function shadowTitle(shadow: Shadow, branch: ShadowBranch): string {
  return `${shadow.question}. ${branch.key}: ${branch.title}: ${consequence(shadow, branch)} The ghost candle is an illustration, not a forecast; its size is invented.`;
}

function cap(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1);
}
