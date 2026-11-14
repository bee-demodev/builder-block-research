import { describe, expect, it } from 'vitest';
import type { Candle, Mark } from '../wire';
import { COLUMN_MAX, buildColumn, capBand, cappedRange, columnBars, columnNote, ltfSpan, numberedCandles, slotLogical } from './htf';

const H = 3600;
/** New York wall clock as if UTC, like the core's `t`. */
const at = (day: number, hour: number) => Date.UTC(2026, 10, day, hour) / 1000;

const candle = (t: number, low: number, high: number, extra: Partial<Candle> = {}): Candle => ({
  time: '',
  t,
  open: low,
  high,
  low,
  close: high,
  forming: false,
  label: '',
  ...extra,
});

/** Hourly bars from `from` to `to` (exclusive), skipping the 17:00 break and the weekend. */
function hourly(from: number, to: number): Candle[] {
  const out: Candle[] = [];
  for (let t = from; t < to; t += H) {
    const d = new Date(t * 1000);
    const dow = d.getUTCDay();
    const hour = d.getUTCHours();
    if (hour === 17) continue;
    if (dow === 6 || (dow === 5 && hour > 17) || (dow === 0 && hour < 18)) continue;
    out.push(candle(t, 100, 101));
  }
  return out;
}

// Daily candles open at 18:00 the evening before (Thu 12 to Mon 16 Nov 2026).
const daily = [
  candle(at(11, 18), 90, 120, { label: 'Nov 12' }), // Thu
  candle(at(12, 18), 95, 125, { label: 'Nov 13' }), // Fri, runs over the weekend
  candle(at(15, 18), 99, 110, { label: 'Nov 16', forming: true }), // Mon
];

const marker = (title: string, label: string, start: number): Mark => ({
  kind: 'marker',
  role: 'reference',
  label,
  title,
  price: 100,
  top: null,
  bottom: null,
  start,
  end: null,
});

describe('ltfSpan', () => {
  const ltf = hourly(at(12, 9), at(16, 9)); // Thu 09:00 .. Mon 08:00
  it('takes the bars from the open up to the next candle open', () => {
    const span = ltfSpan(ltf, daily[1]!.t, daily[2]!.t)!;
    expect(ltf[span.from]!.t).toBe(at(12, 18));
    expect(ltf[span.to]!.t).toBe(at(13, 16)); // Friday's last bar before the break
  });
  it('keeps the weekend inside the Friday candle and leaves no bar uncovered', () => {
    const fri = ltfSpan(ltf, daily[1]!.t, daily[2]!.t)!;
    const mon = ltfSpan(ltf, daily[2]!.t, Infinity)!;
    expect(mon.from).toBe(fri.to + 1);
    expect(mon.to).toBe(ltf.length - 1);
  });
  it('clips a candle that opened before the first bar loaded', () => {
    expect(ltfSpan(ltf, daily[0]!.t, daily[1]!.t)).toEqual({ from: 0, to: expect.any(Number) });
  });
  it('is null when no bar falls inside', () => {
    expect(ltfSpan(ltf, at(1, 0), at(2, 0))).toBeNull();
  });
});

describe('numberedCandles', () => {
  it('reads the core’s Bias Candle markers and ignores the rest', () => {
    const marks = [marker('Bias Candle 1', 'C1', 3), marker('Bias Candle 2', 'C2', 4), marker('Bias swing confirmed (CISD)', 'Bias CISD', 4)];
    expect([...numberedCandles(marks)]).toEqual([
      [3, 'C1'],
      [4, 'C2'],
    ]);
  });
  it('falls back to the number when the marker has no short label', () => {
    expect(numberedCandles([marker('Bias Candle 3', '', 9)]).get(9)).toBe('C3');
  });
});

describe('buildColumn', () => {
  const ltf = hourly(at(12, 9), at(16, 9));
  it('maps each daily candle to the 1h bars it covers, oldest first', () => {
    const col = buildColumn(ltf, daily, '1D');
    expect(col.timeframe).toBe('1D');
    expect(col.bars.map((b) => b.slot)).toEqual([0, 1, 2]);
    expect(col.bars[0]!.from).toBe(0);
    expect(col.bars[2]!.to).toBe(ltf.length - 1);
    for (let k = 1; k < col.bars.length; k++) expect(col.bars[k]!.from).toBe(col.bars[k - 1]!.to! + 1);
  });
  it('shows the last few candles and widens to reach a numbered one', () => {
    const many = Array.from({ length: 12 }, (_, i) => candle(at(1, 0) + i * 86400, 1, 2));
    expect(buildColumn(ltf, many, '1D', new Map(), 4).bars).toHaveLength(4);
    const labelled = buildColumn(ltf, many, '1D', new Map([[6, 'C1']]), 4);
    expect(labelled.bars).toHaveLength(6);
    expect(labelled.bars[0]!.label).toBe('C1');
    // A numbered candle further back than COLUMN_MAX is left out rather than crowding the pane.
    expect(buildColumn(ltf, many, '1D', new Map([[0, 'C1']]), 4).bars).toHaveLength(COLUMN_MAX);
  });
  it('gives a candle no span when its bars are not loaded', () => {
    const late = hourly(at(16, 0), at(16, 9));
    const col = buildColumn(late, daily, '1D');
    expect(col.bars[0]!.from).toBeNull();
    expect(col.bars[2]!.from).toBe(0);
  });
  it('is empty without candles', () => {
    expect(buildColumn([], daily, '1D').bars).toEqual([]);
    expect(buildColumn(ltf, [], '1D').bars).toEqual([]);
  });
});

describe('column geometry', () => {
  it('places slots right of the last bar, past the gap', () => {
    expect(slotLogical(99, 0)).toBeGreaterThan(99 + 2);
    expect(slotLogical(99, 1) - slotLogical(99, 0)).toBeCloseTo(2.5);
  });
  it('asks for room only when there is a column', () => {
    expect(columnBars(null)).toBe(0);
    expect(columnBars({ timeframe: '1D', bars: [] })).toBe(0);
    const col = buildColumn(hourly(at(12, 9), at(16, 9)), daily, '1D');
    expect(columnBars(col)).toBeGreaterThan(slotLogical(0, col.bars.length - 1));
  });
});

describe('the cap', () => {
  const ltf = [candle(at(16, 0), 100, 110), candle(at(16, 1), 104, 120)];
  it('lets the column widen the scale only a little past the 1h range', () => {
    const band = capBand(ltf)!;
    expect(band.lo).toBeCloseTo(100 - 3);
    expect(band.hi).toBeCloseTo(120 + 3);
    const col = { timeframe: '1D', bars: [{ candle: candle(at(15, 18), 60, 122), slot: 0, label: '', from: 0, to: 1 }] };
    expect(cappedRange(col, band)).toEqual({ lo: band.lo, hi: 122 });
  });
  it('notes the extremes that were cut, and nothing when it fits', () => {
    const band = capBand(ltf)!;
    const tall = { timeframe: '1D', bars: [{ candle: candle(at(15, 18), 60, 200), slot: 0, label: '', from: 0, to: 1 }] };
    expect(columnNote(tall, band)).toBe('1D high 200.00 and low 60.00 are past the scale');
    const low = { timeframe: '1D', bars: [{ candle: candle(at(15, 18), 60, 115), slot: 0, label: '', from: 0, to: 1 }] };
    expect(columnNote(low, band)).toBe('1D low 60.00 is past the scale');
    const fits = { timeframe: '1D', bars: [{ candle: candle(at(15, 18), 98, 115), slot: 0, label: '', from: 0, to: 1 }] };
    expect(columnNote(fits, band)).toBe('');
  });
});
