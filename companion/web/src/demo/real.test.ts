// The REAL data case: a snapshot the core produced on saved history. These pin the
// problems real content exposed so they stay fixed.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { initialWindowStart, partitionMarks } from '../chart/marks';
import { pathLine, plainText, titleText } from '../format';
import { checkTotals, groupTally, orderGroups, rowFilter } from '../tones';
import { parseRealSnapshot } from './real';

const frame = parseRealSnapshot(readFileSync(new URL('./real-snapshot.json', import.meta.url), 'utf8'));
const view = frame.view!;

describe('real snapshot', () => {
  it('is a valid snapshot frame with a verdict', () => {
    expect(frame.type).toBe('snapshot');
    expect(view.groups).toHaveLength(9);
    expect(view.charts.every((c) => c.candles.length > 150)).toBe(true);
  });

  it('builds the path line from path, bias and stage', () => {
    expect([view.path, view.bias, view.stage]).toEqual(['CONTINUATION', 'BEARISH', 'C4']);
    expect(pathLine(view)).toBe('Continuation, bearish bias, stage C4');
  });

  it('counts only the groups in play', () => {
    const all = view.groups.reduce((n, g) => n + g.passed + g.failed + g.not_evaluated, 0);
    const t = checkTotals(view.groups);
    expect(t.total).toBeLessThan(all);
    expect(t).toEqual({ passed: 18, failed: 4, notEvaluated: 0, total: 22 });
  });

  it('lists the reversal groups, which are not in play, after the continuation ones', () => {
    const { inPlay, notInPlay } = orderGroups(view.groups);
    expect(inPlay.map((g) => titleText(g.title))).toEqual(['Shared', 'Continuation C1', 'Continuation C2', 'Continuation C3', 'Continuation C4']);
    expect(notInPlay.map((g) => titleText(g.title))).toEqual(['Reversal C1', 'Reversal C2', 'Reversal C3', 'Reversal C4']);
    expect(notInPlay.every((g) => g.collapsed)).toBe(true);
    expect(groupTally(view.groups.find((g) => g.name === 'reversal c4')!).short).toBe('0 of 3, 1 failed');
  });

  it('splits the joined tags so the Quality filter finds quality rows', () => {
    const rows = view.groups.flatMap((g) => g.rows);
    expect(view.groups.find((g) => g.name === 'continuation c1')!.rows[0]!.tags).toEqual(['gate', '1D']);
    expect(rows.filter((r) => rowFilter(r) === 'quality').length).toBeGreaterThan(5);
  });

  it('shows server sentences without raw separators', () => {
    expect(plainText(view.source_note)).toBe('Historical data (saved 1-minute bars), not live TradingView');
    for (const r of view.read) expect(plainText(r.headline)).not.toMatch(/ [·—] /);
  });

  it('opens each chart on a recent window that still holds every mark start', () => {
    for (const chart of view.charts) {
      const bars = chart.role === 'setup' ? 60 : 40;
      const from = initialWindowStart(chart.candles.length, chart.marks, bars);
      expect(chart.candles.length - from).toBeLessThan(80);
      for (const m of chart.marks) if (m.start !== null) expect(m.start).toBeGreaterThanOrEqual(from);
      // Nothing the core marked is pushed off the scale on this snapshot (the 5m
      // target sits well below the recent candles, but trade levels always show).
      expect(partitionMarks(chart.candles.slice(from), chart.marks).shown).toHaveLength(chart.marks.length);
    }
  });
});
