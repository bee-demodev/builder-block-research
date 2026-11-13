import { describe, expect, it } from 'vitest';
import { validateFrame } from '../wire';
import { chartProblemView, errorStaleExtra, longView, snapshot, watchView } from './fixtures';

// Demo frames go through the same validator as live ones; if a fixture drifts from
// the contract the demo would silently drop it, so catch that here.
describe('demo fixtures', () => {
  const views = { watch: watchView(), long: longView(), chartProblem: chartProblemView() };

  it.each(Object.entries(views))('%s is a valid snapshot frame', (_name, view) => {
    const r = validateFrame(JSON.stringify(snapshot(1, view)));
    expect(r.ok ? 'ok' : r.reason).toBe('ok');
  });

  it('the error case is a valid snapshot frame', () => {
    expect(validateFrame(JSON.stringify(snapshot(2, null, errorStaleExtra))).ok).toBe(true);
  });

  it.each(Object.entries(views))('%s has ordered candles, one forming at the end, and mark indexes inside the candles', (_name, view) => {
    for (const chart of view.charts) {
      const ts = chart.candles.map((c) => c.t);
      expect([...ts].sort((a, b) => a - b)).toEqual(ts);
      expect(new Set(ts).size).toBe(ts.length);
      expect(chart.candles.filter((c) => c.forming)).toHaveLength(1);
      expect(chart.candles.at(-1)!.forming).toBe(true);
      for (const c of chart.candles) expect(c.low <= Math.min(c.open, c.close) && c.high >= Math.max(c.open, c.close)).toBe(true);
      for (const m of chart.marks) {
        for (const idx of [m.start, m.end]) if (idx !== null) expect(idx).toBeLessThan(chart.candles.length);
      }
    }
  });

  it('the watch sample includes a zone, a waiting level, a stop and a target', () => {
    const roles = watchView().charts.flatMap((c) => c.marks.map((m) => `${m.kind}:${m.role}`));
    expect(roles).toEqual(expect.arrayContaining(['zone:poi', 'level:waiting', 'level:stop', 'level:target', 'marker:confirm']));
  });

  it('the setup sample sweeps the level it marks and closes back above it', () => {
    const setup = watchView().charts.find((c) => c.role === 'setup')!;
    const sweep = setup.candles[53]!;
    expect(sweep.low).toBe(25398.75);
    expect(sweep.close).toBeGreaterThan(25412.5);
  });
});
