import { describe, expect, it } from 'vitest';
import { detectRange, pickRange, rangeOf, readRange, type Bar, type Range, type RangePick, type ReadOptions, type Reading, type StepKey } from './expansion';
import { SCENARIOS } from './scenarios';
import { consequence, explainShadow, shadowAt as shadowAtPick, shadowTitle, type Shadow } from './shadow';

/** As the tab calls it: with the way it picks the range (default: a candle of the expansion was picked). */
const shadowAt = (bars: readonly Bar[], range: Range, cursor: number, o: ReadOptions, pick?: RangePick) =>
  shadowAtPick(bars, range, cursor, o, pick ?? { kind: 'anchor', at: range.end });

const opts = { minSize: 30, decimals: 0 };
const status = (r: Reading, key: StepKey) => r.steps.find((s) => s.key === key)?.status;
const mirror = (bars: readonly Bar[]): Bar[] => bars.map((b) => ({ t: b.t, open: -b.open, close: -b.close, high: -b.low, low: -b.high }));
const scenario = (key: string) => SCENARIOS.find((x) => x.key === key)!;
const at = (key: string, cursor: number, min = 30) => {
  const s = scenario(key);
  return shadowAt(s.bars, detectRange(s.bars, s.anchor, cursor)!, cursor, { ...opts, minSize: min });
};
const ohlc = (rows: readonly (readonly [number, number, number, number])[]): Bar[] =>
  rows.map(([open, high, low, close], i) => ({ t: i * 300, open, high, low, close }));

/**
 * Everything a shown shadow must hold, wherever it is drawn. `where` names the moment in a failure.
 *  - A settles the pending decision and B does not.
 *  - A settles nothing else, except what no candle could avoid (a close past CSD when CSD sits at or
 *    under 50%, or past EQ when price is still short of an EQ that sits under the close it needs).
 *  - No ghost (but "Extends") voids the range, trades the target, counts as an OLR, or reaches the stop.
 *  - Every ghost opens at the last close one bar later, is a valid candle, and its caption is the rules' read.
 */
function expectHonest(where: string, bars: readonly Bar[], range: Range, cursor: number, sh: Shadow, o: ReadOptions = opts) {
  const now = readRange(bars, range, cursor, o);
  const w = (p: number) => (range.dir === 'down' ? p : -p);
  const c0 = w(bars[cursor]!.close);
  expect(status(sh.a.after, sh.decision), `${where} A settles`).toBe('pass');
  expect(status(sh.b.after, sh.decision), `${where} B does not`).not.toBe('pass');
  const forced = (k: StepKey) =>
    (sh.decision === 'half' && k === 'csd' && w(range.csd) <= Math.max(w(range.half), c0)) ||
    (sh.decision === 'half' && k === 'eq' && w(range.eq) <= Math.max(w(range.half), c0) && c0 < w(range.eq)) ||
    (sh.decision === 'csd' && k === 'eq' && w(range.eq) <= w(range.csd) && c0 < w(range.eq));
  for (const k of ['range', 'half', 'csd', 'entry', 'eq', 'target'] as StepKey[]) {
    if (k !== sh.decision && !forced(k)) expect(status(sh.a.after, k), `${where} A leaves ${k}`).toBe(status(now, k));
  }
  // the range stays the trader's: A reads it as it is; B keeps its start (only "Extends" moves the end)
  expect([sh.a.after.range.start, sh.a.after.range.end], `${where} A range`).toEqual([range.start, range.end]);
  expect(sh.b.after.range.start, `${where} B range start`).toBe(range.start);
  if (sh.decision !== 'range') expect(sh.b.after.range.end, `${where} B range end`).toBe(range.end);
  for (const br of [sh.a, sh.b]) {
    const c = br.candle;
    const tag = `${where} ${br.key}`;
    expect(c.open, `${tag} no gap`).toBe(bars[cursor]!.close);
    expect(c.t, `${tag} next bar`).toBe(bars[cursor]!.t + (cursor > 0 ? bars[cursor]!.t - bars[cursor - 1]!.t : 300));
    expect(c.high, `${tag} high`).toBeGreaterThanOrEqual(Math.max(c.open, c.close));
    expect(c.low, `${tag} low`).toBeLessThanOrEqual(Math.min(c.open, c.close));
    expect(consequence(sh, br).endsWith(`${br.after.verdict.word}. ${br.after.verdict.detail}`), `${tag} caption`).toBe(true);
    if (sh.decision === 'range' && br.key === 'B') continue; // "Extends" runs on past the low by design
    expect(br.after.voidAt, `${tag} void`).toBeNull();
    expect(status(br.after, 'target'), `${tag} target`).not.toBe('pass');
    if (status(now, 'olr') !== 'pass') expect(status(br.after, 'olr'), `${tag} olr`).not.toBe('pass');
    if (br.after.stop !== null) {
      if (range.dir === 'down') expect(c.low, `${tag} stop`).toBeGreaterThan(br.after.stop);
      else expect(c.high, `${tag} stop`).toBeLessThan(br.after.stop);
    }
  }
  const bText = consequence(sh, sh.b);
  const sameRange = sh.b.after.range.start === sh.now.range.start && sh.b.after.range.end === sh.now.range.end;
  const same = sameRange && sh.b.after.verdict.word === sh.now.verdict.word && sh.b.after.verdict.detail === sh.now.verdict.detail;
  expect(bText.startsWith('No change: still '), `${where} no change`).toBe(same);
}

/**
 * Charts the practice lessons never produce, from the council's reproductions: a last candle closing in
 * its far half or on the range low, an open under its own 50%, CSD past EQ after a gap, CSD next to the
 * target, the target one candle away, a CSD candle past the target, a stop between price and EQ.
 */
const EDGES: { key: string; bars: Bar[]; anchor: number; at: number; off?: true }[] = [
  { key: 'far-half', bars: ohlc([[150, 152, 149, 151], [151, 151, 120, 121], [121, 121, 95, 112]]), anchor: 2, at: 2 },
  { key: 'far-half-csd', bars: ohlc([[200, 205, 195, 200], [200, 201, 140, 141], [141, 142, 125, 138]]), anchor: 2, at: 2 },
  { key: 'near-low', bars: ohlc([[150, 152, 149, 151], [151, 151, 120, 121], [121, 121, 100, 102], [102, 115, 101, 114], [114, 115, 101, 101.5]]), anchor: 2, at: 4 },
  { key: 'close-on-low', bars: ohlc([[150, 152, 149, 151], [151, 151, 120, 121], [121, 121, 100, 100]]), anchor: 2, at: 2 },
  { key: 'close-on-low-2', bars: ohlc([[150, 151, 149, 150], [150, 150, 120, 120], [120, 120, 100, 100]]), anchor: 2, at: 2 },
  { key: 'close-on-low-3', bars: ohlc([[1000, 1004, 997, 1003], [1003, 1015, 999, 1011], [1011, 1024, 976, 981], [981, 990, 970, 970]]), anchor: 3, at: 3 },
  { key: 'open-under-half', bars: ohlc([[1006, 1020, 986, 986], [986, 986, 975, 976], [976, 990, 942, 948], [945, 947, 934, 934], [934, 949, 932, 932]]), anchor: 4, at: 4 },
  { key: 'csd-under-half', bars: ohlc([[863, 863, 863, 863], [863, 870, 827, 839], [839, 859, 830, 830], [830, 836, 830, 836]]), anchor: 2, at: 3 },
  { key: 'csd-near-target', bars: ohlc([[970, 992, 957, 974], [974, 974, 971, 971], [971, 975, 941, 959], [959, 972, 959, 971], [977, 977, 954, 959]]), anchor: 2, at: 4 },
  { key: 'csd-near-target-2', bars: ohlc([[200, 201, 190, 192], [192, 193, 100, 110], [110, 160, 105, 155]]), anchor: 1, at: 2 },
  { key: 'near-target', bars: ohlc([[195, 201, 194, 200], [200, 200, 174, 175], [175, 176, 100, 102], [102, 140, 101, 139], [160, 197, 159, 196], [196, 199, 190, 198]]), anchor: 2, at: 5 },
  { key: 'target-wick', bars: ohlc([[150, 400, 149, 200], [200, 201, 170, 171], [171, 172, 160, 161], [161, 177, 160.5, 175], [175, 179, 172, 178]]), anchor: 2, at: 4 },
  { key: 'csd-past-target', bars: ohlc([[150, 152, 149, 151], [151, 151, 120, 121], [121, 121, 100, 102], [102, 103, 101, 103], [114, 160, 113, 157]]), anchor: 2, at: 4, off: true },
  { key: 'entry-at-eq', bars: ohlc([[1000, 1004, 994, 994], [994, 995, 988, 990], [990, 998, 959, 968], [968, 976, 955, 963], [963, 983, 954, 954], [954, 979, 941, 979]]), anchor: 4, at: 5 },
  { key: 'stop-under-eq-1', bars: ohlc([[200, 201, 100.8, 101.2], [101.2, 101.3, 100, 100.1], [100.1, 102, 100.05, 101.5], [101.5, 102, 101.3, 101.4]]), anchor: 1, at: 3 },
  { key: 'stop-under-eq-2', bars: ohlc([[300, 302, 299, 301], [301, 301, 101, 102], [102, 102, 100, 100.5], [100.5, 103, 100.4, 102.5], [102.5, 103, 100.5, 102]]), anchor: 2, at: 4 },
  { key: 'gap-past-eq', bars: ohlc([[195, 201, 194, 200], [200, 200, 174, 175], [175, 176, 100, 102], [102, 140, 101, 139], [160, 182, 159, 180], [180, 182, 176, 178]]), anchor: 2, at: 5 },
  { key: 'tight', bars: ohlc([[150, 152, 149, 151], [151, 151, 91, 92], [92, 92, 90, 90.2], [90.2, 90.8, 90.1, 90.5]]), anchor: 2, at: 3 },
];

/** Every (chart, cursor) where the anchor's expansion is visible, both price directions. */
function* moments() {
  for (const s of [...SCENARIOS, ...EDGES]) {
    for (const bars of [s.bars, mirror(s.bars)]) {
      for (let cursor = s.anchor; cursor < bars.length; cursor++) {
        const range = detectRange(bars, s.anchor, cursor);
        if (range) yield { key: s.key, bars, range, cursor };
      }
    }
  }
}

/** A small seeded generator (mulberry32), so the random charts are the same on every run. */
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * A random chart with the shapes that broke earlier rounds made common: runs of candles one way,
 * closes on the low or high, opens near the far end of a candle, gaps, whole and fractional prices.
 */
function randomChart(next: () => number, n: number): Bar[] {
  const whole = next() < 0.6;
  const round = (p: number) => (whole ? Math.round(p) : Math.round(p * 100) / 100);
  const bars: Bar[] = [];
  let close = 1000;
  let drift = 0;
  for (let i = 0; i < n; i++) {
    if (next() < 0.25) drift = (next() - 0.5) * 24;
    const open = round(next() < 0.06 ? close + (next() - 0.5) * 30 : close);
    const c = round(open + drift + (next() - 0.5) * 22);
    const up = next() < 0.18 ? 0 : next() * 10;
    const down = next() < 0.18 ? 0 : next() * 10;
    bars.push({ t: i * 300, open, close: c, high: round(Math.max(open, c) + up), low: round(Math.min(open, c) - down) });
    close = c;
  }
  return bars;
}

describe('shadow: the two ways the next candle can go', () => {
  it('holds every rule at every candle of the practice charts and the council’s edge charts', () => {
    let seen = 0;
    const decisions = new Set<StepKey>();
    for (const { key, bars, range, cursor } of moments()) {
      const sh = shadowAt(bars, range, cursor, opts);
      if (!sh) continue;
      seen++;
      decisions.add(sh.decision);
      expectHonest(`${key} @${cursor} ${range.dir} ${sh.decision}`, bars, range, cursor, sh);
    }
    expect(seen).toBeGreaterThan(40);
    expect([...decisions].sort()).toEqual(['csd', 'entry', 'eq', 'half', 'range'].sort());
  });

  it('holds every rule on 150 seeded random charts, both directions', { timeout: 20000 }, () => {
    const next = rng(20261115);
    const ropts = { minSize: 20, decimals: 2 };
    let shown = 0;
    let pending = 0;
    for (let chart = 0; chart < 150; chart++) {
      const base = randomChart(next, 30);
      for (const bars of [base, mirror(base)]) {
        for (let cursor = 2; cursor < bars.length; cursor++) {
          for (let end = Math.max(1, cursor - 6); end <= cursor; end++) {
            const range = detectRange(bars, end, cursor);
            if (!range || range.end !== end) continue;
            const now = readRange(bars, range, cursor, ropts);
            if (now.voidAt !== null || now.size < ropts.minSize || status(now, 'target') === 'pass') continue;
            if (!['range', 'half', 'csd', 'entry', 'eq'].some((k) => status(now, k as StepKey) === 'waiting')) continue;
            pending++;
            const sh = shadowAt(bars, range, cursor, ropts);
            if (!sh) continue;
            shown++;
            expectHonest(`random #${chart} @${cursor} ${range.dir} ${sh.decision}`, bars, range, cursor, sh, ropts);
          }
        }
      }
    }
    // the honesty guard turns the shadow off only where a chart leaves no room, which is rare
    expect(pending).toBeGreaterThan(600);
    expect(shown / pending).toBeGreaterThan(0.95);
  });

  it('every council reproduction still shows a shadow where one is expected (and none where it is not)', () => {
    for (const e of EDGES) {
      for (const bars of [e.bars, mirror(e.bars)]) {
        const range = detectRange(bars, e.anchor, e.at)!;
        expect(range, `${e.key} range`).not.toBeNull();
        const sh = shadowAt(bars, range, e.at, opts);
        if (e.off) expect(sh, `${e.key} off`).toBeNull();
        else expect(sh, `${e.key} shown`).not.toBeNull();
      }
    }
  });

  it('a range set by hand: no shadow while its end is the last candle (the next candle settles it either way)', () => {
    const s = scenario('scalp-only');
    for (const bars of [s.bars, mirror(s.bars)]) {
      const manual = rangeOf(bars, 5, 13, bars === s.bars ? 'down' : 'up');
      expect(shadowAt(bars, manual, 13, { ...opts, manual: true }, { kind: 'manual', start: 5, end: 13, dir: manual.dir })).toBeNull();
      // by the rule, the same moment still has both branches, and B extends from the same start
      const ruled = detectRange(bars, 8, 8)!;
      const sr = shadowAt(bars, ruled, 8, opts)!;
      expect(sr.b.after.range.start).toBe(ruled.start);
    }
  });

  it('on random hand-set ranges every branch is exactly what the tab would read once the ghost is real', { timeout: 20000 }, () => {
    const next = rng(77);
    const mopts = { minSize: 20, decimals: 2, manual: true };
    let shown = 0;
    for (let chart = 0; chart < 60; chart++) {
      const base = randomChart(next, 24);
      for (const bars of [base, mirror(base)]) {
        for (let cursor = 3; cursor < bars.length; cursor++) {
          const end = cursor - Math.floor(next() * 4);
          const start = Math.max(0, end - 1 - Math.floor(next() * 4));
          if (end <= start) continue;
          const dir = bars[end]!.close < bars[end]!.open ? 'down' : 'up';
          const pick: RangePick = { kind: 'manual', start, end, dir };
          const range = pickRange(bars, cursor, pick)!;
          const sh = shadowAt(bars, range, cursor, mopts, pick);
          if (!sh) continue;
          shown++;
          expect(sh.decision, 'never the range decision on a hand-set range').not.toBe('range');
          expectHonest(`manual #${chart} ${start}..${end} @${cursor} ${dir} ${sh.decision}`, bars, range, cursor, sh, mopts);
          for (const br of [sh.a, sh.b]) {
            // what the tab would pick and read once the ghost printed is exactly this branch's read
            const ext = [...bars.slice(0, cursor + 1), br.candle];
            const tabRange = pickRange(ext, cursor + 1, pick)!;
            expect([tabRange.start, tabRange.end], `manual #${chart} ${br.key} range`).toEqual([br.after.range.start, br.after.range.end]);
            expect(br.after.verdict, `manual #${chart} ${br.key} verdict`).toEqual(readRange(ext, tabRange, cursor + 1, mopts).verdict);
          }
        }
      }
    }
    expect(shown).toBeGreaterThan(100);
  });

  it('live, nothing pinned: every branch is read on the range the tab would pick once the ghost printed', { timeout: 20000 }, () => {
    const next = rng(4242);
    const lopts = { minSize: 20, decimals: 2 };
    const pick: RangePick = { kind: 'latest', minSize: 20 };
    let shown = 0;
    let pending = 0;
    for (let chart = 0; chart < 100; chart++) {
      const base = randomChart(next, 30);
      for (const bars of [base, mirror(base)]) {
        for (let cursor = 3; cursor < bars.length; cursor++) {
          const range = pickRange(bars, cursor, pick);
          if (!range) continue;
          const now = readRange(bars, range, cursor, lopts);
          if (now.voidAt !== null || now.size < 20 || status(now, 'target') === 'pass') continue;
          if (!['range', 'half', 'csd', 'entry', 'eq'].some((k) => status(now, k as StepKey) === 'waiting')) continue;
          pending++;
          const sh = shadowAt(bars, range, cursor, lopts, pick);
          if (!sh) continue;
          shown++;
          expectHonest(`live #${chart} @${cursor} ${range.dir} ${sh.decision}`, bars, range, cursor, sh, lopts);
          for (const br of [sh.a, sh.b]) {
            const ext = [...bars.slice(0, cursor + 1), br.candle];
            const tabRange = pickRange(ext, cursor + 1, pick)!;
            expect([tabRange.start, tabRange.end, tabRange.dir], `live #${chart} ${br.key} range`).toEqual([range.start, range.end, range.dir]);
            expect(br.after.verdict, `live #${chart} ${br.key} verdict`).toEqual(readRange(ext, tabRange, cursor + 1, lopts).verdict);
          }
        }
      }
    }
    expect(pending).toBeGreaterThan(300);
    expect(shown / pending).toBeGreaterThan(0.85);
  });

  it('live: a ghost that would make the tab switch to a newer range turns the shadow off (a reviewer\u2019s chart)', () => {
    const base = ohlc([
      [1000, 1000, 982, 991], [991, 996, 981, 990], [990, 993, 979, 986], [986, 996, 962, 969], [969, 974, 963, 968],
      [968, 976, 949, 958], [958, 966, 943, 944], [944, 969, 939, 962], [962, 972, 952, 967],
    ]);
    const pick: RangePick = { kind: 'latest', minSize: 20 };
    for (const bars of [base, mirror(base)]) {
      const range = pickRange(bars, 8, pick)!;
      expect([range.start, range.end]).toEqual([0, 6]);
      expect(shadowAt(bars, range, 8, opts, pick)).toBeNull();
    }
  });

  it('holds its conditions when the last candle is tiny next to the recent candle size', () => {
    const tight = EDGES.find((e) => e.key === 'tight')!.bars;
    for (const bars of [tight, mirror(tight)]) {
      const range = detectRange(bars, 2)!;
      expect(range).toMatchObject({ start: 1, end: 2 });
      const sh = shadowAt(bars, range, 3, opts)!;
      expect(sh.decision).toBe('half');
      expect(status(sh.a.after, 'csd')).toBe('waiting');
    }
  });

  it('the hover text marks every ghost as an illustration', () => {
    for (const { bars, range, cursor } of moments()) {
      const sh = shadowAt(bars, range, cursor, opts);
      if (!sh) continue;
      for (const br of [sh.a, sh.b]) expect(shadowTitle(sh, br)).toContain('illustration, not a forecast');
    }
  });

  it('B at 50% is the rejection: it tags 50% and closes back under it', () => {
    const sh = at('olr-hold', 8)!;
    expect(sh.decision).toBe('half');
    expect(sh.question).toBe('Next candle at 50% (21,572)');
    expect(sh.b.candle.high).toBeGreaterThanOrEqual(21572);
    expect(sh.b.candle.close).toBeLessThan(21572);
    expect(sh.b).toMatchObject({ title: 'If it rejects 50%', tone: 'bad' });
    expect(sh.a).toMatchObject({ short: 'Above 50%', tone: 'good' });
    expect(consequence(sh, sh.b)).toBe('No change: still Watch, long. Wait for a close above 50% of the last candle (21,572).');
    expect(consequence(sh, sh.a)).toBe('Watch, long. Wait for CSD: a close above 21,581.');
  });

  it('B after CSD runs without a pullback: the rules say do not chase', () => {
    const sh = at('scalp-only', 10)!;
    expect(sh.decision).toBe('entry');
    expect(consequence(sh, sh.b)).toBe('Long idea. No pullback below 21,460 yet: do not chase. Wait for it; stop past 21,440.');
  });

  it('an expansion running on is neither good nor bad, and is never called "no change"', () => {
    const sh = at('scalp-only', 8)!;
    expect(sh.decision).toBe('range');
    expect(sh.b).toMatchObject({ short: 'Extends', tone: 'neutral' });
    expect(sh.b.after.range.end).toBe(9);
    expect(consequence(sh, sh.b)).toBe('Expansion running. No range until a candle stops closing below.');
  });

  it('words flip for the short side', () => {
    const csd = at('short-mirror', 6)!;
    expect(csd.decision).toBe('csd');
    expect(csd.a).toMatchObject({ short: 'Below CSD', title: 'If it closes below CSD (21,823)' });
    expect(consequence(csd, csd.a)).toMatch(/^Short idea\./);
    const fill = at('short-mirror', 7)!;
    expect(fill.decision).toBe('entry');
    expect(fill.a).toMatchObject({ short: 'Pulls back', title: 'If it pulls back above 21,815' });
    expect(consequence(fill, fill.b)).toBe('Short idea. No pullback above 21,815 yet: do not chase. Wait for it; stop past 21,842.');
  });

  it('B at EQ keeps the hold away even when a gap left CSD past EQ', () => {
    const gap = EDGES.find((e) => e.key === 'gap-past-eq')!.bars;
    for (const bars of [gap, mirror(gap)]) {
      const range = detectRange(bars, 2)!;
      const sh = shadowAt(bars, range, 5, opts)!;
      expect(sh.decision).toBe('eq');
      expect(status(sh.a.after, 'eq')).toBe('pass');
      expect(sh.b.after.verdict.word).toBe('Scalp only');
    }
  });

  it('a candle closing on the range low gets a wick that ends on it, not past it', () => {
    for (const key of ['close-on-low', 'close-on-low-2']) {
      const base = EDGES.find((e) => e.key === key)!.bars;
      for (const bars of [base, mirror(base)]) {
        const range = detectRange(bars, 2)!;
        const sh = shadowAt(bars, range, 2, opts)!;
        expect(sh.decision).toBe('range');
        if (range.dir === 'down') expect(sh.a.candle.low).toBe(range.low);
        else expect(sh.a.candle.high).toBe(range.high);
        expect(status(sh.a.after, 'olr')).not.toBe('pass');
      }
    }
  });

  it('says why it is off, for each reason', () => {
    const why = (key: string, cursor: number, min = 30) => {
      const sc = scenario(key);
      const range = detectRange(sc.bars, sc.anchor, cursor)!;
      return explainShadow(sc.bars, range, cursor, { ...opts, minSize: min }, { kind: 'anchor', at: range.end }).off;
    };
    expect(why('void', 12)).toBe('void');
    expect(why('too-small', 4)).toBe('small');
    expect(why('olr-hold', 12)).toBe('held');
    expect(why('olr-hold', 15)).toBe('target');
    const past = EDGES.find((e) => e.key === 'csd-past-target')!.bars;
    expect(explainShadow(past, detectRange(past, 2)!, 4, opts, { kind: 'anchor', at: 2 }).off).toBe('past-target');
    const sc = scenario('scalp-only');
    const manual = rangeOf(sc.bars, 5, 13, 'down');
    expect(explainShadow(sc.bars, manual, 13, opts, { kind: 'manual', start: 5, end: 13, dir: 'down' }).off).toBe('manual');
    const live = ohlc([
      [1000, 1000, 982, 991], [991, 996, 981, 990], [990, 993, 979, 986], [986, 996, 962, 969], [969, 974, 963, 968],
      [968, 976, 949, 958], [958, 966, 943, 944], [944, 969, 939, 962], [962, 972, 952, 967],
    ]);
    const lp: RangePick = { kind: 'latest', minSize: 20 };
    expect(explainShadow(live, pickRange(live, 8, lp)!, 8, opts, lp).off).toBe('switch');
    expect(explainShadow(sc.bars, detectRange(sc.bars, 8, 10)!, 10, opts, { kind: 'anchor', at: 8 }).off).toBeNull();
  });

  it('is off when nothing is pending or nothing honest can be drawn', () => {
    expect(at('void', 12)).toBeNull();
    expect(at('too-small', 7)).toBeNull();
    expect(at('olr-hold', 12)).toBeNull();
    expect(at('olr-hold', 15)).toBeNull();
    // the CSD candle closed past the target: price is already there
    const past = EDGES.find((e) => e.key === 'csd-past-target')!.bars;
    for (const bars of [past, mirror(past)]) expect(shadowAt(bars, detectRange(bars, 2)!, 4, opts)).toBeNull();
  });

  it('is off once the target has traded, even when the entry never filled', () => {
    const bars: Bar[] = [
      ...scenario('no-chase').bars.slice(0, 7),
      { t: 0, open: 21281, high: 21296, low: 21282, close: 21294 },
      { t: 0, open: 21294, high: 21320, low: 21290, close: 21318 },
    ].map((b, i) => ({ ...b, t: i * 60 }));
    const range = detectRange(bars, 5)!;
    const now = readRange(bars, range, 8, opts);
    expect(status(now, 'entry')).toBe('waiting');
    expect(status(now, 'target')).toBe('pass');
    expect(shadowAt(bars, range, 8, opts)).toBeNull();
  });
});
