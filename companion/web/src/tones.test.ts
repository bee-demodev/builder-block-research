import { describe, expect, it } from 'vitest';
import { checkTotals, groupTally, hasDot, isStopLevel, markTone, orderGroups, rowFilter, splitColumns } from './tones';
import { watchView } from './demo/fixtures';
import type { CheckRow } from './wire';

describe('markTone', () => {
  it('maps fixed roles regardless of direction', () => {
    for (const d of ['', 'long', 'short'] as const) {
      expect(markTone('waiting', d)).toBe('watch');
      expect(markTone('next', d)).toBe('watch');
      expect(markTone('stop', d)).toBe('risk');
      expect(markTone('target', d)).toBe('reward');
      expect(markTone('confirm', d)).toBe('bull');
      expect(markTone('reference', d)).toBe('muted');
      expect(markTone('something-new', d)).toBe('muted');
    }
  });

  it('colours directional roles by the view direction', () => {
    for (const role of ['entry', 'poi', 'protected']) {
      expect(markTone(role, 'long')).toBe('long');
      expect(markTone(role, 'short')).toBe('short');
      expect(markTone(role, '')).toBe('muted');
    }
  });

  it('is case-insensitive about the role', () => {
    expect(markTone('Entry', 'long')).toBe('long');
    expect(markTone('NEXT', '')).toBe('watch');
  });
});

describe('checkTotals', () => {
  it('matches the sample verdict: 11 of 14', () => {
    const t = checkTotals(watchView().groups);
    expect(t).toEqual({ passed: 11, failed: 1, notEvaluated: 2, total: 14 });
  });
});

describe('checkTotals counts only the groups in play', () => {
  it('leaves out a path that is not in play', () => {
    const groups = watchView().groups.map((g, i) => (i === 0 ? { ...g, active: false } : g));
    expect(checkTotals(groups)).toEqual({ passed: 7, failed: 1, notEvaluated: 2, total: 10 });
  });
});

describe('groupTally', () => {
  it('gives a full and a short form, leaving out zero counts', () => {
    expect(groupTally({ passed: 2, failed: 1, not_evaluated: 0 })).toEqual({ full: '2 of 3 passed, 1 failed', short: '2 of 3, 1 failed' });
    expect(groupTally({ passed: 0, failed: 1, not_evaluated: 2 })).toEqual({ full: '0 of 3 passed, 1 failed, 2 not evaluated', short: '0 of 3, 1 failed' });
    expect(groupTally({ passed: 4, failed: 0, not_evaluated: 0 })).toEqual({ full: '4 of 4 passed', short: '4 of 4' });
  });
});

describe('orderGroups', () => {
  it('puts the groups in play first and keeps the order inside each part', () => {
    const gs = [
      { active: false, n: 1 },
      { active: true, n: 2 },
      { active: false, n: 3 },
      { active: true, n: 4 },
    ];
    const { inPlay, notInPlay } = orderGroups(gs);
    expect(inPlay.map((g) => g.n)).toEqual([2, 4]);
    expect(notInPlay.map((g) => g.n)).toEqual([1, 3]);
  });
});

describe('hasDot', () => {
  it('shows the status dot for live feed states only', () => {
    for (const s of ['live', 'stale', 'connecting', 'offline'] as const) expect(hasDot(s)).toBe(true);
    for (const s of ['history', 'paused', 'past'] as const) expect(hasDot(s)).toBe(false);
  });
});

describe('isStopLevel', () => {
  it('recognises stop rows by name only', () => {
    expect(isStopLevel({ name: 'Stop', price: '', note: '' })).toBe(true);
    expect(isStopLevel({ name: 'Initial stop', price: '', note: '' })).toBe(true);
    expect(isStopLevel({ name: 'Unstoppable target', price: '', note: '' })).toBe(false);
    expect(isStopLevel({ name: 'Target 1', price: '', note: '' })).toBe(false);
  });
});

describe('splitColumns', () => {
  const g = (n: number) => ({ rows: Array.from({ length: n }) });
  it('keeps order and balances rows', () => {
    const groups = [g(4), g(4), g(3), g(3)];
    const [l, r] = splitColumns(groups);
    expect(l).toEqual([groups[0], groups[1]]);
    expect(r).toEqual([groups[2], groups[3]]);
  });
  it('puts one long group alone when that balances best', () => {
    const groups = [g(10), g(3), g(3)];
    const [l, r] = splitColumns(groups);
    expect(l).toHaveLength(1);
    expect(r).toHaveLength(2);
  });
  it('handles zero and one group', () => {
    expect(splitColumns([])).toEqual([[], []]);
    expect(splitColumns([g(2)])[1]).toEqual([]);
  });
});

describe('rowFilter', () => {
  const row = (tags: string[], advisory = false): CheckRow => ({ key: 'k', status: 'pass', mark: '', label: '', detail: '', tags, advisory });
  it('sends advisory rows to the advisory toggle before anything else', () => {
    expect(rowFilter(row(['quality'], true))).toBe('advisory');
    expect(rowFilter(row(['Quality']))).toBe('quality');
    expect(rowFilter(row(['gate']))).toBe('core');
    expect(rowFilter(row([]))).toBe('core');
    expect(rowFilter(row(['quality', '1h']))).toBe('quality');
  });
});
