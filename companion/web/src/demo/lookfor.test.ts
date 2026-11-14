import { describe, expect, it, vi } from 'vitest';
import { parseServerFrame, validateFrame } from '../wire';
import { snapshot, watchView } from './fixtures';
import { LOOK_FOR_SHORT, lookForView } from './lookfor';

describe('look_for on the wire', () => {
  it('parses a full look_for', () => {
    const r = validateFrame(JSON.stringify(snapshot(1, lookForView())));
    expect(r.ok).toBe(true);
    if (r.ok && r.frame.type === 'snapshot') expect(r.frame.view?.look_for).toEqual(LOOK_FOR_SHORT);
  });

  it('reads null from a core that sends none or predates it', () => {
    const { look_for: _gone, ...older } = watchView();
    const r = validateFrame(JSON.stringify(snapshot(1, older as never)));
    expect(r.ok && r.frame.type === 'snapshot' && r.frame.view?.look_for).toBeNull();
  });

  it('a malformed look_for is logged and dropped, the frame is kept', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const view = { ...lookForView(), look_for: { ...LOOK_FOR_SHORT, options: [{ key: 'A', top: 'high' }] } };
    const frame = parseServerFrame(JSON.stringify(snapshot(2, view as never)), () => {});
    expect(frame?.type).toBe('snapshot');
    if (frame?.type === 'snapshot') {
      expect(frame.view?.look_for).toBeNull();
      expect(frame.view?.charts).toHaveLength(3);
    }
    expect(warn).toHaveBeenCalledOnce();
    warn.mockRestore();
  });
});

describe('the look-for sample', () => {
  const view = lookForView();
  const chart = (role: string) => view.charts.find((c) => c.role === role)!;

  it('builds each 1h candle of the morning from its 5m candles, so the panes agree', () => {
    const entry = chart('entry').candles;
    for (const h of chart('setup').candles.slice(-6)) {
      const inside = entry.filter((b) => b.t >= h.t && b.t < h.t + 3600);
      expect(inside.length).toBeGreaterThan(0);
      expect(h.high).toBe(Math.max(...inside.map((b) => b.high)));
      expect(h.low).toBe(Math.min(...inside.map((b) => b.low)));
      expect(h.close).toBe(inside.at(-1)!.close);
    }
  });

  it('builds the daily Candle 1, Candle 2 and forming Candle 3 from their sessions’ 1h candles', () => {
    const daily = chart('bias').candles;
    const hourly = chart('setup').candles;
    for (const d of daily.slice(-3)) {
      const next = daily[daily.indexOf(d) + 1];
      const inside = hourly.filter((b) => b.t >= d.t && (!next || b.t < next.t));
      expect(d.high).toBe(Math.max(...inside.map((b) => b.high)));
      expect(d.low).toBe(Math.min(...inside.map((b) => b.low)));
    }
    expect(daily.at(-1)!.forming).toBe(true);
  });

  it('matches its story: C2 took C1 high and closed back below; option A is an unfilled gap above price', () => {
    const daily = chart('bias').candles;
    const [c1, c2] = [daily.at(-3)!, daily.at(-2)!];
    expect(c2.high).toBeGreaterThan(c1.high);
    expect(c2.close).toBeLessThan(c1.high);
    const a = LOOK_FOR_SHORT.options[0]!;
    const after = chart('setup').candles.slice(36);
    expect(Math.max(...after.map((b) => b.high))).toBeLessThan(a.bottom);
    expect(LOOK_FOR_SHORT.target_price).toBe(c2.low);
  });
});
