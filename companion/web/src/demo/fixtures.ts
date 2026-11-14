// SAMPLE DATA for demo mode only. Every price, rule and sentence here is invented
// to exercise the screen; none of it is market data or a real verdict.
import type {
  Candle,
  ChartView,
  CheckGroup,
  CheckRow,
  Journal,
  JournalTrigger,
  Mark,
  Options,
  Plan,
  Read,
  ServerState,
  Side,
  SnapshotFrame,
  Status,
  Step,
  Tool,
  VerdictView,
} from '../wire';
import { barTimes, pin, walk, wall } from './seeded';

export const SAMPLE_SOURCE_NOTE = 'Sample data, demo mode. Bars are generated, not read from TradingView.';

export const demoOptions: Options = {
  symbols: ['NQ1!', 'ES1!', 'YM1!', 'GC1!'],
  stacks: ['1D / 1h / 5m', '1D / 4h / 15m', '4h / 15m / 1m', '1W / 4h / 15m'],
  timeframes: ['1W', '1D', '4h', '1h', '15m', '5m', '1m'],
  styles: ['TTrades', 'Breakout', 'Mean reversion'],
  data: ['TradingView Desktop', 'Saved history'],
  sides: ['', 'long', 'short'],
  side_labels: { '': 'Auto', long: 'Long', short: 'Short' },
  stack_notes: {
    '1D / 1h / 5m': 'Backtest 2024-26: flat after costs.',
    '1W / 4h / 15m': 'Not validated: flat to slightly negative in the backtest.',
    '4h / 15m / 1m': 'Not validated: 1-minute entries were only backtested on incomplete data.',
  },
};

export const LATEST_WHEN = '2026-11-12T10:35:00-05:00';

export const demoState: ServerState = {
  symbol: 'NQ1!',
  stack: '1D / 1h / 5m',
  style: 'TTrades',
  data: 'TradingView Desktop',
  when: LATEST_WHEN,
  follow: true,
  auto_refresh: true,
  busy: false,
  live: true,
  side: '',
};

export const liveStatus: Status = { state: 'live', text: 'Sample data · demo mode', stale: false };

const LAST = 25455.25;

// ---------- candles ----------

function clampLows(candles: Candle[], from: number, to: number, floor: number): void {
  for (let i = from; i <= to; i++) {
    const c = candles[i];
    if (c && c.low < floor) pin(candles, i, { low: floor, open: Math.max(c.open, floor), close: Math.max(c.close, floor) });
  }
}

function setupCandles(): Candle[] {
  const times = barTimes(wall(2026, 11, 12, 10), 60, 60);
  const c = walk({
    seed: 11,
    times,
    noise: 22,
    forming: true,
    waypoints: [
      { at: 0, price: 25285 },
      { at: 14, price: 25525 },
      { at: 26, price: 25430 },
      { at: 38, price: 25500 },
      { at: 53, price: 25425 },
      { at: 59, price: 25450 },
    ],
  });
  pin(c, 14, { high: 25540 });
  pin(c, 26, { low: 25412.5 });
  clampLows(c, 27, 52, 25414);
  pin(c, 53, { low: 25398.75, close: 25431 });
  clampLows(c, 54, 59, 25420);
  pin(c, 59, { close: LAST });
  return c;
}

function biasCandles(): Candle[] {
  const times = barTimes(wall(2026, 11, 12), 1440, 30);
  const c = walk({
    seed: 7,
    times,
    noise: 55,
    forming: true,
    waypoints: [
      { at: 0, price: 24790 },
      { at: 10, price: 24990 },
      { at: 16, price: 24930 },
      { at: 24, price: 25230 },
      { at: 27, price: 25330 },
      { at: 29, price: 25440 },
    ],
  });
  pin(c, 27, { high: 25371 });
  pin(c, 28, { close: 25431 });
  pin(c, 29, { close: LAST });
  return c;
}

function entryCandles(): Candle[] {
  const times = barTimes(wall(2026, 11, 12, 10, 35), 5, 54);
  const c = walk({
    seed: 23,
    times,
    noise: 7,
    forming: true,
    waypoints: [
      { at: 0, price: 25462 },
      { at: 19, price: 25418 },
      { at: 20, price: 25402 },
      { at: 34, price: 25458 },
      { at: 53, price: 25452 },
    ],
  });
  pin(c, 20, { low: 25398.75, close: 25409 });
  clampLows(c, 21, c.length - 1, 25404);
  pin(c, c.length - 1, { close: LAST });
  return c;
}

// ---------- marks ----------

export const level = (role: string, label: string, price: number, start: number | null, title = label): Mark => ({
  kind: 'level',
  role,
  label,
  title,
  price,
  top: null,
  bottom: null,
  start,
  end: null,
});

const zone = (role: string, label: string, top: number, bottom: number, start: number | null, end: number | null = null): Mark => ({
  kind: 'zone',
  role,
  label,
  title: label,
  price: null,
  top,
  bottom,
  start,
  end,
});

const marker = (role: string, label: string, start: number, price: number | null = null): Mark => ({
  kind: 'marker',
  role,
  label,
  title: label,
  price,
  top: null,
  bottom: null,
  start,
  end: null,
});

/** A numbered bias candle, titled as the core titles it ("Bias Candle 2", short "C2"). */
export const biasCandle = (n: number, start: number, price: number, role = 'reference'): Mark => ({ ...marker(role, `C${n}`, start, price), title: `Bias Candle ${n}` });

// ---------- checklist ----------

export const row = (key: string, status: CheckRow['status'], label: string, detail: string, tag: string, advisory = false): CheckRow => ({
  key,
  status,
  mark: status === 'pass' ? 'ok' : status === 'fail' ? 'x' : '...',
  label,
  detail,
  tags: [tag],
  advisory,
});

export function group(name: string, title: string, path: string, rows: CheckRow[], extra: Partial<CheckGroup> = {}): CheckGroup {
  const counted = rows.filter((r) => !r.advisory);
  const passed = counted.filter((r) => r.status === 'pass').length;
  const failed = counted.filter((r) => r.status === 'fail').length;
  const not_evaluated = counted.filter((r) => r.status === 'na').length;
  return {
    name,
    title,
    path,
    active: true,
    collapsed: false,
    passed,
    failed,
    not_evaluated,
    tally: `${passed} of ${counted.length}`,
    rows,
    ...extra,
  };
}

function groups(entryConfirmed: boolean): CheckGroup[] {
  return [
    group('bias', 'Bias', '1D', [
      row('bias.directional', 'pass', 'Higher timeframe is directional', 'Three daily closes above the 25,110.00 swing.', 'gate'),
      row('bias.c2', 'pass', 'Candle 2 closed beyond candle 1', 'Closed at 25,431.00, above the prior high at 25,371.00.', 'step'),
      row('bias.upper_half', 'pass', 'Closed in the upper half of its range', "Close sits at 84% of the day's range.", 'quality'),
      row('bias.protected', 'pass', 'Protected low is intact', 'Nothing has closed below 25,240.00.', 'gate'),
    ]),
    group('setup', 'Setup', '1h', [
      row('setup.poi', 'pass', 'Price reached a point of interest', 'Traded into the 1h low at 25,412.50.', 'gate'),
      row('setup.liquidity', 'pass', 'Liquidity taken', 'Swept 25,412.50 and reached 25,398.75.', 'step'),
      row('setup.inside', 'pass', 'Closed back inside', 'The sweeping bar closed at 25,431.00.', 'step'),
      row('setup.room', 'pass', 'Room to the target', '71.75 pts from entry to 25,540.00.', 'quality'),
    ]),
    group('entry', 'Entry', '5m', [
      row('entry.sweep', 'pass', 'Sweep seen on the entry timeframe', '5m low at 25,398.75 at 07:50.', 'step'),
      entryConfirmed
        ? row('entry.cisd', 'pass', 'Change in state of delivery', 'The 10:30 bar closed at 25,471.50, above 25,468.25.', 'gate')
        : row('entry.cisd', 'na', 'Change in state of delivery', 'Needs a 5m close above 25,468.25. Last close 25,455.25.', 'gate'),
      entryConfirmed
        ? row('entry.trigger', 'pass', 'Entry trigger', 'Triggered at 25,468.25 on the 10:30 close.', 'step')
        : row('entry.trigger', 'na', 'Entry trigger', 'Arms when delivery changes.', 'step'),
    ]),
    group('quality', 'Quality', 'All', [
      row('quality.rr', 'pass', 'Reward covers the risk', '1.03R to target 1, 2.08R to target 2.', 'quality'),
      row('quality.stop', 'pass', 'Stop sits beyond the sweep', 'Stop at 25,398.75, 69.50 pts from entry.', 'quality'),
      row('quality.session', 'fail', 'Inside the session window', '10:35 is past the 09:30 to 10:30 window.', 'quality'),
      row('quality.volume', 'pass', 'Volume above the 20-bar average', 'The sweeping bar traded 1.4 times the average.', 'quality', true),
      row('quality.news', 'na', 'No scheduled news in the next hour', 'Calendar not loaded in demo mode.', 'quality', true),
    ]),
  ];
}

// ---------- views ----------

export function chart(role: string, timeframe: string, minutes: number, candles: Candle[], read: Read, marks: Mark[], tool: Tool | null = null): ChartView {
  const last = candles[candles.length - 1]!;
  return {
    role,
    timeframe,
    status: read.status,
    word: read.word,
    headline: read.headline,
    as_of: last.time,
    minutes,
    candles,
    marks,
    tool,
  };
}

// ---------- the plan, its tool and the steps (sample) ----------

const ENTRY = 25468.25;
const STOP = 25398.75;
const TARGET = 25612.5;

function longTool(planned: boolean, start: number): Tool {
  const caption = planned ? 'PLANNED  ' : '';
  const entryNames = planned ? ['Planned long entry', 'Planned entry', 'Entry'] : ['Long entry', 'Entry'];
  return {
    direction: 'long',
    planned,
    entry: ENTRY,
    stop: STOP,
    target: TARGET,
    r_multiple: 2.08,
    start,
    outcome: 'open',
    outcome_at: null,
    entry_note: planned ? 'Next: 5m close above' : '',
    box: true,
    named: true,
    risk_zone: { top: ENTRY, bottom: STOP },
    reward_zone: { top: TARGET, bottom: ENTRY },
    risk_points: 69.5,
    reward_points: 144.25,
    lines: [
      { role: 'entry', price: ENTRY, names: entryNames, names_worded: entryNames },
      { role: 'stop', price: STOP, names: ['Stop  \u221269.50', 'Stop'], names_worded: ['Stop \u00b7 risk  \u221269.50', 'Stop \u00b7 risk', 'Stop'] },
      {
        role: 'target',
        price: TARGET,
        names: ['Target 2.08R  +144.25', 'Target 2.08R', 'Target'],
        names_worded: ['Target \u00b7 reward 2.08R  +144.25', 'Target \u00b7 reward 2.08R', 'Target \u00b7 reward', 'Target'],
      },
    ],
    captions: { reward: `${caption}REWARD  2.08R`, risk: `${caption}RISK  1R` },
  };
}

function longPlan(planned: boolean, since: string, last: number): Plan {
  return {
    direction: 'long',
    state: planned ? 'planned' : 'triggered',
    outcome: 'open',
    title: planned ? 'PLANNED LONG' : 'LONG',
    levels: [
      { name: 'Entry', price: '25,468.25', note: planned ? 'trigger level' : '' },
      { name: 'Stop', price: '25,398.75', note: 'risk 69.50' },
      { name: 'Target', price: '25,612.50', note: '2.08R  \u00b7  144.25' },
    ],
    note: planned
      ? 'Planned, not triggered: the entry shown is the level a 5m close has to clear. Stop: the swept low 25,398.75. Entry, stop and target move if price makes a new low first.'
      : 'Entry is the close of the 5m candle at 10:30. Stop: the swept low 25,398.75.',
    entry: ENTRY,
    stop: STOP,
    target: TARGET,
    r_multiple: 2.08,
    timeframe: '5m',
    since,
    outcome_at: null,
    last,
    r_now: planned ? null : (last - ENTRY) / (ENTRY - STOP),
    stage_label: planned ? 'forming' : 'actionable',
    age_bars: planned ? null : 1,
    risk_adr: 0.17,
    cost_r_mini: 0.007,
    cost_r_micro: 0.014,
    cost_note: 'Stop 17% of ADR · costs 0.01R mini, 0.01R micro',
  };
}

export const step = (number: number, status: Step['status'], timeframe: string, label: string, detail: string, price: number | null = null, level_label = ''): Step => ({
  number,
  status,
  word: status.charAt(0).toUpperCase() + status.slice(1),
  timeframe,
  label,
  detail,
  price,
  level_label,
});

function longSteps(triggered: boolean): Step[] {
  return [
    step(1, 'done', '1D', '1D bias is bullish', 'Candle 2 closed at 25,431.00, above the prior high 25,371.00'),
    step(2, 'done', '1h', '1h sweeps a low and closes back inside', 'Took 25,412.50, reached 25,398.75 and closed at 25,431.00'),
    triggered
      ? step(3, 'done', '5m', '5m closes above the level: the entry', '10:30 close 25,471.50, above 25,468.25')
      : step(3, 'next', '5m', '5m closes above the level: the entry', '5m close above 25,468.25, after the low 25,398.75', ENTRY, '5m close above'),
    triggered ? step(4, 'done', '1h', '1h holds above the swept low', 'No 1h close below 25,398.75 since the sweep') : step(4, 'later', '1h', '1h holds above the swept low', ''),
  ];
}

const biasRead: Read = {
  role: 'bias',
  timeframe: '1D',
  status: 'confirmed',
  word: 'Confirmed',
  headline: 'Bullish, candle 2 closed',
  reason: 'Closed above the prior high at 25,371.00.',
};

const setupRead: Read = {
  role: 'setup',
  timeframe: '1h',
  status: 'confirmed',
  word: 'Confirmed',
  headline: 'Low swept, closed back inside',
  reason: 'Took 25,412.50, reached 25,398.75, closed at 25,431.00.',
};

export function watchView(): VerdictView {
  const entryRead: Read = {
    role: 'entry',
    timeframe: '5m',
    status: 'waiting',
    word: 'Waiting',
    headline: 'No change in delivery yet',
    reason: 'Needs a close above 25,468.25.',
  };
  const setup = setupCandles();
  const bias = biasCandles();
  const entry = entryCandles();
  return {
    decision: 'watch',
    decision_word: 'WATCH',
    tone: 'watch',
    headline: 'Watch, entry not confirmed',
    bias: 'BULLISH',
    path: 'CONTINUATION',
    stage: 'C3',
    levels: [
      { name: 'Entry', price: '25,468.25', note: 'on a 5m close' },
      { name: 'Stop', price: '25,398.75', note: '69.50 pts risk' },
      { name: 'Target 1', price: '25,540.00', note: '1.03R' },
      { name: 'Target 2', price: '25,612.50', note: '2.08R' },
    ],
    has_levels: true,
    invalidation: 'A 1h close below 25,398.75 ends the long idea. A daily close below 25,240.00 flips the bias to neutral.',
    summary: 'Bias and setup agree. The entry is armed but has not triggered.',
    groups: groups(false),
    hidden_advisory: 2,
    notes: ['Gates must pass before a step counts.'],
    read: [biasRead, setupRead, entryRead],
    why: 'Daily is bullish. The 1h took the low at 25,412.50 and closed back above it.',
    waiting_for: 'A 5m close above 25,468.25',
    direction: 'long',
    requested: '',
    idea: 'long',
    suggestion: 'WATCH \u00b7 LONG',
    suggestion_tone: 'watch',
    idea_state: 'Planned long, not triggered: the levels are a projection and move with a new low.',
    idea_alert: false,
    auto_note: '',
    steps: longSteps(false),
    plan: longPlan(true, entry.at(-1)!.time, 25455.25),
    look_for: null,
    journal: demoJournal(null),
    charts: [
      chart('setup', '1h', 60, setup, setupRead, [
        level('target', 'Target 1', 25540, 14),
        level('target', 'Target 2', 25612.5, 14),
        level('waiting', 'Close above to confirm', 25468.25, 44),
        level('reference', 'Swept low', 25412.5, 26),
        zone('poi', 'Sweep zone', 25412.5, 25398.75, 53),
        level('stop', 'Stop', 25398.75, 53),
      ]),
      chart('bias', '1D', 1440, bias, biasRead, [
        level('confirm', 'Prior high', 25371, 27),
        biasCandle(1, 27, 25371),
        biasCandle(2, 28, 25431, 'confirm'),
      ]),
      chart('entry', '5m', 5, entry, entryRead, [marker('protected', 'Swept low', 20, 25398.75)], longTool(true, entry.length - 1)),
    ],
    chart_problem: '',
    source_note: SAMPLE_SOURCE_NOTE,
    last: { name: 'Last', price: '25,455.25', note: '5m' },
  };
}

export function longView(): VerdictView {
  const base = watchView();
  const entryRead: Read = {
    role: 'entry',
    timeframe: '5m',
    status: 'confirmed',
    word: 'Confirmed',
    headline: 'Delivery changed, closed above 25,468.25',
    reason: 'The 10:30 bar closed at 25,471.50.',
  };
  const entry = entryCandles();
  pin(entry, entry.length - 2, { close: 25471.5 });
  pin(entry, entry.length - 1, { close: 25474 });
  const setup = setupCandles();
  pin(setup, setup.length - 1, { close: 25474, high: 25476.25 });
  const bias = biasCandles();
  pin(bias, bias.length - 1, { close: 25474, high: 25476.25 });
  return {
    ...base,
    decision: 'long',
    decision_word: 'TRADE LONG',
    tone: 'long',
    headline: 'Trade long, entry confirmed',
    suggestion: 'TRADE LONG',
    suggestion_tone: 'long',
    idea_state: 'Triggered 10:30 \u00b7 open \u00b7 last close +0.08R from the entry.',
    steps: longSteps(true),
    plan: longPlan(false, entry.at(-2)!.time, 25474),
    journal: demoJournal(demoTrigger(entry.at(-2)!.time)),
    stage: 'C4',
    why: 'Daily is bullish, the 1h swept its low and the 5m has now closed above 25,468.25.',
    waiting_for: '',
    summary: 'Every gate passed. One quality check failed: the session window has closed.',
    groups: groups(true),
    read: [biasRead, setupRead, entryRead],
    levels: [
      { name: 'Entry', price: '25,468.25', note: 'on the 10:30 close' },
      { name: 'Stop', price: '25,398.75', note: '69.50 pts risk' },
      { name: 'Target 1', price: '25,540.00', note: '1.03R' },
      { name: 'Target 2', price: '25,612.50', note: '2.08R' },
    ],
    charts: [
      chart('setup', '1h', 60, setup, setupRead, [
        level('target', 'Target 1', 25540, 14),
        level('target', 'Target 2', 25612.5, 14),
        level('entry', 'Entry', 25468.25, 44),
        zone('poi', 'Sweep zone', 25412.5, 25398.75, 53),
        level('stop', 'Stop', 25398.75, 53),
      ]),
      chart('bias', '1D', 1440, bias, biasRead, [
        level('confirm', 'Prior high', 25371, 27),
        biasCandle(1, 27, 25371),
        biasCandle(2, 28, 25431, 'confirm'),
      ]),
      chart('entry', '5m', 5, entry, entryRead, [
        level('target', 'Target 1', 25540, 34),
        zone('confirm', 'Delivery change', 25471.5, 25458, 34, entry.length - 2),
        marker('confirm', 'Trigger', entry.length - 2, 25471.5),
      ], longTool(false, entry.length - 2)),
    ],
    last: { name: 'Last', price: '25,474.00', note: '5m' },
  };
}

/**
 * The sample read with a side forced, as the core answers `set {side}`: Long reads
 * as Auto does; Short has no setup on a bullish bias, so its first step is blocked.
 */
export function sideView(view: VerdictView, side: Side): VerdictView {
  if (side === '') return view;
  const auto = `Auto reads ${view.suggestion.replace(/\s*\u00b7\s*/g, ' ').toLowerCase()}.`;
  if (side === 'long') return { ...view, requested: 'long', auto_note: auto };
  const watch = watchView();
  return {
    ...view,
    decision: 'no_trade',
    decision_word: "DON'T TRADE",
    tone: 'no_trade',
    requested: 'short',
    idea: 'short',
    suggestion: 'NO SHORT SETUP',
    suggestion_tone: 'no_trade',
    idea_state: 'Nothing to plan on the short side while the 1D bias is bullish.',
    idea_alert: true,
    auto_note: auto,
    direction: '',
    has_levels: false,
    levels: [],
    waiting_for: '',
    plan: null,
    look_for: null,
    journal: view.journal ? { ...view.journal, trigger: null } : null,
    steps: [
      step(1, 'blocked', '1D', '1D bias is bearish', 'The 1D bias is bullish: candle 2 closed above the prior high 25,371.00, so a short has nothing to follow'),
      step(2, 'later', '1h', '1h pulls back to a point of interest', ''),
      step(3, 'later', '5m', '5m turns down: the entry', ''),
    ],
    charts: watch.charts.map((c) => (c.role === 'entry' ? { ...c, tool: null } : c)),
  };
}

/** A sample journal for `stack`: invented counts, under 20 closed so the panel says they mean nothing yet. */
export function demoJournal(trigger: JournalTrigger | null, stack = '1D / 1h / 5m'): Journal {
  return {
    stack,
    note: demoOptions.stack_notes[stack] ?? '',
    trigger,
    reasons: [
      { key: 'late', label: 'Late' },
      { key: 'no_confluence', label: 'No confluence' },
      { key: 'news', label: 'News' },
      { key: 'risk_too_big', label: 'Risk too big' },
      { key: 'other', label: 'Other' },
    ],
    stats: {
      taken: { n: 6, avg_r: 0.42 },
      skipped: { n: 9, avg_r: -0.11 },
      all: { n: 23, avg_r: 0.04 },
      open: 2,
      min_n: 20,
    },
  };
}

export function demoTrigger(since: string): JournalTrigger {
  return { key: `NQ1!|1D/1h/5m|TTrades|long|${since}`, side: 'long', since, mark: '', reason: '', note: '', outcome: 'open', result_r: null };
}

export function chartProblemView(): VerdictView {
  return {
    ...watchView(),
    charts: [],
    chart_problem: 'The 5m chart returned 12 closed bars, fewer than the 40 the style needs. Charts are hidden until TradingView sends more history.',
  };
}

// ---------- frames ----------

export function snapshot(seq: number, view: VerdictView | null, extra: Partial<Omit<SnapshotFrame, 'type' | 'seq' | 'view'>> = {}): SnapshotFrame {
  return {
    type: 'snapshot',
    seq,
    view,
    error: '',
    offer_history: false,
    status: liveStatus,
    timing: {
      bar_closed_at: '2026-11-12T10:35:00-05:00',
      detected_at: '2026-11-12T10:35:01-05:00',
      fetch_ms: 184,
      compute_ms: 12,
      lag_ms: 1196,
      load_ms: 3,
    },
    ...extra,
  };
}

export const errorStaleExtra = {
  view: null,
  error: 'TradingView Desktop stopped answering at 10:36. The read below is from the 10:35 check.',
  offer_history: true,
  status: { state: 'stale', text: 'No new bars for 2 min · last good 10:35', stale: true } satisfies Status,
  timing: null,
} as const;

