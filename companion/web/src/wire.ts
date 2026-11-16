// Wire contract, version 1. The Python core implements exactly these frames; the
// authoritative description is the docstring of companion/core/wire.py.
// Every incoming frame goes through parseServerFrame; a malformed frame is
// logged and dropped there and never reaches the reducer or render.
// Fields added within version 1 (the side, the suggestion, steps, plan, tool,
// load_ms, look_for) are read with a fallback, so a frame from an older core still parses.
// look_for is display only: a malformed one is logged and read as null, the frame kept.
// journal (the decision journal, live only) is read the same lenient way.

export const WIRE_VERSION = 1;

// ---------- shared shapes ----------

export interface Candle {
  time: string; // ISO-8601 with New York offset
  t: number; // New York wall-clock open time expressed as if UTC, epoch seconds
  open: number;
  high: number;
  low: number;
  close: number;
  forming: boolean;
  label: string;
}

/** The bias selector's values: "" is Auto (the style proposes the idea). */
export type Side = '' | 'long' | 'short';

export interface Options {
  symbols: string[];
  stacks: string[];
  timeframes: string[];
  styles: string[];
  data: string[];
  /** Values of `ServerState.side`. Auto, Long, Short from a core that predates the side. */
  sides: Side[];
  side_labels: Record<string, string>;
  /** What the backtest found for a stack, by stack name; a stack may have none. */
  stack_notes: Record<string, string>;
}

export interface ServerState {
  symbol: string;
  stack: string;
  style: string;
  data: string;
  when: string;
  follow: boolean;
  auto_refresh: boolean;
  busy: boolean;
  live: boolean;
  side: Side;
}

export type StatusState = 'history' | 'connecting' | 'live' | 'stale' | 'paused' | 'past' | 'offline';

export interface Status {
  state: StatusState;
  text: string;
  stale: boolean;
}

export interface Timing {
  bar_closed_at: string | null;
  detected_at: string;
  fetch_ms: number;
  compute_ms: number;
  lag_ms: number | null;
  /** Loading bars the source did not hold yet. null from a core that predates it. */
  load_ms: number | null;
}

export type Decision = 'long' | 'short' | 'watch' | 'no_trade';
export type Tone = 'long' | 'short' | 'watch' | 'no_trade' | 'neutral';
export type ReadStatus = 'confirmed' | 'waiting' | 'failed' | 'not_applicable';
export type RowStatus = 'pass' | 'fail' | 'na';
export type Direction = '' | 'long' | 'short';

export interface Level {
  name: string;
  price: string; // already formatted
  note: string;
}

export interface CheckRow {
  key: string;
  status: RowStatus;
  mark: string;
  label: string;
  detail: string;
  tags: string[]; // normalised: the contract leaves the type open; a string or string[] is accepted and split on " · "
  advisory: boolean;
}

export interface CheckGroup {
  name: string;
  title: string;
  path: string;
  active: boolean;
  collapsed: boolean;
  passed: number;
  failed: number;
  not_evaluated: number;
  tally: string;
  rows: CheckRow[];
}

export interface Read {
  role: 'bias' | 'setup' | 'entry';
  timeframe: string;
  status: ReadStatus;
  word: string;
  headline: string;
  reason: string;
}

export type MarkKind = 'level' | 'zone' | 'marker';

export interface Mark {
  kind: MarkKind;
  role: string;
  label: string;
  title: string;
  price: number | null;
  top: number | null;
  bottom: number | null;
  start: number | null; // candle index; null = began before the candles shown
  end: number | null; // candle index; null = runs to the right edge
}

export type StepStatus = 'done' | 'next' | 'later' | 'blocked';

export interface Step {
  number: number;
  status: StepStatus;
  word: string;
  timeframe: string;
  label: string;
  /** next: the exact condition with its price; done: what was seen; blocked: why. May be "". */
  detail: string;
  price: number | null;
  /** The condition's words without the price, as the chart names its line. */
  level_label: string;
}

export type TradeSide = 'long' | 'short';
export type Outcome = 'open' | 'target_reached' | 'stopped';

export interface Plan {
  direction: TradeSide;
  state: 'planned' | 'triggered';
  outcome: Outcome;
  title: string;
  levels: Level[];
  note: string;
  entry: number;
  stop: number;
  target: number;
  r_multiple: number;
  timeframe: string;
  since: string | null;
  outcome_at: string | null;
  last: number | null;
  r_now: number | null;
  /** Where the idea stands: forming | actionable | late | played_out ('' when the core did not say). */
  stage_label: StageLabel;
  /** Triggered: closed entry bars after the trigger bar. */
  age_bars: number | null;
  /** The stop as a share of the 14-day average daily range. */
  risk_adr: number | null;
  /** One contract's round-turn cost (a tick of slippage plus commission) as a share of the risk. */
  cost_r_mini: number | null;
  cost_r_micro: number | null;
  /** Those in words: "Stop 6% of ADR · costs 0.05R mini, 0.11R micro" ('' when unknown). */
  cost_note: string;
  /** What one contract loses at the stop: "1 micro risks $96 · 1 mini $960" ('' when unknown). */
  size_note: string;
  /** What the backtest measured for this setup, while the outcome is open (information only). */
  evidence: Evidence | null;
}

export type EvidenceGrade = 'small_stop' | 'best_measured' | 'no_edge' | 'untested';

export interface Evidence {
  grade: EvidenceGrade;
  /** "Best-measured setup", "No edge measured", "Small stop", "Not backtested". */
  label: string;
  /** The record in one sentence. */
  line: string;
  /** How the exits compared on this stack ('' when not measured). */
  exits: string;
  /** Where the numbers come from. */
  source: string;
  /** The odds board for this trigger, or null when the evidence file has none. */
  odds: Odds | null;
}

export interface OddsRow {
  /** "1D / 1h / 5m", "Continuation, CISD", "NY AM". */
  label: string;
  n: number;
  /** Percent of trades that reached 2R before the stop. */
  win: number;
  /** Percent needed to break even at 2R after costs. */
  breakeven: number;
  /** Percent that reached 1R before the stop. */
  win_1r: number;
  /** Median time to the target / the stop: "4.6 h", "35 min" ('' when none). */
  to_target: string;
  to_stop: string;
  /** "Many still open after 10 days" ('' when the win rate is honest). */
  note: string;
  /** This trigger's row. */
  current: boolean;
}

export interface Odds {
  /** "This setup wins 33% to 2R (breakeven 34%), target ~3 h, stop ~1.7 h, 666 trades". */
  line: string;
  stacks: OddsRow[];
  /** The setups (path and trigger) on this trigger's stack. */
  setups: OddsRow[];
  sessions: OddsRow[];
}

export type StageLabel = '' | 'forming' | 'actionable' | 'late' | 'played_out';

export interface Zone {
  top: number;
  bottom: number;
}

export type ToolRole = 'entry' | 'stop' | 'target';

export interface ToolLine {
  role: ToolRole;
  price: number;
  /** Fullest first, down to the bare role word. */
  names: string[];
  /** The names when this line's zone has no room for its caption. */
  names_worded: string[];
}

/** The plan as a risk / reward tool on the entry chart. */
export interface Tool {
  direction: TradeSide;
  planned: boolean;
  entry: number;
  stop: number;
  target: number;
  r_multiple: number;
  /** Candle index both zones begin at; they run to the right edge. */
  start: number;
  outcome: Outcome;
  outcome_at: number | null;
  /** "" or the next step's words when the level it waits on is this entry. */
  entry_note: string;
  box: boolean;
  named: boolean;
  risk_zone: Zone;
  reward_zone: Zone;
  risk_points: number;
  reward_points: number;
  lines: ToolLine[];
  captions: { reward: string; risk: string };
}

export interface LookStep {
  label: string;
  status: StepStatus;
}

/** A zone the setup may play out at: "A" the nearest point of interest, "B" the next one beyond it. */
export interface LookOption {
  key: string;
  name: string;
  top: number;
  bottom: number;
  /** "" for A; when B comes into play, e.g. "only after a 1h close above the POI". */
  condition: string;
}

/** What to look for while the setup is still ahead. Display only. */
export interface LookFor {
  direction: TradeSide;
  /** The timeframe to watch for the setup, e.g. "1h". */
  timeframe: string;
  entry_timeframe: string;
  steps: LookStep[];
  options: LookOption[];
  /** Words: "5m close below the run", "above the 1h C2 high", "2R, then PDL". */
  entry: string;
  stop: string;
  target: string;
  /** The structural level `target` names. */
  target_price: number | null;
  /** The entry forms while the setup's C2 forms; false: after it (the conservative entry). */
  entry_during: boolean;
  /** "continuation": the options are setup points of interest; "reversal": the bias key levels a reversal waits for. */
  kind: LookKind;
}

export type JournalMark = '' | 'took' | 'skipped';

/** The trigger on screen, as the decision journal logged it. */
export interface JournalTrigger {
  key: string;
  side: TradeSide;
  since: string | null;
  /** The trader's call: '' none yet. */
  mark: JournalMark;
  /** '' or a reason key from Journal.reasons. */
  reason: string;
  note: string;
  outcome: Outcome;
  /** +r_multiple at the target, -1 stopped; null while open. */
  result_r: number | null;
}

export interface JournalTally {
  n: number;
  /** Average R per closed trade, before costs; null when n is 0. */
  avg_r: number | null;
}

export interface JournalStats {
  taken: JournalTally;
  skipped: JournalTally;
  /** Every logged trigger: the engine's baseline. */
  all: JournalTally;
  open: number;
  /** Below this many closed trades an average means nothing yet. */
  min_n: number;
  /** Calls made after the trade had ended: kept, but out of the took / skipped rows. */
  late: number;
}

/** The decision journal for the view's stack. Display only: it never changes the decision. */
export interface Journal {
  stack: string;
  /** The stack's backtest note ('' when none). */
  note: string;
  trigger: JournalTrigger | null;
  reasons: { key: string; label: string }[];
  stats: JournalStats;
}

export type LookKind = 'continuation' | 'reversal';

export interface ChartView {
  role: string;
  timeframe: string;
  status: ReadStatus;
  word: string;
  headline: string;
  as_of: string;
  minutes: number;
  candles: Candle[];
  marks: Mark[];
  tool: Tool | null;
}

export interface VerdictView {
  decision: Decision;
  decision_word: string;
  tone: Tone;
  headline: string;
  bias: string;
  path: string;
  stage: string;
  levels: Level[];
  has_levels: boolean;
  invalidation: string;
  summary: string;
  groups: CheckGroup[];
  hidden_advisory: number;
  notes: string[];
  read: Read[];
  why: string;
  waiting_for: string;
  direction: Direction;
  charts: ChartView[];
  chart_problem: string;
  source_note: string;
  last: Level | null;
  // The suggestion, as the window's banner shows it. A core that predates these
  // sends none: the reader then fills the suggestion from decision_word and tone.
  requested: Direction;
  idea: Direction;
  suggestion: string;
  suggestion_tone: Tone;
  idea_state: string;
  idea_alert: boolean;
  auto_note: string;
  steps: Step[];
  plan: Plan | null;
  look_for: LookFor | null;
  /** Live only; null on saved history and from an older core. */
  journal: Journal | null;
}

// ---------- frames ----------

export interface HelloFrame {
  type: 'hello';
  version: number;
  options: Options;
  state: ServerState;
}
export interface StateFrame {
  type: 'state';
  state: ServerState;
}
export interface SnapshotFrame {
  type: 'snapshot';
  seq: number;
  view: VerdictView | null;
  error: string;
  offer_history: boolean;
  status: Status;
  timing: Timing | null;
}
export interface StatusFrame {
  type: 'status';
  status: Status;
}
export interface TickFrame {
  type: 'tick';
  timeframe: string;
  candle: Candle;
  last: number;
}
export interface ErrorFrame {
  type: 'error';
  message: string;
}

export type ServerFrame = HelloFrame | StateFrame | SnapshotFrame | StatusFrame | TickFrame | ErrorFrame;

export type ClientFrame =
  | { type: 'set'; symbol?: string; stack?: string; style?: string; data?: string; when?: string; side?: Side }
  | { type: 'check' }
  | { type: 'step'; direction: -1 | 1 }
  | { type: 'latest' }
  | { type: 'use_history' }
  | { type: 'journal'; key: string; mark: JournalMark; reason?: string; note?: string };

// ---------- validation ----------

export class FrameError extends Error {
  constructor(
    readonly path: string,
    message: string,
  ) {
    super(`${path}: ${message}`);
    this.name = 'FrameError';
  }
}

type Reader<T> = (value: unknown, path: string) => T;

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

const str: Reader<string> = (v, p) => {
  if (typeof v !== 'string') throw new FrameError(p, `expected string, got ${typeof v}`);
  return v;
};
const num: Reader<number> = (v, p) => {
  if (typeof v !== 'number' || !Number.isFinite(v)) throw new FrameError(p, 'expected finite number');
  return v;
};
const bool: Reader<boolean> = (v, p) => {
  if (typeof v !== 'boolean') throw new FrameError(p, 'expected boolean');
  return v;
};
const nullable =
  <T>(r: Reader<T>): Reader<T | null> =>
  (v, p) =>
    v === null ? null : r(v, p);
/** A field added within version 1: a frame from an older core may leave it out. */
const optional =
  <T>(r: Reader<T>, fallback: () => T): Reader<T> =>
  (v, p) =>
    v === undefined ? fallback() : r(v, p);
const arr =
  <T>(r: Reader<T>): Reader<T[]> =>
  (v, p) => {
    if (!Array.isArray(v)) throw new FrameError(p, 'expected array');
    return v.map((item, i) => r(item, `${p}[${i}]`));
  };
const record =
  <T>(r: Reader<T>): Reader<Record<string, T>> =>
  (v, p) => {
    if (!isRecord(v)) throw new FrameError(p, 'expected object');
    const out: Record<string, T> = {};
    for (const [k, item] of Object.entries(v)) out[k] = r(item, `${p}.${k}`);
    return out;
  };
const oneOf =
  <T extends string>(...allowed: readonly T[]): Reader<T> =>
  (v, p) => {
    if (typeof v !== 'string' || !(allowed as readonly string[]).includes(v)) {
      throw new FrameError(p, `expected one of ${allowed.map((a) => JSON.stringify(a)).join(', ')}`);
    }
    return v as T;
  };
// The core sends a row's tags as one string joined with " · " ("quality · 1h").
// Split it so each tag is its own chip and the Details filters can match "quality".
const splitTags = (s: string) =>
  s
    .split('·')
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
const tags: Reader<string[]> = (v, p) => {
  if (v === null || v === undefined || v === '') return [];
  if (typeof v === 'string') return splitTags(v);
  return arr(str)(v, p).flatMap(splitTags);
};

type Shape<T> = { [K in keyof T]: Reader<T[K]> };
const obj =
  <T>(shape: Shape<T>): Reader<T> =>
  (v, p) => {
    if (!isRecord(v)) throw new FrameError(p, 'expected object');
    const out = {} as T;
    for (const key of Object.keys(shape) as (keyof T & string)[]) {
      out[key] = shape[key](v[key], `${p}.${key}`);
    }
    return out;
  };

const candle = obj<Candle>({
  time: str,
  t: num,
  open: num,
  high: num,
  low: num,
  close: num,
  forming: bool,
  label: str,
});

const side = oneOf<Side>('', 'long', 'short');
export const DEFAULT_SIDES: readonly Side[] = ['', 'long', 'short'];
export const DEFAULT_SIDE_LABELS: Readonly<Record<Side, string>> = { '': 'Auto', long: 'Long', short: 'Short' };

const options = obj<Options>({
  symbols: arr(str),
  stacks: arr(str),
  timeframes: arr(str),
  styles: arr(str),
  data: arr(str),
  sides: optional(arr(side), () => [...DEFAULT_SIDES]),
  side_labels: optional(record(str), () => ({ ...DEFAULT_SIDE_LABELS })),
  stack_notes: optional(record(str), () => ({})),
});

const serverState = obj<ServerState>({
  symbol: str,
  stack: str,
  style: str,
  data: str,
  when: str,
  follow: bool,
  auto_refresh: bool,
  busy: bool,
  live: bool,
  side: optional(side, () => ''),
});

const status = obj<Status>({
  state: oneOf('history', 'connecting', 'live', 'stale', 'paused', 'past', 'offline'),
  text: str,
  stale: bool,
});

const timing = obj<Timing>({
  bar_closed_at: nullable(str),
  detected_at: str,
  fetch_ms: num,
  compute_ms: num,
  lag_ms: nullable(num),
  load_ms: optional(nullable(num), () => null),
});

const level = obj<Level>({ name: str, price: str, note: str });
const readStatus = oneOf<ReadStatus>('confirmed', 'waiting', 'failed', 'not_applicable');

const row = obj<CheckRow>({
  key: str,
  status: oneOf<RowStatus>('pass', 'fail', 'na'),
  mark: str,
  label: str,
  detail: str,
  tags,
  advisory: bool,
});

const group = obj<CheckGroup>({
  name: str,
  title: str,
  path: str,
  active: bool,
  collapsed: bool,
  passed: num,
  failed: num,
  not_evaluated: num,
  tally: str,
  rows: arr(row),
});

const read = obj<Read>({
  role: oneOf('bias', 'setup', 'entry'),
  timeframe: str,
  status: readStatus,
  word: str,
  headline: str,
  reason: str,
});

const mark = obj<Mark>({
  kind: oneOf<MarkKind>('level', 'zone', 'marker'),
  role: str,
  label: str,
  title: str,
  price: nullable(num),
  top: nullable(num),
  bottom: nullable(num),
  start: nullable(num),
  end: nullable(num),
});

const tradeSide = oneOf<TradeSide>('long', 'short');
const outcome = oneOf<Outcome>('open', 'target_reached', 'stopped');
const zone = obj<Zone>({ top: num, bottom: num });

const toolLineFields = obj<{ role: ToolRole; price: number; names: string[]; names_worded: string[] | null }>({
  role: oneOf<ToolRole>('entry', 'stop', 'target'),
  price: num,
  names: arr(str),
  names_worded: optional(arr(str), () => null),
});
const toolLine: Reader<ToolLine> = (v, p) => {
  const line = toolLineFields(v, p);
  if (line.names.length === 0) throw new FrameError(`${p}.names`, 'expected at least one name');
  const worded = line.names_worded && line.names_worded.length > 0 ? line.names_worded : line.names;
  return { role: line.role, price: line.price, names: line.names, names_worded: worded };
};

const tool = obj<Tool>({
  direction: tradeSide,
  planned: bool,
  entry: num,
  stop: num,
  target: num,
  r_multiple: num,
  start: num,
  outcome,
  outcome_at: nullable(num),
  entry_note: optional(str, () => ''),
  box: optional(bool, () => true),
  named: optional(bool, () => true),
  risk_zone: zone,
  reward_zone: zone,
  risk_points: num,
  reward_points: num,
  lines: arr(toolLine),
  captions: obj<Tool['captions']>({ reward: str, risk: str }),
});

const step = obj<Step>({
  number: num,
  status: oneOf<StepStatus>('done', 'next', 'later', 'blocked'),
  word: str,
  timeframe: str,
  label: str,
  detail: str,
  price: nullable(num),
  level_label: optional(str, () => ''),
});

const oddsRow = obj<OddsRow>({
  label: str,
  n: num,
  win: num,
  breakeven: num,
  win_1r: num,
  to_target: optional(str, () => ''),
  to_stop: optional(str, () => ''),
  note: optional(str, () => ''),
  current: optional(bool, () => false),
});

const odds = obj<Odds>({ line: str, stacks: arr(oddsRow), setups: arr(oddsRow), sessions: arr(oddsRow) });

const plan = obj<Plan>({
  direction: tradeSide,
  state: oneOf('planned', 'triggered'),
  outcome,
  title: str,
  levels: arr(level),
  note: str,
  entry: num,
  stop: num,
  target: num,
  r_multiple: num,
  timeframe: str,
  since: nullable(str),
  outcome_at: nullable(str),
  last: nullable(num),
  r_now: nullable(num),
  stage_label: optional(oneOf<StageLabel>('', 'forming', 'actionable', 'late', 'played_out'), () => '' as StageLabel),
  age_bars: optional(nullable(num), () => null),
  risk_adr: optional(nullable(num), () => null),
  cost_r_mini: optional(nullable(num), () => null),
  cost_r_micro: optional(nullable(num), () => null),
  cost_note: optional(str, () => ''),
  size_note: optional(str, () => ''),
  evidence: optional(
    nullable(
      obj<Evidence>({
        grade: oneOf<EvidenceGrade>('small_stop', 'best_measured', 'no_edge', 'untested'),
        label: str,
        line: str,
        exits: optional(str, () => ''),
        source: optional(str, () => ''),
        odds: optional(nullable(odds), () => null),
      }),
    ),
    () => null,
  ),
});

const lookFor = obj<LookFor>({
  direction: tradeSide,
  timeframe: str,
  entry_timeframe: str,
  steps: arr(obj<LookStep>({ label: str, status: oneOf<StepStatus>('done', 'next', 'later', 'blocked') })),
  options: arr(obj<LookOption>({ key: str, name: str, top: num, bottom: num, condition: optional(str, () => '') })),
  entry: str,
  stop: str,
  target: str,
  target_price: optional(nullable(num), () => null),
  entry_during: optional(bool, () => true),
  kind: optional(oneOf<LookKind>('continuation', 'reversal'), () => 'continuation'),
});

const tally = obj<JournalTally>({ n: num, avg_r: nullable(num) });

const journal = obj<Journal>({
  stack: str,
  note: optional(str, () => ''),
  trigger: nullable(
    obj<JournalTrigger>({
      key: str,
      side: tradeSide,
      since: nullable(str),
      mark: oneOf<JournalMark>('', 'took', 'skipped'),
      reason: optional(str, () => ''),
      note: optional(str, () => ''),
      outcome,
      result_r: nullable(num),
    }),
  ),
  reasons: optional(arr(obj<{ key: string; label: string }>({ key: str, label: str })), () => []),
  stats: obj<JournalStats>({ taken: tally, skipped: tally, all: tally, open: num, min_n: optional(num, () => 20), late: optional(num, () => 0) }),
});

/** A display-only field: when it does not parse, log it and read null; the frame is kept. */
const lenient =
  <T>(r: Reader<T>): Reader<T | null> =>
  (v, p) => {
    if (v === undefined || v === null) return null;
    try {
      return r(v, p);
    } catch (e) {
      if (!(e instanceof FrameError)) throw e;
      console.warn(`[wire] ignored ${e.message}`);
      return null;
    }
  };

const chartView = obj<ChartView>({
  role: str,
  timeframe: str,
  status: readStatus,
  word: str,
  headline: str,
  as_of: str,
  minutes: num,
  candles: arr(candle),
  marks: arr(mark),
  tool: optional(nullable(tool), () => null),
});

const tone = oneOf<Tone>('long', 'short', 'watch', 'no_trade', 'neutral');
const direction = oneOf<Direction>('', 'long', 'short');

const verdictFields = obj<VerdictView>({
  decision: oneOf<Decision>('long', 'short', 'watch', 'no_trade'),
  decision_word: str,
  tone,
  headline: str,
  bias: str,
  path: str,
  stage: str,
  levels: arr(level),
  has_levels: bool,
  invalidation: str,
  summary: str,
  groups: arr(group),
  hidden_advisory: num,
  notes: arr(str),
  read: arr(read),
  why: str,
  waiting_for: str,
  direction,
  charts: arr(chartView),
  chart_problem: str,
  source_note: str,
  last: nullable(level),
  requested: optional(direction, () => ''),
  idea: optional(direction, () => ''),
  suggestion: optional(str, () => ''),
  suggestion_tone: optional(tone, () => 'neutral'),
  idea_state: optional(str, () => ''),
  idea_alert: optional(bool, () => false),
  auto_note: optional(str, () => ''),
  steps: optional(arr(step), () => []),
  plan: optional(nullable(plan), () => null),
  look_for: lenient(lookFor),
  journal: lenient(journal),
});

/** An older core sends no suggestion: its decision is the suggestion then. */
const verdictView: Reader<VerdictView> = (v, p) => {
  const view = verdictFields(v, p);
  if (view.suggestion.trim() !== '') return view;
  return { ...view, suggestion: view.decision_word, suggestion_tone: view.tone };
};

const frameReaders: { [K in ServerFrame['type']]: Reader<Extract<ServerFrame, { type: K }>> } = {
  hello: obj<HelloFrame>({ type: oneOf('hello'), version: num, options, state: serverState }),
  state: obj<StateFrame>({ type: oneOf('state'), state: serverState }),
  snapshot: obj<SnapshotFrame>({
    type: oneOf('snapshot'),
    seq: num,
    view: nullable(verdictView),
    error: str,
    offer_history: bool,
    status,
    timing: nullable(timing),
  }),
  status: obj<StatusFrame>({ type: oneOf('status'), status }),
  tick: obj<TickFrame>({ type: oneOf('tick'), timeframe: str, candle, last: num }),
  error: obj<ErrorFrame>({ type: oneOf('error'), message: str }),
};

export type ParseResult = { ok: true; frame: ServerFrame } | { ok: false; reason: string };

/** Validate one JSON text frame. Never throws. */
export function validateFrame(raw: string): ParseResult {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return { ok: false, reason: 'not JSON' };
  }
  if (!isRecord(data) || typeof data.type !== 'string') return { ok: false, reason: 'missing "type"' };
  const reader = (frameReaders as Record<string, Reader<ServerFrame> | undefined>)[data.type];
  if (!reader) return { ok: false, reason: `unknown frame type ${JSON.stringify(data.type)}` };
  try {
    const frame = reader(data, data.type);
    if (frame.type === 'hello' && frame.version !== WIRE_VERSION) {
      return { ok: false, reason: `unsupported wire version ${frame.version}` };
    }
    return { ok: true, frame };
  } catch (err) {
    return { ok: false, reason: err instanceof Error ? err.message : String(err) };
  }
}

/** Validate and log-and-drop. Returns null for a malformed frame. */
export function parseServerFrame(raw: string, log: (msg: string) => void = console.warn): ServerFrame | null {
  const result = validateFrame(raw);
  if (result.ok) return result.frame;
  log(`[companion] dropped malformed frame: ${result.reason}`);
  return null;
}
