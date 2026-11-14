// SAMPLE DATA for demo mode only (`?demo=look-for`). Every price here is invented.
//
// Thu 12 Nov 2026 07:15 New York, watch short: a bearish continuation waiting on its
// setup. The daily Candle 2 took Candle 1's high 25,506 and closed back below it; the 1h
// is pulling back up under its fair value gap 25,410 to 25,428 (option A), with the swing
// high 25,505 to 25,525 beyond it (option B). The 1D and 1h candles are built from the
// timeframe below them, so the two panes agree on time and price.
import type { Candle, LookFor, Read, Step, VerdictView } from '../wire';
import { SAMPLE_SOURCE_NOTE, biasCandle, chart, group, level, row, step } from './fixtures';
import { barTimes, isoNY, pin, walk, wall } from './seeded';

export const LOOK_WHEN = '2026-11-12T07:15:00-05:00';

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

function capHighs(candles: Candle[], from: number, to: number, cap: number): void {
  for (let i = from; i <= to; i++) {
    const c = candles[i];
    if (c && c.high > cap) candles[i] = { ...c, high: cap, open: Math.min(c.open, cap), close: Math.min(c.close, cap) };
  }
}

function floorLows(candles: Candle[], from: number, to: number, floor: number): void {
  for (let i = from; i <= to; i++) {
    const c = candles[i];
    if (c && c.low < floor) candles[i] = { ...c, low: floor, open: Math.max(c.open, floor), close: Math.max(c.close, floor) };
  }
}

/** Daily session opens (18:00 the evening before; Monday's on Sunday evening), ending at `lastOpen`. */
export function sessionOpens(lastOpen: number, count: number): number[] {
  const out: number[] = [];
  for (let t = lastOpen; out.length < count; t -= 86400) {
    if (new Date(t * 1000).getUTCDay() <= 4) out.push(t); // a session opens Sunday to Thursday evening
  }
  return out.reverse();
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const sessionLabel = (t: number) => {
  const d = new Date((t + 6 * 3600) * 1000);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
};

function entryCandles(): Candle[] {
  const times = barTimes(wall(2026, 11, 12, 7, 15), 5, 64); // 02:00 to 07:15
  const c = walk({
    seed: 31,
    times,
    noise: 6,
    forming: true,
    waypoints: [
      { at: 0, price: 25384 },
      { at: 12, price: 25377 },
      { at: 24, price: 25372 },
      { at: 38, price: 25383 },
      { at: 52, price: 25395 },
      { at: 63, price: 25399 },
    ],
  });
  pin(c, 24, { low: 25370.5 });
  floorLows(c, 0, 63, 25370.5);
  capHighs(c, 0, 63, 25404);
  return c;
}

function setupCandles(entry: readonly Candle[]): Candle[] {
  const times = barTimes(wall(2026, 11, 12, 7), 60, 60); // Mon 18:00 to Thu 07:00
  const c = walk({
    seed: 17,
    times,
    noise: 16,
    waypoints: [
      { at: 0, price: 25350 },
      { at: 20, price: 25492 },
      { at: 22, price: 25470 },
      { at: 26, price: 25500 },
      { at: 32, price: 25445 },
      { at: 36, price: 25398 },
      { at: 41, price: 25370 },
      { at: 45, price: 25392 },
      { at: 53, price: 25382 },
    ],
  });
  // Candle 1 (the Tuesday session, bars 0 to 22): low 25,330, high 25,506
  pin(c, 1, { low: 25330 });
  floorLows(c, 0, 22, 25330);
  pin(c, 20, { high: 25506 });
  capHighs(c, 0, 26, 25506);
  // Candle 2 (Wednesday, 23 to 45): the swing high 25,525 (body top 25,505) takes it, then the sell-off
  pin(c, 27, { open: 25497, close: 25505, high: 25525 });
  capHighs(c, 28, 45, 25500);
  // the fair value gap 25,410 to 25,428 left by bar 34, never filled since
  pin(c, 33, { low: 25428 });
  pin(c, 34, { open: 25431, high: 25436, low: 25401, close: 25404 });
  pin(c, 35, { high: 25410 });
  capHighs(c, 36, 59, 25409);
  pin(c, 41, { low: 25360 });
  floorLows(c, 23, 59, 25360);
  pin(c, 45, { close: 25392 });
  floorLows(c, 46, 53, 25372);
  // Thursday 02:00 to 07:00: the 5m candles, hour by hour
  for (let k = 0; k < 6; k++) {
    const i = 54 + k;
    const t = c[i]!.t;
    c[i] = aggregate(
      entry.filter((b) => b.t >= t && b.t < t + 3600),
      t,
      c[i]!.label,
      k === 5,
    );
  }
  const before = c[53]!;
  const open = c[54]!.open;
  c[53] = { ...before, close: open, high: Math.max(before.high, open), low: Math.min(before.low, open) };
  return c;
}

function biasCandles(setup: readonly Candle[]): Candle[] {
  const times = sessionOpens(wall(2026, 11, 11, 18), 30);
  const c = walk({
    seed: 5,
    times,
    noise: 70,
    label: sessionLabel,
    waypoints: [
      { at: 0, price: 25010 },
      { at: 12, price: 25240 },
      { at: 20, price: 25160 },
      { at: 26, price: 25350 },
    ],
  });
  capHighs(c, 0, c.length - 4, 25480);
  // Candle 1, Candle 2 and the forming Candle 3 are their sessions' 1h candles
  const spans: [number, number][] = [
    [0, 22],
    [23, 45],
    [46, 59],
  ];
  spans.forEach(([from, to], k) => {
    const i = c.length - 3 + k;
    c[i] = aggregate(setup.slice(from, to + 1), times[i]!, sessionLabel(times[i]!), k === 2);
  });
  return c;
}

const STEPS: Step[] = [
  step(1, 'done', '1D', '1D bias is bearish', 'Candle 3 forming; Candle 2 took the high 25,506.00 of Candle 1 and closed back below it'),
  step(
    2,
    'next',
    '1h',
    '1h pulls back to a point of interest',
    '1h candle trades up to 25,410.00 (the unfilled 1h fair value gap, the nearest point of interest), with 1h closes holding below 25,442.50',
    25410,
    '1h pullback to',
  ),
  step(3, 'later', '1h', '1h closes back down there', ''),
  step(4, 'later', '5m', '5m turns down: the entry', ''),
];

export const LOOK_FOR_SHORT: LookFor = {
  direction: 'short',
  timeframe: '1h',
  entry_timeframe: '5m',
  steps: [
    { label: '1h C1 pushes into the POI', status: 'next' },
    { label: "1h C2 sweeps C1's high", status: 'later' },
    { label: 'While that C2 forms: a 5m close below the up-close run', status: 'later' },
  ],
  options: [
    { key: 'A', name: '1h fair value gap', top: 25428, bottom: 25410, condition: '' },
    { key: 'B', name: '1h swing high', top: 25525, bottom: 25505, condition: 'only after a 1h close above the POI' },
  ],
  entry: '5m close below the run',
  stop: 'above the 1h C2 high',
  target: '2R, then PDL',
  target_price: 25360,
  entry_during: true,
  kind: 'continuation',
};

const biasRead: Read = {
  role: 'bias',
  timeframe: '1D',
  status: 'confirmed',
  word: 'Confirmed',
  headline: 'Bearish, Candle 3 forming',
  reason: 'Candle 2 took the 25,506.00 high of Candle 1 and closed back below it at 25,392.00.',
};
const setupRead: Read = {
  role: 'setup',
  timeframe: '1h',
  status: 'waiting',
  word: 'Waiting',
  headline: 'Waiting for the pullback',
  reason: 'Price is under the 1h fair value gap 25,410.00 to 25,428.00 and below the daily EQ 25,442.50.',
};
const entryRead: Read = {
  role: 'entry',
  timeframe: '5m',
  status: 'not_applicable',
  word: 'Not yet',
  headline: 'Not yet',
  reason: 'The 5m entry comes while the 1h C2 forms.',
};

export function lookForView(): VerdictView {
  const entry = entryCandles();
  const setup = setupCandles(entry);
  const bias = biasCandles(setup);
  const n = bias.length;
  return {
    decision: 'watch',
    decision_word: 'WATCH',
    tone: 'watch',
    headline: 'Watch, short continuation',
    bias: 'BEARISH',
    path: 'CONTINUATION',
    stage: 'C1',
    levels: [],
    has_levels: false,
    invalidation: 'A 1h close above 25,442.50, the daily EQ, ends the short idea.',
    summary: 'Bias is bearish. The 1h has not reached a point of interest yet.',
    groups: [
      group('bias', 'Bias', '1D', [
        row('bias.c2', 'pass', 'Candle 2 swept Candle 1 and closed back inside', 'Took 25,506.00, closed 25,392.00.', 'step'),
        row('bias.lower_half', 'pass', 'Closed in the lower half of its range', 'Close sits at 19% of the range.', 'quality'),
        row('bias.protected', 'pass', 'Protected high is intact', 'Nothing has closed above 25,525.00.', 'gate'),
      ]),
      group('setup', 'Setup', '1h', [
        row('setup.eq', 'pass', 'Closes hold below the daily EQ', 'Last 1h close below 25,442.50.', 'gate'),
        row('setup.poi', 'na', 'Price reached a point of interest', 'Nearest: the 1h fair value gap 25,410.00 to 25,428.00.', 'step'),
        row('setup.closure', 'na', 'Candle 2 closure at the point of interest', 'Waits on the pullback.', 'step'),
      ]),
      group('entry', 'Entry', '5m', [
        row('entry.cisd', 'na', 'Change in state of delivery', 'Comes while the 1h Candle 2 forms.', 'gate'),
        row('entry.trigger', 'na', 'Entry trigger', 'Arms when delivery changes.', 'step'),
      ]),
      group('quality', 'Quality', 'All', [
        row('quality.room', 'pass', 'Room to the target', '50 points from the gap to the PDL 25,360.00.', 'quality'),
        row('quality.session', 'fail', 'Inside the session window', '07:15 is before the 09:30 window.', 'quality'),
      ]),
    ],
    hidden_advisory: 0,
    notes: [],
    read: [biasRead, setupRead, entryRead],
    why: 'Daily Candle 2 took the high of Candle 1 and closed back below it. The 1h has not pulled back to a point of interest yet.',
    waiting_for: '',
    direction: 'short',
    requested: '',
    idea: 'short',
    suggestion: 'WATCH · SHORT',
    suggestion_tone: 'watch',
    idea_state: '',
    idea_alert: false,
    auto_note: '',
    steps: STEPS,
    plan: null,
    look_for: LOOK_FOR_SHORT,
    charts: [
      chart('bias', '1D', 1440, bias, biasRead, [biasCandle(1, n - 3, bias[n - 3]!.high), biasCandle(2, n - 2, bias[n - 2]!.high, 'confirm')]),
      chart('setup', '1h', 60, setup, setupRead, [
        level('reference', 'PDH', 25525, 23, 'Previous day high'),
        level('reference', 'EQ, stay below', 25442.5, 46, 'Previous day equilibrium: 1h closes stay below it'),
        level('target', 'PDL, target', 25360, 41, 'Previous day low: the target after 2R'),
      ]),
      chart('entry', '5m', 5, entry, entryRead, []),
    ],
    chart_problem: '',
    source_note: SAMPLE_SOURCE_NOTE,
    last: { name: 'Last', price: entry[entry.length - 1]!.close.toLocaleString('en-US', { minimumFractionDigits: 2 }), note: '5m' },
  };
}
