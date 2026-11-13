import { describe, expect, it, vi } from 'vitest';
import { parseServerFrame, validateFrame } from './wire';
import { snapshot, watchView } from './demo/fixtures';

const state = {
  symbol: 'NQ1!',
  stack: '1D / 1h / 5m',
  style: 'TTrades',
  data: 'TradingView Desktop',
  when: '2026-11-12T10:35:00-05:00',
  follow: true,
  auto_refresh: true,
  busy: false,
  live: true,
};
const options = { symbols: ['NQ1!'], stacks: ['1D / 1h / 5m'], timeframes: ['1D'], styles: ['TTrades'], data: ['TradingView Desktop'] };

describe('validateFrame', () => {
  it('accepts a hello frame', () => {
    const r = validateFrame(JSON.stringify({ type: 'hello', version: 1, options, state }));
    expect(r.ok && r.frame.type).toBe('hello');
  });

  it('accepts a full snapshot with a verdict and ignores unknown extra fields', () => {
    const frame = { ...snapshot(3, watchView()), future_field: 42 };
    const r = validateFrame(JSON.stringify(frame));
    expect(r.ok).toBe(true);
    if (r.ok && r.frame.type === 'snapshot') {
      expect(r.frame.view?.charts).toHaveLength(3);
      expect('future_field' in r.frame).toBe(false);
    }
  });

  it('names the path of the first bad field', () => {
    const view = watchView();
    const broken = { ...snapshot(1, view), view: { ...view, charts: [{ ...view.charts[0], candles: [{ ...view.charts[0]!.candles[0], close: '1' }] }] } };
    const r = validateFrame(JSON.stringify(broken));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain('snapshot.view.charts[0].candles[0].close');
  });

  it('rejects values outside the enums', () => {
    const r = validateFrame(JSON.stringify({ type: 'status', status: { state: 'sleeping', text: '', stale: false } }));
    expect(r.ok).toBe(false);
  });

  it('rejects missing fields, unknown types, non-JSON and other wire versions', () => {
    expect(validateFrame(JSON.stringify({ type: 'state', state: { ...state, busy: undefined } })).ok).toBe(false);
    expect(validateFrame(JSON.stringify({ type: 'bogus' })).ok).toBe(false);
    expect(validateFrame('{not json').ok).toBe(false);
    expect(validateFrame('[1,2]').ok).toBe(false);
    expect(validateFrame(JSON.stringify({ type: 'hello', version: 2, options, state })).ok).toBe(false);
  });

  it('rejects NaN-like numbers that JSON cannot carry but a buggy server might send as null', () => {
    const r = validateFrame(JSON.stringify({ type: 'tick', timeframe: '5m', last: null, candle: watchView().charts[0]!.candles[0] }));
    expect(r.ok).toBe(false);
  });

  it('normalises row tags given as a single string', () => {
    const view = watchView();
    const g = view.groups[0]!;
    const withStringTag = { ...view, groups: [{ ...g, rows: [{ ...g.rows[0]!, tags: 'gate' }] }] };
    const r = validateFrame(JSON.stringify({ ...snapshot(1, null), view: withStringTag }));
    expect(r.ok).toBe(true);
    if (r.ok && r.frame.type === 'snapshot') expect(r.frame.view?.groups[0]?.rows[0]?.tags).toEqual(['gate']);
  });
});

describe('parseServerFrame', () => {
  it('logs and returns null for a malformed frame instead of throwing', () => {
    const log = vi.fn();
    expect(parseServerFrame('{"type":"tick"}', log)).toBeNull();
    expect(log).toHaveBeenCalledOnce();
    expect(log.mock.calls[0]![0]).toMatch(/dropped malformed frame/);
  });
});
