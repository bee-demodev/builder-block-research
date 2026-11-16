import { describe, expect, it } from 'vitest';
import type { Candle, Mark } from '../wire';
import { placeChoices } from './marks';
import {
  nameAnswers,
  leastCoverSpot,
  slightCover,
  bestJustBegunSpot,
  begunLevels,
  clearOfSpans,
  justBegunSpot,
  keyNameSpots,
  foldInto,
  covers,
  currentSessionMarks,
  derivedDaily,
  stackChips,
  edgeGroups,
  familyShown,
  fromMark,
  groupKeyLevels,
  groupTexts,
  keyLevels,
  nearestAround,
  takenByKeys,
  thinByGap,
  tradingDay,
  tradingWeek,
  type KeyLevel,
  type KeySource,
} from './keylevels';

/** New York wall-clock time as epoch seconds (the wire's `t`). */
const ny = (y: number, mo: number, d: number, h = 0, mi = 0) => Date.UTC(y, mo - 1, d, h, mi) / 1000;

const bar = (t: number, high: number, low: number, open = (high + low) / 2): Candle => ({
  time: '',
  t,
  open,
  high,
  low,
  close: open,
  forming: false,
  label: '',
});

/** Hourly bars from `from` for `n` hours, each 10 points wide around a base that climbs 1 a bar. */
function hours(from: number, n: number, base = 100): Candle[] {
  return Array.from({ length: n }, (_, i) => bar(from + i * 3600, base + i + 5, base + i - 5));
}

const find = (levels: KeyLevel[], short: string) => levels.find((l) => l.short === short);

describe('trading days and weeks', () => {
  it('puts the 18:00 open in the next day, and Sunday evening in the new week', () => {
    expect(tradingDay(ny(2025, 11, 17, 18))).toBe(tradingDay(ny(2025, 11, 18, 9)));
    expect(tradingDay(ny(2025, 11, 17, 17))).toBe(tradingDay(ny(2025, 11, 17, 9)));
    // Sunday 16 Nov 18:00 opens Monday 17's session: the week of 17-21 Nov
    expect(tradingWeek(ny(2025, 11, 16, 18))).toBe(tradingWeek(ny(2025, 11, 21, 16)));
    expect(tradingWeek(ny(2025, 11, 14, 16))).not.toBe(tradingWeek(ny(2025, 11, 16, 18)));
  });
});

describe('key levels of a pane', () => {
  // Daily candles open at 18:00 the evening before: Mon 10 .. Fri 14 Nov, then Mon 17, Tue 18.
  const opens = [
    ny(2025, 11, 2, 18), // Mon 3 (week before: the first loaded, so maybe cut)
    ny(2025, 11, 9, 18), // Mon 10
    ny(2025, 11, 10, 18),
    ny(2025, 11, 11, 18),
    ny(2025, 11, 12, 18),
    ny(2025, 11, 13, 18), // Fri 14
    ny(2025, 11, 16, 18), // Mon 17
    ny(2025, 11, 17, 18), // Tue 18, forming
  ];
  const highs = [300, 210, 220, 205, 215, 200, 190, 185];
  const lows = [250, 150, 160, 140, 170, 155, 120, 150];
  const daily: KeySource = { timeframe: '1D', minutes: 1440, candles: opens.map((t, i) => bar(t, highs[i]!, lows[i]!, 160 + i)) };
  // 1h pane from Mon 17 Nov 12:00 to Tue 18 Nov 08:00
  const setup: KeySource = { timeframe: '1h', minutes: 60, candles: hours(ny(2025, 11, 17, 12), 21) };

  it('gives the day open, PDH, PDL and the previous day EQ, starting at the day open', () => {
    const levels = keyLevels(setup, daily, [daily, setup]);
    const start = setup.candles.findIndex((c) => c.t === ny(2025, 11, 17, 18));
    expect(find(levels, 'Day open')).toMatchObject({ price: 167, family: 'day', start });
    expect(find(levels, 'PDH')).toMatchObject({ price: 190, start });
    expect(find(levels, 'PDL')).toMatchObject({ price: 120 });
    expect(find(levels, 'PD EQ')).toMatchObject({ price: 155 });
  });

  it('builds the week from daily candles: the week open, and the previous whole week high and low', () => {
    const levels = keyLevels(setup, daily, [daily, setup]);
    // the week opened Sunday 16 Nov 18:00, before the 1h candles loaded
    expect(find(levels, 'Wk open')).toMatchObject({ price: 166, family: 'week', start: null });
    expect(find(levels, 'PWH')).toMatchObject({ price: 220 });
    expect(find(levels, 'PWL')).toMatchObject({ price: 140 });
  });

  it('takes the week from weekly candles when the stack has them, and nothing when they stop last week', () => {
    const weekly: KeySource = {
      timeframe: '1W',
      minutes: 10080,
      candles: [bar(ny(2025, 11, 2, 18), 300, 250, 260), bar(ny(2025, 11, 9, 18), 230, 130, 170), bar(ny(2025, 11, 16, 18), 200, 120, 177)],
    };
    const levels = keyLevels(setup, daily, [weekly, daily, setup]);
    expect(find(levels, 'Wk open')).toMatchObject({ price: 177, family: 'week', start: null }); // the weekly candle's, not the daily one's 166
    expect(find(levels, 'PWH')).toMatchObject({ price: 230 });
    expect(find(levels, 'PWL')).toMatchObject({ price: 130 });
    const stale: KeySource = { ...weekly, candles: weekly.candles.slice(0, 2) }; // ends last week
    expect(keyLevels(setup, daily, [stale, daily, setup]).some((l) => l.family === 'week')).toBe(false);
  });

  it('leaves out the previous week when it is the first week loaded and starts mid-week (it is cut)', () => {
    const short: KeySource = { ...daily, candles: daily.candles.slice(2) }; // from Tue 11
    const levels = keyLevels(setup, short, [short, setup]);
    expect(find(levels, 'Wk open')).toBeDefined();
    expect(find(levels, 'PWH')).toBeUndefined();
  });

  it('keeps a first loaded week that starts on its Monday: it is whole', () => {
    const fromMonday: KeySource = { ...daily, candles: daily.candles.slice(1) }; // from Mon 10
    expect(find(keyLevels(setup, fromMonday, [fromMonday, setup]), 'PWH')).toMatchObject({ price: 220 });
    const thisWeek: KeySource = { ...daily, candles: daily.candles.slice(6) }; // from Mon 17
    expect(find(keyLevels(setup, thisWeek, [thisWeek, setup]), 'Wk open')).toMatchObject({ price: 166 });
  });

  it('draws no week levels when the daily candles stop before the week the pane is in', () => {
    const lastWeek: KeySource = { ...daily, candles: daily.candles.slice(0, 6) }; // ends Fri 14
    const levels = keyLevels(setup, lastWeek, [lastWeek, setup]);
    expect(levels.some((l) => l.family === 'week')).toBe(false);
  });

  it('draws no previous-candle levels when a tick has crossed into a candle the chart above lacks', () => {
    const entry: KeySource = {
      timeframe: '5m',
      minutes: 5,
      candles: Array.from({ length: 30 }, (_, i) => bar(ny(2025, 11, 18, 7) + i * 300, 130, 120)), // to 09:25
    };
    const stale: KeySource = { ...setup, candles: setup.candles.filter((c) => c.t <= ny(2025, 11, 18, 8)) };
    expect(keyLevels(entry, stale, [daily, stale, entry]).some((l) => l.family === 'htf')).toBe(false);
  });

  it('draws no day levels when the daily chart is missing the day the pane is in', () => {
    const stale: KeySource = { ...daily, candles: daily.candles.slice(0, -1) }; // no Tue 18
    const levels = keyLevels(setup, stale, [stale, setup]);
    expect(levels.some((l) => l.family === 'day')).toBe(false);
  });

  it('leaves out the week open when loaded history starts inside this week (its first day is unknown)', () => {
    // history from Tue 18 only: the earliest loaded candle is not the week's first
    const cut: KeySource = { ...daily, candles: daily.candles.slice(7) };
    const levels = keyLevels(setup, cut, [cut, setup]);
    expect(levels.some((l) => l.family === 'week')).toBe(false);
    expect(find(levels, 'Day open')).toBeDefined();
  });

  it('gives an intraday pane the previous candle of the timeframe above, not when that is daily', () => {
    const entry: KeySource = {
      timeframe: '5m',
      minutes: 5,
      candles: Array.from({ length: 30 }, (_, i) => bar(ny(2025, 11, 18, 6) + i * 300, 130, 120)),
    };
    const levels = keyLevels(entry, setup, [daily, setup, entry]);
    // the 1h candle the last 5m bar (08:25) is in opened at 08:00; the previous one at 07:00
    const prev = setup.candles.find((c) => c.t === ny(2025, 11, 18, 7))!;
    expect(find(levels, 'Prev 1h H')).toMatchObject({ price: prev.high, family: 'htf' });
    expect(find(levels, 'Prev 1h EQ')).toMatchObject({ price: (prev.high + prev.low) / 2 });
    expect(find(levels, '1h open')).toBeDefined();
    expect(keyLevels(setup, daily, [daily, setup]).some((l) => l.family === 'htf')).toBe(false);
  });

  it('draws a session range only once its window has closed, from candles that cover it', () => {
    const levels = keyLevels(setup, daily, [daily, setup]);
    // Asia 18:00-00:00: 1h bars opening 18:00 .. 23:00 (indexes 6 .. 11)
    const asia = setup.candles.slice(6, 12);
    expect(find(levels, 'Asia H')!.price).toBe(Math.max(...asia.map((c) => c.high)));
    expect(find(levels, 'Asia L')!.price).toBe(Math.min(...asia.map((c) => c.low)));
    expect(find(levels, 'London H')).toBeDefined();
    // at 03:00 London (02:00-05:00) is still open
    const early: KeySource = { ...setup, candles: setup.candles.filter((c) => c.t <= ny(2025, 11, 18, 3)) };
    const now = keyLevels(early, daily, [daily, early]);
    expect(find(now, 'Asia H')).toBeDefined();
    expect(find(now, 'London H')).toBeUndefined();
    // 1h candles that start after 18:00 cannot give the Asia range
    const late: KeySource = { ...setup, candles: setup.candles.filter((c) => c.t >= ny(2025, 11, 17, 20)) };
    expect(find(keyLevels(late, daily, [daily, late]), 'Asia H')).toBeUndefined();
  });

  it('builds the days from 4h candles when the stack has no daily chart, leaving out the first (maybe cut) day', () => {
    // 4h bars rolling at 18:00: Thu 13 from 06:00 (cut), Fri 14, Mon 17, Tue 18 to 06:00
    const t0 = ny(2025, 11, 13, 6);
    const times = [0, 4, 8, 12, 16, 20, 24, 28, 32].map((h) => t0 + h * 3600) // Thu 06:00 .. Fri 14:00
      .concat([ny(2025, 11, 16, 18), ny(2025, 11, 16, 22), ny(2025, 11, 17, 2), ny(2025, 11, 17, 6), ny(2025, 11, 17, 10), ny(2025, 11, 17, 14)])
      .concat([ny(2025, 11, 17, 18), ny(2025, 11, 17, 22), ny(2025, 11, 18, 2), ny(2025, 11, 18, 6)]);
    const h4: KeySource = { timeframe: '4h', minutes: 240, candles: times.map((t, i) => bar(t, 200 + i, 100 + i, 150 + i)) };
    const m15: KeySource = { timeframe: '15m', minutes: 15, candles: [bar(ny(2025, 11, 18, 6), 170, 160)] };
    const days = derivedDaily([h4, m15])!;
    expect(days.candles.map((c) => c.t)).toEqual([ny(2025, 11, 13, 18), ny(2025, 11, 16, 18), ny(2025, 11, 17, 18)]);
    const levels = keyLevels(m15, h4, [h4, m15]);
    // Mon 17 (bars 9..14) is the previous day; Tue 18 opened at 18:00 Mon (bar 15)
    expect(find(levels, 'PDH')!.price).toBe(214);
    expect(find(levels, 'PDL')!.price).toBe(109);
    expect(find(levels, 'Day open')!.price).toBe(165);
    expect(derivedDaily([m15])).toBeNull();
  });

  it('gives a daily pane only the week levels', () => {
    const levels = keyLevels(daily, null, [daily]);
    expect(new Set(levels.map((l) => l.family))).toEqual(new Set(['week']));
  });
});

describe('grouping and showing', () => {
  const lv = (price: number, short: string, family: KeyLevel['family'], start: number | null = 10): KeyLevel => ({ price, short, name: short, family, start });

  it('merges levels at one price, most senior first, each wording once, from the earliest start', () => {
    const groups = groupKeyLevels([lv(100.25, 'Asia L', 'session', 4), lv(100.25, 'PDL', 'day', 8), lv(100.249, 'PDL', 'day'), lv(120, 'PWH', 'week')], 2);
    expect(groups.map((g) => g.price)).toEqual([120, 100.25]);
    expect(groups[1]!.levels.map((l) => l.short)).toEqual(['PDL', 'Asia L']);
    expect(groups[1]!.start).toBe(4);
    expect(groupKeyLevels([lv(1, 'a', 'core', null), lv(1, 'b', 'day', 3)], 2)[0]!.start).toBeNull();
  });

  it('keeps every name in the hover when two levels share a wording', () => {
    const core: KeyLevel = { price: 5, short: '1D EQ', name: 'Respect level on the setup timeframe', family: 'core', start: 2 };
    const day: KeyLevel = { price: 5, short: 'PD EQ', name: 'Previous day equilibrium', family: 'day', start: 3 };
    const [g] = groupKeyLevels([core, day], 2);
    expect(g!.levels).toHaveLength(1);
    expect(g!.levels[0]!.name).toBe('Previous day equilibrium; Respect level on the setup timeframe');
    expect(core.name).toBe('Respect level on the setup timeframe'); // the input is not changed
  });

  it('keeps each merged level its own start, so a later one is not named before it began', () => {
    const older: KeyLevel = { price: 7, short: '1D EQ', name: 'Respect level', family: 'core', start: 2 };
    const later: KeyLevel = { price: 7, short: 'PDH', name: 'Previous day high', family: 'day', start: 40 };
    const again: KeyLevel = { price: 7, short: 'PDH', name: 'Previous day high', family: 'day', start: 30 };
    const [g] = groupKeyLevels([later, older, again], 2);
    expect(g!.start).toBe(2);
    expect(g!.levels.map((l) => [l.short, l.start])).toEqual([['1D EQ', 2], ['PDH', 30]]);
  });

  it('merges the core’s wording of a bias level with this module’s on 4h and 1W bias stacks', () => {
    const lv = (short: string, name: string, family: KeyLevel['family']): KeyLevel => ({ price: 100, short, name, family, start: 3, fromCore: family === 'core' });
    // 4h / 15m / 1m: the core's shared bias levels against the column candle's
    const high = groupKeyLevels([lv('Prev 4h high', 'Previous bias candle high', 'core'), lv('Prev 4h H', 'Previous 4h candle high', 'htf')], 2);
    expect(high).toHaveLength(1);
    expect(high[0]!.levels.map((l) => l.short)).toEqual(['Prev 4h H']);
    expect(high[0]!.levels[0]!.family).toBe('htf'); // dashed and zoomed like its siblings
    expect(high[0]!.levels[0]!.name).toBe('Previous 4h candle high; Previous bias candle high');
    const eq = groupKeyLevels([lv('4h EQ', 'Respect level', 'core'), lv('Prev 4h EQ', 'Previous 4h candle equilibrium', 'htf')], 2);
    expect(eq[0]!.levels.map((l) => l.short)).toEqual(['Prev 4h EQ']);
    // 1W / 4h / 15m: the previous week's high
    const week = groupKeyLevels([lv('Prev 1W high', 'Previous bias candle high', 'core'), lv('PWH', 'Previous week high', 'week')], 2);
    expect(week[0]!.levels.map((l) => l.short)).toEqual(['PWH']);
    // a bias EQ with no timeframe in its wording still merges; two different levels at one price do not
    const bare = groupKeyLevels([lv('EQ', 'Previous bias candle equilibrium', 'core'), lv('Prev 4h EQ', 'x', 'htf')], 2);
    expect(bare[0]!.levels).toHaveLength(1);
    const two = groupKeyLevels([lv('PDH', 'Previous day high', 'day'), lv('PWH', 'Previous week high', 'week')], 2);
    expect(two[0]!.levels.map((l) => l.short)).toEqual(['PWH', 'PDH']);
  });

  it('words a group fullest first, then the senior name with a count, then the name alone', () => {
    expect(groupTexts([lv(1, 'PDL', 'day'), lv(1, 'Asia L', 'session')])).toEqual(['PDL · Asia L', 'PDL +1', 'PDL']);
    expect(groupTexts([lv(1, 'PWH', 'week')])).toEqual(['PWH']);
  });

  it('drops the finer families as the view spans more time', () => {
    expect(familyShown('session', 220, 60)).toBe(true);
    expect(familyShown('session', 2 * 1440, 60)).toBe(false);
    expect(familyShown('htf', 15 * 60, 60)).toBe(true);
    expect(familyShown('htf', 17 * 60, 60)).toBe(false);
    expect(familyShown('day', 20 * 1440, 1440)).toBe(true);
    expect(familyShown('week', 400 * 1440, 1440)).toBe(true);
  });

  it('keeps the senior of two lines closer than a label, and lists the one left out under it', () => {
    const a = { y: 100, levels: [lv(1, 'Asia H', 'session')], group: { price: 1 } };
    const b = { y: 108, levels: [lv(2, 'PDH', 'day')], group: { price: 2 } };
    const c = { y: 140, levels: [lv(3, 'London H', 'session')], group: { price: 3 } };
    const { kept, near } = thinByGap([a, b, c], 19);
    expect(kept).toEqual([b, c]);
    expect(near.get(b)).toEqual([a]);
  });

  it('breaks a tie in seniority toward the level nearer the price', () => {
    const far = { y: 100, levels: [lv(1, 'Asia L', 'session')], group: { price: 90 } };
    const close = { y: 110, levels: [lv(2, 'London L', 'session')], group: { price: 99 } };
    expect(thinByGap([far, close], 19, 100).kept).toEqual([close]);
  });

  it('tags the nearest level above and below the price, and chips the nearest past each edge', () => {
    const gs = [{ price: 90 }, { price: 95 }, { price: 105 }, { price: 130 }, { price: 100 }];
    const { up, down } = nearestAround(gs, 100);
    expect(up.map((g) => g.price)).toEqual([105, 130]);
    expect(down.map((g) => g.price)).toEqual([95, 90]);
    const { above, below } = edgeGroups(gs, 110, 92, 2);
    expect(above.map((g) => g.price)).toEqual([130]);
    expect(below.map((g) => g.price)).toEqual([90]);
  });
});

describe('core marks in the key layer', () => {
  const mark = (role: string, title: string, label: string, price: number | null = 10): Mark => ({
    kind: 'level',
    role,
    label,
    title,
    price,
    top: null,
    bottom: null,
    start: 5,
    end: null,
  });

  it('takes the session and plain reference levels, never a trade or next level', () => {
    expect(takenByKeys(mark('session', 'Asia session low', 'Asia L'), 'short')).toBe(true);
    expect(takenByKeys(mark('reference', 'Previous bias candle equilibrium', 'EQ'), 'short')).toBe(true);
    expect(takenByKeys(mark('next', 'Next level', 'Next'), 'short')).toBe(false);
    expect(takenByKeys(mark('stop', 'Stop', 'Stop'), 'short')).toBe(false);
    expect(takenByKeys(mark('session', 'x', 'x', null), 'short')).toBe(false);
    expect(takenByKeys({ ...mark('reference', 'Old level', 'Old'), end: 40 }, 'short')).toBe(false); // ends part way
  });

  it('files the core PDH with the day levels so the computed one merges into it', () => {
    expect(fromMark(mark('session', 'Previous day high', 'PDH'))).toMatchObject({ family: 'day', short: 'PDH', start: 5 });
    expect(fromMark(mark('session', 'London session high', 'London H'))!.family).toBe('session');
    expect(fromMark(mark('reference', 'Respect level on the setup timeframe', '1D EQ'))!.family).toBe('core');
  });
});

describe('edge chips and begun levels', () => {
  // slots from the top edge: y = 4, 22, 40, ...
  const slotY = (n: number) => (n < 6 ? 4 + n * 18 : null);

  it('stacks the farthest at the edge and the nearest inward', () => {
    const [near, far] = stackChips([60, 50], slotY, 300, 15, [], 6);
    expect(far).toEqual({ x: 250, y: 4, w: 50, h: 15 });
    expect(near).toEqual({ x: 240, y: 22, w: 60, h: 15 });
  });

  it('slides a chip left past a candle, and skips a slot that holds a line', () => {
    const candle = { x: 280, y: 0, w: 10, h: 12 }; // a wick in slot 0 at the right
    const line = { x: 0, y: 25, w: 300, h: 4 }; // a key line through slot 1
    const [only] = stackChips([50], slotY, 300, 15, [candle, line], 6);
    expect(only).toEqual({ x: 226, y: 4, w: 50, h: 15 });
    const [a, b] = stackChips([50, 50], slotY, 300, 15, [line], 6);
    expect(b!.y).toBe(4); // the farther at the edge
    expect(a!.y).toBe(40); // the nearer steps over the line's slot
  });

  it('gives the nearest a chip before a farther one when only one fits', () => {
    const tight = (n: number) => (n === 0 ? 4 : null);
    expect(stackChips([60, 50], tight, 300, 15, [], 6)).toEqual([{ x: 240, y: 4, w: 60, h: 15 }, null]);
  });

  it('keeps only the levels that have begun by the right edge', () => {
    const lv = (start: number | null): KeyLevel => ({ price: 1, short: String(start), name: '', family: 'day', start });
    const xOf = (start: number) => start * 10;
    expect(begunLevels([lv(null), lv(5), lv(40)], xOf, 300).map((l) => l.start)).toEqual([null, 5]);
  });
});

describe('session honesty', () => {
  const hourly = (from: number, n: number, forming = false): KeySource => ({
    timeframe: '1h',
    minutes: 60,
    candles: hours(from, n).map((c, i, all) => ({ ...c, forming: forming && i === all.length - 1 })),
  });
  const begin = ny(2025, 11, 18, 2);
  const end = ny(2025, 11, 18, 5);

  it('needs candles through the session close', () => {
    expect(covers(hourly(ny(2025, 11, 18, 0), 5), begin, end)).toBe(true); // 00:00 .. 04:00, closed at 05:00
    expect(covers(hourly(ny(2025, 11, 18, 0), 3), begin, end)).toBe(false); // stops at 02:00
    expect(covers(hourly(ny(2025, 11, 18, 0), 5, true), begin, end)).toBe(false); // 04:00 still forming
    expect(covers(hourly(ny(2025, 11, 18, 3), 4), begin, end)).toBe(false); // starts after the open
  });

  it('leaves out a session whose only source stops before it closed', () => {
    const entry: KeySource = { timeframe: '5m', minutes: 5, candles: [bar(ny(2025, 11, 18, 5), 10, 5)] };
    const short = hourly(ny(2025, 11, 17, 17), 10); // 17:00 .. 02:00
    expect(keyLevels(entry, short, [short, entry]).some((l) => l.short.startsWith('London'))).toBe(false);
  });

  it('drops the core session marks once a tick has rolled into the next trading day', () => {
    const marks = [{ role: 'session' }, { role: 'reference' }];
    const day = tradingDay(ny(2025, 11, 18, 16));
    expect(currentSessionMarks(marks, day, ny(2025, 11, 18, 16, 55))).toHaveLength(2);
    expect(currentSessionMarks(marks, day, ny(2025, 11, 18, 18)).map((m) => m.role)).toEqual(['reference']);
    expect(currentSessionMarks(marks, null, null).map((m) => m.role)).toEqual(['reference']);
  });
});

describe('folding left-out lines into hovers', () => {
  it('carries what a dropped line already held, so a level thinned twice is still listed', () => {
    const london = { y: 105, name: 'London H' };
    const prev1h = { y: 100, name: 'Prev 1h H' };
    const pdh = { y: 60, name: 'PDH' };
    const near = new Map([[prev1h, [london]]]); // London H was thinned under Prev 1h H
    const kept = foldInto([pdh, prev1h], near, (l) => l === prev1h); // then Prev 1h H had no room for its name
    expect(kept).toEqual([pdh]);
    expect(near.get(pdh)).toEqual([prev1h, london]);
    expect(near.has(prev1h)).toBe(false);
  });
});

describe('key name spots', () => {
  // a line from x=100 to the names' right edge at 400, at y=200, names 15 high in a 600-high plot
  const spots = (others: { x: number; y: number }[], below = false, line = { x: 100, y: 200 }, w = 40) => keyNameSpots(line, others, w, 400, 15, 600, below);

  it('puts the name above a line over the last close at the right end first, then further left', () => {
    const s = spots([]);
    expect(s[0]).toEqual({ x: 360, y: 182, w: 40, h: 15 });
    expect(s[1]!.x).toBe(340); // then half a name further left
    expect(s.slice(0, 3).every((b) => b.y === 182)).toBe(true);
  });

  it('never crosses another key line, and flips sides only into a strip with room for two names', () => {
    const tight = spots([{ x: 0, y: 212 }], true); // below is preferred; a line 12 px under: no room
    expect(tight.length).toBeGreaterThan(0);
    expect(tight.every((b) => b.y + b.h < 212 || b.y > 212)).toBe(true);
    expect(tight.every((b) => b.y < 200)).toBe(true); // so the name goes above, where the strip is free
    const crowded = spots([{ x: 0, y: 230 }, { x: 0, y: 175 }], true); // both strips have a neighbour
    expect(crowded.every((b) => b.y + b.h > 200)).toBe(true); // no flip into the strip above (the lead-in is centred)
  });

  it('tries the whole line, right to left, so a name finds a gap between candles', () => {
    // a long line from x=20; its right end and its start are under candles, with a gap between
    const s = keyNameSpots({ x: 20, y: 200 }, [], 40, 400, 15, 600, false);
    const candles = [{ x: 330, y: 150, w: 70, h: 80 }, { x: 20, y: 150, w: 120, h: 80 }];
    const clear = s.filter((b) => !candles.some((c) => b.x < c.x + c.w && c.x < b.x + b.w && b.y < c.y + c.h && c.y < b.y + b.h));
    expect(clear.length).toBeGreaterThan(0);
    expect(clear[0]!.x).toBeGreaterThan(140);
    expect(clear[0]!.x + 40).toBeLessThan(330);
  });

  it('splits a close pair to opposite sides, so each name sits nearer its own line', () => {
    // two lines 21 px apart, both below the close: the lower one is in the upper one's strip below
    const s = keyNameSpots({ x: 20, y: 200 }, [{ x: 20, y: 221 }], 40, 400, 15, 600, true);
    expect(s[0]!.y).toBe(182); // above its own line
    expect(s.every((b) => b.y + b.h <= 200 || b.y < 200)).toBe(true); // nothing in the strip it shares
  });

  it('offers every line a lead-in left of its start, sliding past candles there', () => {
    const s = spots([], false, { x: 100, y: 200 }, 40);
    expect(s[s.length - 1]).toEqual({ x: 56, y: 192.5, w: 40, h: 15 });
    const candle = { x: 92, y: 150, w: 4, h: 80 }; // a wick where the lead-in would sit
    const slid = keyNameSpots({ x: 100, y: 200 }, [], 40, 400, 15, 600, false, [candle]);
    expect(slid[slid.length - 1]).toEqual({ x: 48, y: 192.5, w: 40, h: 15 }); // slid left past it, still beside the line
    const wide = keyNameSpots({ x: 100, y: 200 }, [], 40, 400, 15, 600, false, [{ x: 80, y: 150, w: 8, h: 80 }]);
    expect(wide.some((b) => b.y === 192.5)).toBe(false); // past a wider candle it would float off its line
    const wall = keyNameSpots({ x: 100, y: 200 }, [], 40, 400, 15, 600, false, [{ x: 0, y: 150, w: 96, h: 80 }]);
    expect(wall.some((b) => b.y === 192.5)).toBe(false); // nowhere clear: no lead-in
    // a wall of candles with a gap 100 px to the left: the name would float off its line, so no lead-in
    const far = keyNameSpots({ x: 300, y: 200 }, [], 40, 400, 15, 600, false, [{ x: 150, y: 150, w: 146, h: 80 }]);
    expect(far.some((b) => b.y === 192.5)).toBe(false);
  });

  it('keeps the name of a short line at its right end, and offers a lead-in left of its start', () => {
    const s = spots([], false, { x: 380, y: 200 });
    expect(s[0]).toEqual({ x: 360, y: 182, w: 40, h: 15 }); // reaching left past the start
    expect(s[s.length - 1]).toEqual({ x: 336, y: 192.5, w: 40, h: 15 });
  });
});

describe('a just-begun senior line keeps its name', () => {
  const plot = { w: 500, h: 400 };
  const box = { x: 400, y: 100, w: 50, h: 15 };

  it('takes its right-end spot over candles while the line is short but visible', () => {
    expect(justBegunSpot(60, 50, 15, box, plot, [])).toBe(true);
  });

  it('gives way when the line is a stub (far zoomed out) or long, off the plot, or on a label', () => {
    expect(justBegunSpot(10, 50, 15, box, plot, [])).toBe(false); // a 10 px stub
    expect(justBegunSpot(150, 50, 15, box, plot, [])).toBe(false); // three names long: an old period
    expect(justBegunSpot(60, 50, 15, { ...box, y: 395 }, plot, [])).toBe(false);
    expect(justBegunSpot(60, 50, 15, box, plot, [{ x: 420, y: 105, w: 40, h: 15 }])).toBe(false);
    expect(justBegunSpot(60, 50, 15, box, plot, [{ x: 380, y: 106.5, w: 100, h: 3 }])).toBe(false); // a column hairline
  });
});

describe('a key name never sits on a column hairline', () => {
  it('moves along its line when a hairline crosses the right-end spot', () => {
    const spots = keyNameSpots({ x: 20, y: 200 }, [], 40, 400, 15, 600, false);
    const hairline = { x: 300, y: 191.5, w: 100, h: 3 }; // 8.5 px above the line, through the right-end name
    const [r] = placeChoices([{ choices: [{ candidates: spots }] }], { w: 500, h: 600 }, [hairline]);
    expect(r).not.toBeNull();
    expect(r!.box.x + r!.box.w).toBeLessThanOrEqual(300);
    expect(r!.box.y).toBe(182); // still above its own line
  });
});

describe('hairlines at a line’s own price', () => {
  it('never bar its own name, whether that hairline is drawn or not', () => {
    const spot = { x: 50, y: 192.5, w: 40, h: 15 }; // a lead-in over the line's own price
    const own = { x: 0, y: 198.5, w: 100, h: 3, price: 24903.75 };
    const other = { x: 0, y: 195, w: 100, h: 3, price: 24905 };
    // the same answer with and without its own hairline in the list (drawn or skipped)
    expect(clearOfSpans([spot], [own], 24903.75, 2)).toEqual([spot]);
    expect(clearOfSpans([spot], [], 24903.75, 2)).toEqual([spot]);
    expect(clearOfSpans([spot], [own, other], 24903.75, 2)).toEqual([]); // another price's hairline still bars it
  });
});

describe('the just-begun fallback picks the spot that covers the fewest candles', () => {
  const plot = { w: 500, h: 400 };
  const a = { x: 400, y: 100, w: 50, h: 15 };
  const b = { x: 340, y: 100, w: 50, h: 15 };
  const candle = { x: 395, y: 90, w: 20, h: 40 }; // over a, clear of b

  it('takes the least covered spot', () => {
    expect(bestJustBegunSpot(60, 50, 15, [a, b], plot, [], [candle], 120, 1440)).toEqual(b);
  });

  it('gives way past a quarter of its period when every spot covers candles', () => {
    const wall = { x: 300, y: 90, w: 200, h: 40 };
    expect(bestJustBegunSpot(60, 50, 15, [a, b], plot, [], [wall], 14 * 60, 1440)).toBeNull(); // a day 14 h in
    expect(bestJustBegunSpot(60, 50, 15, [a, b], plot, [], [wall], 2 * 60, 1440)).not.toBeNull(); // a day 2 h in
    expect(bestJustBegunSpot(60, 50, 15, [a, b], plot, [], [wall], 40 * 60, 10080)).not.toBeNull(); // a week 40 h in
    expect(bestJustBegunSpot(60, 50, 15, [a, b], plot, [], [candle], 14 * 60, 1440)).toEqual(b); // b is clear
  });
});

describe('a computed level absorbing the core copy of itself', () => {
  it('starts where this layer starts it (today’s open), not the core’s earlier start', () => {
    const core: KeyLevel = { price: 9, short: 'PDH', name: 'Previous day high', family: 'day', start: 3, fromCore: true };
    const mine: KeyLevel = { price: 9, short: 'PDH', name: 'Previous day high', family: 'day', start: 40 };
    const [g] = groupKeyLevels([core, mine], 2);
    expect(g!.levels).toHaveLength(1);
    expect(g!.start).toBe(40);
  });
});

describe('the nearest level’s last-resort name spot', () => {
  it('is the clear spot covering the fewest candles (slightCover is the just-begun rule’s test)', () => {
    const plot = { w: 500, h: 400 };
    const a = { x: 400, y: 100, w: 50, h: 15 };
    const b = { x: 340, y: 100, w: 50, h: 15 };
    const wick = { x: 360, y: 90, w: 2, h: 40 }; // a thin wick across b
    const body = { x: 400, y: 90, w: 30, h: 40 }; // a body across a
    const spot = leastCoverSpot([a, b], plot, [], [wick, body])!;
    expect(spot.box).toEqual(b);
    expect(slightCover(spot)).toBe(true);
    expect(slightCover(leastCoverSpot([a], plot, [], [body])!)).toBe(false);
    expect(leastCoverSpot([a], plot, [{ x: 410, y: 105, w: 5, h: 5 }], [])).toBeNull(); // blocked
  });
});

describe('the stored name answers', () => {
  it('records a line dropped during placement as unnamed, so a stale "named" cannot outlive it', () => {
    const asia = { id: 'Asia H', fine: true };
    const pdh = { id: 'PDH', fine: false };
    const london = { id: 'London H', fine: true };
    // Asia H was dropped in an early pass (not among the last pass's lines); London H was named
    const answers = nameAnswers([asia, pdh, london], new Set([london]), (l) => l.fine);
    expect(answers.get(asia)).toBe(false);
    expect(answers.get(london)).toBe(true);
    expect(answers.has(pdh)).toBe(false); // a long senior line is not judged
    // clear -> obstructed -> clear: the answer follows the geometry, whatever was stored before
    const store = new Map<string, boolean>();
    for (const placed of [new Set([asia, london]), new Set([london]), new Set([asia, london])]) {
      for (const [line, named] of nameAnswers([asia, pdh, london], placed, (l) => l.fine)) store.set(line.id, named);
      expect(store.get('Asia H')).toBe(placed.has(asia));
    }
  });
});

describe('a last-resort name crosses wicks, never a body', () => {
  it('skips a spot over a body even when it covers the least', () => {
    const plot = { w: 500, h: 400 };
    const a = { x: 400, y: 100, w: 50, h: 15 };
    const b = { x: 340, y: 100, w: 50, h: 15 };
    const body = { x: 410, y: 104, w: 6, h: 8 }; // a small body inside a
    const wicks = [{ x: 410, y: 90, w: 6, h: 40 }, { x: 345, y: 80, w: 40, h: 60 }]; // a's wick small, b's large
    expect(leastCoverSpot([a, b], plot, [], wicks)!.box).toEqual(a); // by wick cover alone, a wins
    expect(leastCoverSpot([a, b], plot, [body], wicks)!.box).toEqual(b); // but a covers a body
    expect(leastCoverSpot([a], plot, [body], wicks)).toBeNull(); // only a body-covering spot: give way
  });
});

describe('a level the core sent never gives way to a computed one', () => {
  it('keeps the merged respect level over a Wk open 20 px away', () => {
    const [eq] = groupKeyLevels(
      [
        { price: 25052.375, short: '1D EQ', name: 'Respect level on the setup timeframe', family: 'core', start: 140, fromCore: true },
        { price: 25052.375, short: 'PD EQ', name: 'Previous day equilibrium', family: 'day', start: 146 },
      ],
      2,
    );
    expect(eq!.levels[0]!.family).toBe('day'); // dashed and zoomed as a day level
    const wk = { price: 25085.5, short: 'Wk open', name: 'Week open', family: 'week' as const, start: 120 };
    const lines = [
      { y: 514, levels: eq!.levels, group: eq! },
      { y: 494, levels: [wk], group: { price: wk.price } },
    ];
    const { kept, near } = thinByGap(lines, 21, 24722.5);
    expect(kept.map((k) => k.y)).toEqual([514]);
    expect(near.get(kept[0]!)!.map((k) => k.y)).toEqual([494]);
  });

  it('gives the same answer whatever order the core and computed copies arrive in', () => {
    const core: KeyLevel = { price: 25052.375, short: '1D EQ', name: 'Respect level on the setup timeframe', family: 'core', start: 140, fromCore: true };
    const mine: KeyLevel = { price: 25052.375, short: 'PD EQ', name: 'Previous day equilibrium', family: 'day', start: 146 };
    const [a] = groupKeyLevels([core, mine], 2);
    const [b] = groupKeyLevels([mine, core], 2);
    expect(b).toEqual(a);
    expect(b!.levels[0]).toMatchObject({ short: 'PD EQ', family: 'day', start: 146, coreSent: true });
  });
});
