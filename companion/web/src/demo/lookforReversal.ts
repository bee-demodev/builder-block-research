// SAMPLE DATA for demo mode only (`?demo=look-for-reversal`). Every price here is invented.
//
// Thu 12 Nov 2026 10:15 New York, no trade on 1W / 4h / 15m: there is no continuation
// bias, and the forming week has not reached a key level. The nearer one is the previous
// week's high 27,480 (high so far 27,330, 150 away; the previous low 26,640 is 380 below
// the week's low 27,020), so the look-for is a short reversal there: option A is the
// band 27,400 to 27,480 the rules count as reaching it, option B the untaken 1W swing
// high 27,735 with its band. The last session's 4h candles are built from the 15m ones,
// and the last three weeks from their 4h candles, so the panes agree on time and price.
import type { Candle, LookFor, Read, Step, VerdictView } from '../wire';
import { SAMPLE_SOURCE_NOTE, chart, demoJournal, group, level, row, step } from './fixtures';
import { sessionOpens } from './lookfor';
import { barTimes, isoNY, pin, walk, wall } from './seeded';

export const LOOK_REVERSAL_WHEN = '2026-11-12T10:15:00-05:00';
export const LOOK_REVERSAL_STACK = '1W / 4h / 15m';

/** The story's prices, so the tests read the same numbers the candles were built to. */
export const STORY = {
  prevHigh: 27480,
  prevLow: 26640,
  weekLow: 27020,
  weekHigh: 27330,
  swingHigh: 27735,
  band: 80,
} as const;

function aggregate(bars: readonly Candle[], t: number, label: string, forming: boolean): Candle {
  return {
    time: isoNY(t),
    t,
    open: bars[0]!.open,
    high: Math.max(...bars.map((b) => b.high)),
    low: Math.min(...bars.map((b) => b.low)),
    close: bars[bars.length - 1]!.close,
    forming,
    label,
  };
}

/** Keep every candle from `from` to `to` inside [floor, cap], still a valid bar. */
function clamp(candles: Candle[], from: number, to: number, floor: number, cap: number): void {
  for (let i = from; i <= to; i++) {
    const c = candles[i];
    if (!c) continue;
    const fit = (p: number) => Math.min(cap, Math.max(floor, p));
    candles[i] = { ...c, open: fit(c.open), close: fit(c.close), high: fit(c.high), low: fit(c.low) };
  }
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/** A week is named by the Monday it trades into ("Nov 9" for the week opening Sunday 8 Nov 18:00). */
const weekLabel = (t: number) => {
  const d = new Date((t + 6 * 3600) * 1000);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
};

function entryCandles(): Candle[] {
  const times = barTimes(wall(2026, 11, 12, 10, 15), 15, 66); // Wed 18:00 to Thu 10:15
  const c = walk({
    seed: 41,
    times,
    noise: 22,
    forming: true,
    waypoints: [
      { at: 0, price: 27240 },
      { at: 26, price: 27180 },
      { at: 48, price: 27290 },
      { at: 58, price: 27315 },
      { at: 65, price: 27296 },
    ],
  });
  pin(c, 58, { high: STORY.weekHigh }); // the week's high so far, Thu 08:30
  clamp(c, 0, 65, 27150, STORY.weekHigh);
  return c;
}

function setupCandles(entry: readonly Candle[]): Candle[] {
  // three weeks of 4h sessions (Sun to Thu evenings), six candles each; the last session has five so far
  const opens = sessionOpens(wall(2026, 11, 11, 18), 14);
  const times = opens.flatMap((o, k) => [0, 4, 8, 12, 16, 20].slice(0, k === opens.length - 1 ? 5 : 6).map((h) => o + h * 3600));
  const c = walk({
    seed: 23,
    times,
    noise: 90,
    waypoints: [
      { at: 0, price: 27120 },
      { at: 14, price: 27360 },
      { at: 29, price: 27180 },
      { at: 30, price: 27060 },
      { at: 40, price: 26700 },
      { at: 55, price: 27420 },
      { at: 59, price: 27210 },
      { at: 66, price: 27060 },
      { at: 77, price: 27240 },
    ],
  });
  // the week of Oct 26 stays inside the one after it
  clamp(c, 0, 29, 26720, 27440);
  // the week of Nov 2: low 26,640 on Tuesday, high 27,480 on Thursday (the key level)
  pin(c, 40, { low: STORY.prevLow });
  pin(c, 55, { high: STORY.prevHigh });
  clamp(c, 30, 59, STORY.prevLow, STORY.prevHigh);
  // the forming week: low 27,020 on Monday, nothing near the previous high yet
  pin(c, 66, { low: STORY.weekLow });
  clamp(c, 60, 77, STORY.weekLow, 27300);
  // Wed 18:00 to Thu 10:00: the 15m candles, four hours at a time
  for (let k = 0; k < 5; k++) {
    const i = 78 + k;
    const t = c[i]!.t;
    c[i] = aggregate(
      entry.filter((b) => b.t >= t && b.t < t + 4 * 3600),
      t,
      c[i]!.label,
      k === 4,
    );
  }
  const before = c[77]!;
  const open = c[78]!.open;
  c[77] = { ...before, close: open, high: Math.max(before.high, open), low: Math.min(before.low, open) };
  return c;
}

function biasCandles(setup: readonly Candle[]): Candle[] {
  const last = wall(2026, 11, 8, 18);
  const times = Array.from({ length: 30 }, (_, i) => last - (29 - i) * 7 * 86400);
  const c = walk({
    seed: 9,
    times,
    noise: 520,
    label: weekLabel,
    waypoints: [
      { at: 0, price: 25600 },
      { at: 14, price: 26500 },
      { at: 24, price: 27450 },
      { at: 27, price: 26900 },
    ],
  });
  // the untaken 1W swing high 27,735 (option B), six weeks back; nothing since has traded above it
  clamp(c, 0, 23, 24800, 27600);
  pin(c, 24, { high: STORY.swingHigh });
  clamp(c, 25, 26, 26300, 27440);
  // the last three weeks are their 4h candles
  const n = c.length;
  for (let k = 0; k < 3; k++) {
    const i = n - 3 + k;
    const from = times[i]!;
    const to = k < 2 ? times[i + 1]! : Infinity;
    c[i] = aggregate(
      setup.filter((b) => b.t >= from && b.t < to),
      from,
      weekLabel(from),
      k === 2,
    );
  }
  const before = c[n - 4]!;
  const open = c[n - 3]!.open;
  c[n - 4] = { ...before, close: open, high: Math.max(before.high, open), low: Math.min(before.low, open) };
  return c;
}

const STEPS: Step[] = [
  step(1, 'blocked', '1W', 'No 1W bias', 'The last 1W candle closed back inside the one before it, so there is no continuation to follow'),
  step(
    2,
    'later',
    '1W',
    'A long opens if the 1W reaches a key level',
    "1W candle trades to the previous 1W candle's low 26,640.00 (within 80.00 of it counts); its low so far is 27,020.00, 380.00 away",
    26640,
    '1W trades to',
  ),
  step(
    3,
    'later',
    '1W',
    'A short opens if the 1W reaches a key level',
    "1W candle trades to the previous 1W candle's high 27,480.00 (within 80.00 of it counts); its high so far is 27,330.00, 150.00 away",
    27480,
    '1W trades to',
  ),
];

export const LOOK_FOR_REVERSAL: LookFor = {
  direction: 'short',
  timeframe: '4h',
  entry_timeframe: '15m',
  steps: [
    { label: '1W trades up into the previous 1W high', status: 'next' },
    { label: '4h C1 / C2 there, closing back below it', status: 'later' },
    { label: '4h turns down: a close below the up-close run, the entry', status: 'later' },
  ],
  options: [
    { key: 'A', name: 'Previous 1W high', top: STORY.prevHigh, bottom: STORY.prevHigh - STORY.band, condition: '' },
    { key: 'B', name: '1W swing high', top: STORY.swingHigh, bottom: STORY.swingHigh - STORY.band, condition: 'only after a 4h close above the key level' },
  ],
  entry: '4h close below the run',
  stop: 'above the reversal wick high',
  target: '2R, then previous 1W EQ',
  target_price: (STORY.prevHigh + STORY.prevLow) / 2,
  entry_during: true,
  kind: 'reversal',
};

const biasRead: Read = {
  role: 'bias',
  timeframe: '1W',
  status: 'failed',
  word: 'Failed',
  headline: 'No continuation bias',
  reason: 'The last 1W candle closed back inside the one before it. The forming week has not reached a key level: its high so far is 27,330.00, 150.00 below the previous high 27,480.00.',
};
const setupRead: Read = {
  role: 'setup',
  timeframe: '4h',
  status: 'not_applicable',
  word: 'Not read',
  headline: 'Not read',
  reason: 'Nothing to read on the 4h until the week reaches a key level.',
};
const entryRead: Read = {
  role: 'entry',
  timeframe: '15m',
  status: 'not_applicable',
  word: 'Not read',
  headline: 'Not read',
  reason: '',
};

export function lookForReversalView(): VerdictView {
  const entry = entryCandles();
  const setup = setupCandles(entry);
  const bias = biasCandles(setup);
  return {
    decision: 'no_trade',
    decision_word: "DON'T TRADE",
    tone: 'no_trade',
    headline: 'No trade',
    bias: 'NEUTRAL',
    path: '—',
    stage: '—',
    levels: [],
    has_levels: false,
    invalidation: '',
    summary: 'No trade. continuation gate failed; reversal: price has not reached a key level.',
    groups: [
      group('bias', 'Bias', '1W', [
        row('bias.closure', 'fail', 'The last 1W candle closed beyond the one before it', 'Closed 27,210.00, back inside 26,905.00 to 27,395.00.', 'gate'),
      ]),
      group('reversal', 'Reversal', '1W', [
        row('rev.key_level', 'fail', 'The forming 1W candle has reached a key level', 'High so far 27,330.00; the previous 1W high 27,480.00 is 150.00 away (within 80.00 counts).', 'step'),
        row('rev.reclaim', 'na', 'The 4h has closed back below the key level', 'No key level has been reached.', 'step'),
      ]),
    ],
    hidden_advisory: 0,
    notes: [],
    read: [biasRead, setupRead, entryRead],
    why: 'No continuation bias on the 1W, and the forming week has not reached a key level.',
    waiting_for: '',
    direction: '',
    requested: '',
    idea: '',
    suggestion: "DON'T TRADE",
    suggestion_tone: 'no_trade',
    idea_state: '',
    idea_alert: false,
    auto_note: '',
    steps: STEPS,
    plan: null,
    look_for: LOOK_FOR_REVERSAL,
    journal: demoJournal(null),
    charts: [
      chart('bias', '1W', 10080, bias, biasRead, []),
      chart('setup', '4h', 240, setup, setupRead, [
        level('reference', 'Prev 1W high', STORY.prevHigh, 55, 'Previous 1W high: the key level the short reversal waits for'),
        level('reference', 'Prev 1W low', STORY.prevLow, 40, 'Previous 1W low: the key level a long reversal would wait for'),
      ]),
      chart('entry', '15m', 15, entry, entryRead, []),
    ],
    chart_problem: '',
    source_note: SAMPLE_SOURCE_NOTE,
    last: { name: 'Last', price: entry[entry.length - 1]!.close.toLocaleString('en-US', { minimumFractionDigits: 2 }), note: '15m' },
  };
}
