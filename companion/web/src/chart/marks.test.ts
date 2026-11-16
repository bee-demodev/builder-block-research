import { describe, expect, it } from 'vitest';
import { mergeCandle } from '../store';
import type { Candle, Mark } from '../wire';
import { diffCandles, distinctTags, initialWindowStart, labelPriority, markerTextX, markInRange, offScaleNotes, partitionMarks, placeLabels, layoutTags, layoutWithKeyTags, placePreferring, tickCovered } from './marks';

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

describe('placePreferring', () => {
  const plot = { w: 200, h: 100 };
  const box = (x: number, y: number, w = 40, h = 10) => ({ x, y, w, h });
  it('places a more important label before a lesser one takes its fallback spot', () => {
    const candle = box(0, 0, 30, 100);
    const stop = { choices: [{ candidates: [box(5, 10)] }] }; // its only spot is on the candle
    const reference = { choices: [{ candidates: [box(40, 10), box(120, 10)] }] }; // clear of the candle, but on the stop's spot
    const [s, r] = placePreferring([stop, reference], plot, [], [candle]);
    expect(s?.box).toEqual(box(5, 10)); // the stop keeps its place, on its halo
    expect(r?.box).toEqual(box(120, 10)); // the reference label moves on
  });
  it('prefers a spot clear of the candles when one exists', () => {
    const candle = box(0, 0, 30, 100);
    const [r] = placePreferring([{ choices: [{ candidates: [box(5, 10), box(120, 10)] }] }], plot, [], [candle]);
    expect(r?.box).toEqual(box(120, 10));
  });
  it('never covers a hard obstacle', () => {
    const line = box(0, 10, 200, 3);
    expect(placePreferring([{ choices: [{ candidates: [box(5, 8)] }] }], plot, [line], [])).toEqual([null]);
  });
});

describe('layoutTags', () => {
  it('keeps role tags where they are when they do not overlap, and hides a reference tag on one', () => {
    const tags = [
      { y: 100, quiet: false }, // stop
      { y: 200, quiet: false }, // target
      { y: 110, quiet: true }, // London H, on the stop: hidden
      { y: 150, quiet: true }, // Asia H, clear: drawn where it is
      { y: 160, quiet: true }, // Asia L, on Asia H: hidden
      { y: null, quiet: false }, // off the scale
    ];
    expect(layoutTags(tags, 18)).toEqual([100, 200, null, 150, null, null]);
  });
  it('spreads overlapping role tags around their centre, and judges reference tags against where they end up', () => {
    const tags = [
      { y: 100, quiet: false }, // entry
      { y: 104, quiet: false }, // stop, 4 px away: the two spread to 93 and 111
      { y: 126, quiet: true }, // clear of 104, but within 18 of the stop's new place at 111: hidden
      { y: 130, quiet: true }, // 19 below 111: drawn
    ];
    expect(layoutTags(tags, 18)).toEqual([93, 111, null, 130]);
  });
  it('merges groups that the spreading pushes into each other', () => {
    const out = layoutTags([{ y: 100, quiet: false }, { y: 101, quiet: false }, { y: 118, quiet: false }], 18);
    const ys = out as number[];
    expect(ys[1]! - ys[0]!).toBe(18);
    expect(ys[2]! - ys[1]!).toBe(18);
  });
});

describe('tickCovered', () => {
  it('hides a tick under a shown tag and keeps the rest', () => {
    expect(tickCovered(548, [545], 15)).toBe(true);
    expect(tickCovered(520, [545], 15)).toBe(false);
    expect(tickCovered(null, [545], 15)).toBe(false);
    expect(tickCovered(300, [], 15)).toBe(false);
  });
});

describe('layoutWithKeyTags', () => {
  it('gives the nearest key level the tag even when a farther, more senior one comes first', () => {
    // a weekly level 20 px above a daily one: both are drawn lines, but only one tag fits
    const tags = [
      { y: 140, quiet: false }, // a role tag (the entry)
      { y: 60, quiet: true, key: { side: 0 as const, order: 1 } }, // PWH, farther
      { y: 80, quiet: true, key: { side: 0 as const, order: 0 } }, // PDH, nearest
    ];
    expect(layoutWithKeyTags(tags, 22)).toEqual([140, null, 80]);
  });

  it('lets the next level stand in when the nearest has no room beside a role tag, one a side', () => {
    const tags = [
      { y: 100, quiet: false },
      { y: 110, quiet: true, key: { side: 1 as const, order: 0 } }, // under the role tag
      { y: 150, quiet: true, key: { side: 1 as const, order: 1 } },
      { y: 190, quiet: true, key: { side: 1 as const, order: 2 } },
      { y: 40, quiet: true, key: { side: 0 as const, order: 0 } },
    ];
    expect(layoutWithKeyTags(tags, 22)).toEqual([100, null, 150, null, 40]);
  });
});
