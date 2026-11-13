// Wire contract, version 1. The Python core implements exactly these frames; the
// authoritative description is the docstring of companion/core/wire.py.
// Every incoming frame goes through parseServerFrame; a malformed frame is
// logged and dropped there and never reaches the reducer or render.
// Fields added within version 1 (the side, the suggestion, steps, plan, tool,
// load_ms) are read with a fallback, so a frame from an older core still parses.

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
}

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
  | { type: 'pause'; paused: boolean }
  | { type: 'use_history' };

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
});

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
