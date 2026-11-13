import { describe, expect, it } from 'vitest';
import { axisLabel, formatMs, formatPrice, pathLine, plainText, priceDecimals, sentenceCase, splitStatus, statusParts, titleText, wallClock } from './format';

describe('sentenceCase', () => {
  it.each([
    ['WATCH', 'Watch'],
    ['TRADE LONG', 'Trade long'],
    ["DON'T TRADE", "Don't trade"],
    ['  trade short ', 'Trade short'],
    ['', ''],
  ])('%s -> %s', (input, out) => expect(sentenceCase(input)).toBe(out));
});

describe('splitStatus', () => {
  it('splits on the middle dot separator and drops empty parts', () => {
    expect(splitStatus('Live from TradingView · lag 1.2 s')).toEqual(['Live from TradingView', 'lag 1.2 s']);
    expect(splitStatus(' · Paused · ')).toEqual(['Paused']);
    expect(splitStatus('Live')).toEqual(['Live']);
  });
});

describe('wallClock', () => {
  it('reads New York wall time from the string, whatever the offset', () => {
    const w = wallClock('2026-11-12T10:35:00-05:00')!;
    expect(w.date).toBe('Thu 12 Nov 2026');
    expect(w.time).toBe('10:35');
    expect(w.local).toBe('2026-11-12T10:35');
    // a late-evening time must not roll into the next UTC day
    expect(wallClock('2026-07-03T23:50:00-04:00')!.date).toBe('Fri 3 Jul 2026');
  });

  it('returns null for text it cannot read', () => {
    expect(wallClock('')).toBeNull();
    expect(wallClock('yesterday')).toBeNull();
    expect(wallClock('2026-13-01T10:00')).toBeNull();
  });
});

describe('formatPrice / priceDecimals', () => {
  it('uses thousands separators and fixed decimals', () => {
    expect(formatPrice(25468.25)).toBe('25,468.25');
    expect(formatPrice(25540)).toBe('25,540.00');
    expect(formatPrice(1.23456, 4)).toBe('1.2346');
  });

  it('finds the decimals the data needs, never fewer than the minimum', () => {
    expect(priceDecimals([25468.25, 25540])).toBe(2);
    expect(priceDecimals([1.0845, 1.08451])).toBe(5);
    expect(priceDecimals([])).toBe(2);
  });

  it('formats timings', () => {
    expect(formatMs(184)).toBe('184 ms');
    expect(formatMs(1196)).toBe('1.2 s');
    expect(formatMs(null)).toBe('n/a');
  });
});

describe('axisLabel', () => {
  // `t` is New York wall time expressed as UTC seconds.
  const t = Date.UTC(2026, 10, 10, 9, 5) / 1000;
  it('labels intraday days with the weekday and daily charts with the month', () => {
    expect(axisLabel(t, 'day', true)).toBe('Tue 10');
    expect(axisLabel(t, 'day', false)).toBe('Nov 10');
    expect(axisLabel(t, 'time', true)).toBe('09:05');
  });
});

describe('plainText', () => {
  it('turns spaced middle dots and em dashes in server sentences into commas', () => {
    expect(plainText('Historical data (saved 1-minute bars) — not live TradingView')).toBe('Historical data (saved 1-minute bars), not live TradingView');
    expect(plainText('Bearish · Candle 3 forming')).toBe('Bearish, Candle 3 forming');
    expect(plainText('NQ  ·  2025-11-18 08:25 New York  ·  1D / 1h / 5m')).toBe('NQ, 2025-11-18 08:25 New York, 1D / 1h / 5m');
  });

  it('leaves prices, ranges and times alone', () => {
    const s = 'the 1h fair value gap 24,784.75–24,838.00 at 08:15, -12.50 pts';
    expect(plainText(s)).toBe(s);
    expect(plainText('2025-11-18 08:25')).toBe('2025-11-18 08:25');
    expect(plainText('a·b')).toBe('a·b');
  });
});

describe('titleText', () => {
  it('sentence-cases a heading and keeps codes with digits', () => {
    expect(titleText('CONTINUATION C2')).toBe('Continuation C2');
    expect(titleText('SHARED')).toBe('Shared');
    expect(titleText('Bias')).toBe('Bias');
  });
});

describe('pathLine', () => {
  it('builds the line from the fields that are there', () => {
    expect(pathLine({ path: 'CONTINUATION', bias: 'BEARISH', stage: 'C4' })).toBe('Continuation, bearish bias, stage C4');
    expect(pathLine({ path: 'REVERSAL', bias: 'BEARISH', stage: '' })).toBe('Reversal, bearish bias');
  });

  it('leaves out empty and placeholder fields', () => {
    expect(pathLine({ path: '—', bias: 'NEUTRAL', stage: '—' })).toBe('Neutral bias');
    expect(pathLine({ path: '', bias: '', stage: '' })).toBe('');
  });
});

describe('statusParts', () => {
  it('says "Saved history" when the history status carries no text', () => {
    expect(statusParts({ state: 'history', text: '' })).toEqual(['Saved history']);
    expect(statusParts({ state: 'history', text: 'Saved history · sample data' })).toEqual(['Saved history', 'sample data']);
    expect(statusParts({ state: 'live', text: '' })).toEqual([]);
  });
});
