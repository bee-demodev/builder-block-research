import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { Connection, type SocketLike } from './connection';
import { checkpointText, focusedStep, formatR, nextCheckpoint, planWords, sections, setSide, sideChoices, stepPrice, suggestionText, waitingText } from './decision';
import { longView, watchView } from './demo/fixtures';
import { parseRealSnapshot } from './demo/real';
import type { Options } from './wire';

const real = (name: string) => parseRealSnapshot(readFileSync(new URL(`./demo/${name}.json`, import.meta.url), 'utf8')).view!;
const planned = real('real-planned');
const triggered = real('real-triggered');

describe('the suggestion line', () => {
  it('reads the core banner in sentence case, without the middle dot', () => {
    expect(suggestionText(planned)).toBe('Watch, short');
    expect(suggestionText(triggered)).toBe('Trade short');
    expect(suggestionText({ suggestion: 'SHORT · TARGET REACHED', decision_word: '' })).toBe('Short, target reached');
    expect(suggestionText({ suggestion: '', decision_word: "DON'T TRADE" })).toBe("Don't trade");
  });
});

describe('what has to happen', () => {
  it('focuses the step marked next', () => {
    expect(focusedStep(planned.steps)?.number).toBe(2);
    expect(focusedStep(watchView().steps)?.label).toMatch(/the entry/);
  });

  it('focuses nothing once every step is done', () => {
    expect(triggered.steps.every((s) => s.status === 'done')).toBe(true);
    expect(focusedStep(triggered.steps)).toBeNull();
  });

  it('shows the waiting block while something is pending, and the plan instead of the levels', () => {
    expect(planned.waiting_for).not.toBe('');
    expect(sections(planned)).toEqual({ waiting: true, plan: true, levels: false });
    expect(triggered.has_levels).toBe(true);
    expect(sections({ ...triggered, waiting_for: '' })).toEqual({ waiting: false, plan: true, levels: false });
  });

  it('falls back to the levels when the core sends no plan', () => {
    const old = { ...watchView(), steps: [], plan: null };
    expect(sections(old)).toEqual({ waiting: true, plan: false, levels: true });
    expect(sections({ ...old, waiting_for: '' }).waiting).toBe(false);
  });

  it('waits on the core text first, then on the step marked next', () => {
    expect(waitingText(watchView())).toBe('A 5m close above 25,468.25');
    expect(waitingText({ ...watchView(), waiting_for: '' })).toBe('5m close above 25,468.25, after the low 25,398.75');
    expect(waitingText({ waiting_for: '', steps: triggered.steps })).toBe('');
  });

  it('prints a step price only when the step has one', () => {
    expect(planned.steps.map(stepPrice)).toEqual(['', '24,958.25', '']);
  });
});

describe('the session clock', () => {
  it('names the next checkpoint and how long until it', () => {
    expect(nextCheckpoint(9, 29)).toEqual({ time: '09:30', label: 'New York open', minutes: 1 });
    expect(nextCheckpoint(9, 30)?.time).toBe('09:45');
    expect(checkpointText(9, 50)).toBe('Next 10:00, new 4H and 1H candles, in 10 min');
    expect(checkpointText(7, 15)).toBe('Next 09:30, New York open, in 2 h 15 min');
  });

  it('says the window has closed after 11:00', () => {
    expect(nextCheckpoint(11, 0)).toBeNull();
    expect(checkpointText(14, 5)).toBe('His window closed at 11:00');
  });
});

describe('the plan block', () => {
  it('words a triggered plan with its time, last close and R', () => {
    expect(planWords(triggered.plan!)).toEqual({
      title: 'Short',
      state: 'Triggered 08:20',
      outcome: '',
      last: { price: '24,713.25', r: '+0.19R' },
      stage: '', // a snapshot from a core that predates the stage
      stageAlert: false,
      cost: '',
      size: '', // nor the size and the backtest record
      evidence: null,
    });
  });

  it('says how old a triggered plan is and flags a late one', () => {
    const plan = { ...longView().plan!, stage_label: 'late' as const, age_bars: 5 };
    expect(planWords(plan)).toMatchObject({ stage: 'Late · 5 bars', stageAlert: true });
    expect(planWords({ ...plan, stage_label: 'actionable', age_bars: 1 })).toMatchObject({ stage: 'Actionable · 1 bar', stageAlert: false });
    expect(planWords({ ...plan, stage_label: 'forming', age_bars: null }).stage).toBe('');
  });

  it('passes the stop size and cost line through', () => {
    expect(planWords(longView().plan!).cost).toBe('Stop 17% of ADR · costs 0.01R mini, 0.01R micro');
  });

  it('passes the dollar risk through and grades the setup while the trade is open', () => {
    const plan = longView().plan!;
    expect(planWords(plan).size).toBe('1 micro risks $141 · 1 mini $1,400');
    const best = { ...plan, evidence: { grade: 'best_measured' as const, label: 'Best-measured setup', line: '+0.07R a trade', exits: '', source: 's' } };
    expect(planWords(best).evidence).toEqual({ label: 'Best-measured setup', line: '+0.07R a trade', exits: '', source: 's', tone: 'reward' });
    const small = { ...best, evidence: { ...best.evidence, grade: 'small_stop' as const, label: 'Small stop' } };
    expect(planWords(small).evidence?.tone).toBe('watch');
    expect(planWords({ ...best, outcome: 'target_reached' as const }).evidence).toBeNull();
  });

  it('words a planned plan without a last close', () => {
    expect(planWords(planned.plan!)).toMatchObject({ title: 'Planned short', state: 'Planned', last: null });
  });

  it('names the outcome and its time once the trade is over', () => {
    const plan = { ...longView().plan!, outcome: 'stopped' as const, outcome_at: '2026-11-12T10:50:00-05:00' };
    expect(planWords(plan).outcome).toBe('Stopped 10:50');
  });

  it('writes R with a true minus sign and no negative zero', () => {
    expect(formatR(-1)).toBe('−1.00R');
    expect(formatR(-0.001)).toBe('+0.00R');
  });
});

describe('the side selector', () => {
  const options: Pick<Options, 'sides' | 'side_labels'> = { sides: ['', 'long', 'short'], side_labels: { '': 'Auto', long: 'Long', short: 'Short' } };

  it('shows the side the core reports, not the one last clicked', () => {
    expect(sideChoices(options, { side: 'short' }).map((c) => [c.label, c.pressed])).toEqual([
      ['Auto', false],
      ['Long', false],
      ['Short', true],
    ]);
    expect(sideChoices(options, null).some((c) => c.pressed)).toBe(false);
  });

  it('offers Auto, Long and Short before the first hello', () => {
    expect(sideChoices(null, null).map((c) => c.label)).toEqual(['Auto', 'Long', 'Short']);
  });

  it('sends set {side} and nothing else: the core re-checks by itself', () => {
    const sent: string[] = [];
    const socket: SocketLike = { onopen: null, onmessage: null, onclose: null, onerror: null, readyState: 1, send: (d) => sent.push(d), close: () => {} };
    const conn = new Connection(() => socket, () => {});
    conn.start();
    conn.send(setSide('short'));
    conn.send(setSide(''));
    expect(sent.map((s) => JSON.parse(s))).toEqual([
      { type: 'set', side: 'short' },
      { type: 'set', side: '' },
    ]);
    conn.stop();
  });
});
