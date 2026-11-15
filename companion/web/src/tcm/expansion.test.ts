import { describe, expect, it } from 'vitest';
import { detectRange, latestRange, rangeOf, readRange, type Bar, type Reading, type StepKey } from './expansion';
import { SCENARIOS } from './scenarios';

const opts = { minSize: 30, decimals: 0 };
const scenario = (key: string) => SCENARIOS.find((s) => s.key === key)!;
const status = (r: Reading, key: StepKey) => r.steps.find((s) => s.key === key)?.status;
const at = (r: Reading, key: StepKey) => r.steps.find((s) => s.key === key)?.at;

/** Read a scenario at its anchor with every candle shown. */
function readAll(key: string): Reading {
  const s = scenario(key);
  const range = detectRange(s.bars, s.anchor)!;
  return readRange(s.bars, range, s.bars.length - 1, opts);
}

const bar = (open: number, high: number, low: number, close: number, i = 0): Bar => ({ t: i * 300, open, high, low, close });
const mirror = (bars: Bar[]): Bar[] => bars.map((b) => ({ t: b.t, open: -b.open, close: -b.close, high: -b.low, low: -b.high }));

describe('finding the expansion', () => {
  it('runs from the first to the last candle closing beyond the one before, from any of its candles', () => {
    const s = scenario('scalp-only');
    for (const i of [6, 7, 8]) expect(detectRange(s.bars, i)).toMatchObject({ dir: 'down', start: 6, end: 8, high: 21494, low: 21440, eq: 21467, half: 21449, csd: 21455 });
  });

  it('needs two candles: one big candle is not an expansion', () => {
    const bars = [bar(10, 11, 9, 10.5), bar(10.5, 10.6, 5, 5.5), bar(5.5, 7, 5.2, 6.8)];
    expect(detectRange(bars, 1)).toBeNull();
  });

  it('ignores a doji', () => {
    expect(detectRange([bar(10, 11, 9, 10)], 0)).toBeNull();
  });

  it('does not look past the cursor', () => {
    const s = scenario('scalp-only');
    expect(detectRange(s.bars, 7, 7)).toMatchObject({ start: 6, end: 7 });
    expect(detectRange(s.bars, 8, 7)).toBeNull();
  });

  it('reads an up expansion the same way', () => {
    expect(detectRange(scenario('short-mirror').bars, 4)).toMatchObject({ dir: 'up', start: 3, end: 5, high: 21842, low: 21784, csd: 21823 });
  });

  it('finds the latest confirmed expansion, skipping ones under the minimum size', () => {
    const s = scenario('void');
    // the rally out of the second range is itself an up expansion
    expect(latestRange(s.bars)).toMatchObject({ dir: 'up', start: 8, end: 11 });
    expect(latestRange(s.bars, 9)).toMatchObject({ dir: 'down', start: 5, end: 7 });
    expect(latestRange(s.bars, 6)).toMatchObject({ start: 1, end: 3 });
    expect(latestRange(s.bars, 12, 1000)).toBeNull();
    // at candle 6 the first range has been closed through: alive skips it
    expect(latestRange(s.bars, 6, 0, true)).toBeNull();
    expect(latestRange(s.bars, 9, 0, true)).toMatchObject({ start: 5, end: 7 });
  });
});

describe('reading the range candle by candle', () => {
  it('scalp only: 50%, then CSD with a big wick, filled, but no close above EQ', () => {
    const r = readAll('scalp-only');
    expect(at(r, 'range')).toBe(9);
    expect(at(r, 'half')).toBe(9);
    expect(at(r, 'csd')).toBe(10);
    expect(r.steps.find((s) => s.key === 'entry')!.detail).toMatch(/^Big upper wick/);
    expect(at(r, 'entry')).toBe(11);
    expect(status(r, 'eq')).toBe('fail');
    expect(at(r, 'eq')).toBe(13);
    expect(r.verdict.word).toBe('Scalp only');
    expect(r).toMatchObject({ entry: 21460, stop: 21440, risk: 20 });
  });

  it('OLR then CSD with no wick, held above EQ to the range high', () => {
    const r = readAll('olr-hold');
    expect(at(r, 'olr')).toBe(9);
    expect(at(r, 'csd')).toBe(10);
    expect(r.events.find((e) => e.key === 'csd')!.label).toBe('50% + CSD');
    expect(r.steps.find((s) => s.key === 'entry')!.detail).toMatch(/^Small upper wick/);
    expect(status(r, 'eq')).toBe('pass');
    expect(at(r, 'target')).toBe(14);
    expect(r.verdict.word).toBe('Target reached');
    expect(r.stop).toBe(21552);
  });

  it('no chase: the next candle did not dip, the fill comes later', () => {
    const s = scenario('no-chase');
    const range = detectRange(s.bars, s.anchor)!;
    const early = readRange(s.bars, range, 7, opts);
    expect(status(early, 'entry')).toBe('waiting');
    expect(early.steps.find((x) => x.key === 'entry')!.detail).toMatch(/do not chase/);
    expect(early.verdict.word).toBe('Long idea');
    const r = readAll('no-chase');
    expect(at(r, 'entry')).toBe(8);
    expect(r.verdict.word).toBe('Target reached');
  });

  it('short mirror: the same rules, prices and words flipped', () => {
    const r = readAll('short-mirror');
    expect(r.idea).toBe('short');
    expect(at(r, 'half')).toBe(6);
    expect(at(r, 'csd')).toBe(7);
    expect(at(r, 'entry')).toBe(8);
    expect(status(r, 'eq')).toBe('pass');
    expect(at(r, 'target')).toBe(10);
    expect(r).toMatchObject({ entry: 21815, stop: 21842, risk: 27 });
    expect(r.levels.find((l) => l.key === 'csd')!.price).toBe(21823);
    expect(r.steps.find((s) => s.key === 'csd')!.detail).toMatch(/closed below 21,823/);
    expect(r.events.find((e) => e.key === 'csd')!.above).toBe(false);
  });

  it('a mirrored chart gives the same steps at the same candles', () => {
    for (const s of SCENARIOS) {
      const down = readRange(s.bars, detectRange(s.bars, s.anchor)!, s.bars.length - 1, opts);
      const flipped = mirror(s.bars);
      const up = readRange(flipped, detectRange(flipped, s.anchor)!, s.bars.length - 1, opts);
      expect(up.steps.map((x) => [x.key, x.status, x.at])).toEqual(down.steps.map((x) => [x.key, x.status, x.at]));
      expect(up.entry === null ? null : -up.entry).toEqual(down.entry);
    }
  });

  it('too small: the size rule fails and the verdict says watch', () => {
    const r = readAll('too-small');
    expect(r.size).toBe(20);
    expect(status(r, 'size')).toBe('fail');
    expect(r.verdict.word).toBe('Range too small');
    expect(readRange(scenario('too-small').bars, r.range, 7, { ...opts, minSize: 15 }).verdict.word).not.toBe('Range too small');
  });

  it('void: a close through the range low ends it and stops the waiting steps', () => {
    const r = readAll('void');
    expect(r.voidAt).toBe(6);
    expect(status(r, 'half')).toBe('pass');
    expect(status(r, 'csd')).toBe('na');
    expect(r.steps.at(-1)!.key).toBe('void');
    expect(r.verdict.word).toBe('Range void');
    const next = readRange(scenario('void').bars, detectRange(scenario('void').bars, 7)!, 12, opts);
    expect(next.verdict.word).toBe('Target reached');
  });

  it('says when the range was set by hand', () => {
    const s = scenario('void');
    const r = readRange(s.bars, rangeOf(s.bars, 4, 7, 'down'), 12, { ...opts, manual: true });
    expect(r.steps[0]!.detail).toBe('Set by hand: 4 candles, 09:50 to 10:05.');
  });

  it('waits while the expansion is still running', () => {
    const s = scenario('scalp-only');
    const r = readRange(s.bars, detectRange(s.bars, 8, 8)!, 8, opts);
    expect(status(r, 'range')).toBe('waiting');
    expect(r.verdict.word).toBe('Expansion running');
    expect(r.events).toEqual([]);
  });

  it('every scenario reads at its start without error and names its video timestamp', () => {
    for (const s of SCENARIOS) {
      expect(s.ref).toMatch(/^\d{2}:\d{2}$/);
      const range = detectRange(s.bars, s.anchor, Math.max(s.start, s.anchor));
      expect(range, s.key).not.toBeNull();
      expect(readRange(s.bars, range!, Math.max(s.start, s.anchor), opts).steps.length).toBeGreaterThan(5);
    }
  });
});
