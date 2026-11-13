import { describe, expect, it } from 'vitest';
import { mergeCandle } from '../store';
import type { Candle, Mark } from '../wire';
import { diffCandles, distinctTags, initialWindowStart, labelPriority, markerTextX, markInRange, offScaleNotes, partitionMarks, placeLabels } from './marks';

const c = (t: number, low: number, high: number, forming = false): Candle => ({
  time: '',
  t,
  open: low,
  high,
  low,
  close: high,
  forming,
  label: '',
});

const level = (label: string, price: number): Mark => ({
  kind: 'level',
  role: 'target',
  label,
  title: label,
  price,
  top: null,
  bottom: null,
  start: 0,
  end: null,
});

describe('diffCandles', () => {
  const base = [c(1, 10, 12), c(2, 11, 13), c(3, 12, 14, true)];

  it('updates in place when a tick replaces the forming candle', () => {
    const next = mergeCandle(base, c(3, 12, 15, true));
    expect(diffCandles(base, next)).toEqual({ kind: 'update', from: 2 });
  });

  it('updates in place when a tick opens a new candle', () => {
    const next = mergeCandle(base, c(4, 14, 15, true));
    expect(diffCandles(base, next)).toEqual({ kind: 'update', from: 2 });
  });

  it('redraws for a new snapshot (new candle objects)', () => {
    expect(diffCandles(base, base.map((x) => ({ ...x })))).toEqual({ kind: 'reset' });
    expect(diffCandles([], base)).toEqual({ kind: 'reset' });
    expect(diffCandles(base, base.slice(0, 2))).toEqual({ kind: 'reset' });
  });

  it('does nothing when the candles did not change', () => {
    expect(diffCandles(base, base)).toEqual({ kind: 'none' });
    expect(diffCandles(base, base.slice())).toEqual({ kind: 'none' });
  });

  it('redraws rather than feeding the chart a bar that goes back in time', () => {
    expect(diffCandles(base, [base[0]!, base[1]!, c(2, 1, 2)])).toEqual({ kind: 'reset' });
    expect(diffCandles(base, [...base, c(3, 1, 2)])).toEqual({ kind: 'reset' });
  });
});

describe('partitionMarks / offScaleNotes', () => {
  const candles = [c(1, 100, 110), c(2, 105, 120)]; // range 100..120, reach 0.15 -> 3 points
  it('keeps nearby levels and lists distant ones as off the scale', () => {
    const ref = (label: string, price: number): Mark => ({ ...level(label, price), role: 'reference' });
    const p = partitionMarks(candles, [ref('Near', 122), ref('Far', 140), ref('Low', 80)]);
    expect(p.shown.map((m) => m.label)).toEqual(['Near']);
    expect(p.above.map((m) => m.label)).toEqual(['Far']);
    expect(p.below.map((m) => m.label)).toEqual(['Low']);
    expect(offScaleNotes(p)).toEqual(['Above the scale: Far at 140.00', 'Below the scale: Low at 80.00']);
  });

  it('always shows zones and markers', () => {
    const zone: Mark = { ...level('Z', 0), kind: 'zone', price: null, top: 999, bottom: 990 };
    expect(partitionMarks(candles, [zone]).shown).toEqual([zone]);
  });
});

describe('initialWindowStart', () => {
  const at = (start: number | null): Mark => ({ ...level('x', 1), start });
  it('opens on the last N candles', () => {
    expect(initialWindowStart(160, [], 40)).toBe(120);
    expect(initialWindowStart(30, [], 40)).toBe(0);
  });
  it('widens to include the start of every mark, a couple of candles before it', () => {
    expect(initialWindowStart(160, [at(100), at(150), at(null)], 40)).toBe(98);
    expect(initialWindowStart(160, [at(1)], 40)).toBe(0);
  });
});

describe('markInRange', () => {
  it('levels run to the right edge, markers sit on one candle, zones span start to end', () => {
    expect(markInRange({ ...level('l', 1), start: 10 }, 50, 60)).toBe(true);
    expect(markInRange({ ...level('l', 1), start: 70 }, 50, 60)).toBe(false);
    const marker: Mark = { ...level('m', 1), kind: 'marker', start: 40 };
    expect(markInRange(marker, 50, 60)).toBe(false);
    expect(markInRange({ ...marker, start: 55 }, 50, 60)).toBe(true);
    const zone: Mark = { ...level('z', 0), kind: 'zone', price: null, top: 2, bottom: 1, start: null, end: 40 };
    expect(markInRange(zone, 50, 60)).toBe(false);
    expect(markInRange({ ...zone, end: 52 }, 50, 60)).toBe(true);
  });
});

describe('labels', () => {
  it('ranks waiting, stop, entry, target, then the rest', () => {
    expect(['waiting', 'stop', 'entry', 'target', 'reference'].map((r) => labelPriority(r))).toEqual([0, 1, 2, 3, 4]);
  });

  it('places labels in order, tries the next spot on a collision, drops what does not fit', () => {
    const plot = { w: 300, h: 200 };
    const a = { x: 10, y: 50, w: 60, h: 13 };
    const below = { x: 10, y: 70, w: 60, h: 13 };
    expect(placeLabels([{ candidates: [a] }, { candidates: [a, below] }, { candidates: [a, below] }], plot)).toEqual([a, below, null]);
    expect(placeLabels([{ candidates: [{ x: 280, y: 10, w: 40, h: 13 }] }], plot)).toEqual([null]);
  });

  it('keeps marker text inside the plot, flipping left of the anchor near the right edge', () => {
    expect(markerTextX(100, 40, 300)).toBe(80);
    expect(markerTextX(290, 40, 300)).toBe(290 - 8 - 40);
    expect(markerTextX(5, 40, 300)).toBe(4);
  });

  it('shows one price tag per price, the more important role winning', () => {
    const tags = distinctTags(
      [
        { price: 25361.25, role: 'reference' },
        { price: 25361.25, role: 'stop' },
        { price: 25052.375, role: 'reference' },
      ],
      2,
    );
    expect(tags).toEqual([
      { price: 25361.25, role: 'stop' },
      { price: 25052.375, role: 'reference' },
    ]);
  });
});

describe('partitionMarks keeps the trade levels', () => {
  it('shows a target a full range away while a reference level that far is off the scale', () => {
    const candles = [c(1, 100, 110), c(2, 105, 120)]; // range 20
    const ref = { ...level('Far ref', 135), role: 'reference' };
    const p = partitionMarks(candles, [level('Target', 135), ref]);
    expect(p.shown.map((m) => m.label)).toEqual(['Target']);
    expect(p.above.map((m) => m.label)).toEqual(['Far ref']);
  });
});
