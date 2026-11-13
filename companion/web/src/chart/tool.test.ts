import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { parseRealSnapshot } from '../demo/real';
import type { Tool } from '../wire';
import { TOOL_PRIORITY, labelPriority, placeChoices } from './marks';
import { captionFits, captionText, chooseLabel, outcomePrice, toolLineLabels, toolLineStyle, toolText } from './tool';

const toolOf = (name: string): Tool =>
  parseRealSnapshot(readFileSync(new URL(`../demo/${name}.json`, import.meta.url), 'utf8')).view!.charts.find((c) => c.role === 'entry')!.tool!;
const planned = toolOf('real-planned');
const triggered = toolOf('real-triggered');
const line = (tool: Tool, role: 'entry' | 'stop' | 'target') => tool.lines.find((l) => l.role === role)!;
const on = { named: true, captionShown: true };

describe('tool line labels', () => {
  it('offer the names fullest first when the zone shows its caption', () => {
    expect(toolLineLabels(planned, line(planned, 'target'), on)).toEqual(['Target 2.00R +58.50', 'Target 2.00R', 'Target']);
    expect(toolLineLabels(planned, line(planned, 'entry'), on)).toEqual(['Planned short entry', 'Planned entry', 'Entry']);
  });

  it('use the worded names, without the middle dot, when the zone has no room for its caption', () => {
    expect(toolLineLabels(planned, line(planned, 'stop'), { named: true, captionShown: false })).toEqual(['Stop, risk −29.25', 'Stop, risk', 'Stop']);
    // The entry has no zone of its own: no worded form.
    expect(toolLineLabels(planned, line(planned, 'entry'), { named: true, captionShown: false })[0]).toBe('Planned short entry');
  });

  it('keep only the bare role word when level names are off', () => {
    for (const role of ['entry', 'stop', 'target'] as const) {
      expect(toolLineLabels(triggered, line(triggered, role), { named: false, captionShown: false })).toEqual([role.charAt(0).toUpperCase() + role.slice(1)]);
    }
  });

  it('carry the next step on the entry when the level the next step waits on is the entry', () => {
    const waiting = { ...planned, entry_note: 'Next: 5m close below' };
    const labels = toolLineLabels(waiting, line(waiting, 'entry'), on);
    expect(labels[0]).toBe('Planned short entry, next: 5m close below');
    expect(labels.slice(-2)).toEqual(['Next: 5m close below', 'Entry']);
  });

  it('take the fullest label that fits, and the bare word when none does', () => {
    const labels = toolLineLabels(triggered, line(triggered, 'target'), on);
    const width = (s: string) => s.length * 6;
    expect(chooseLabel(labels, (s) => width(s) <= 80)).toBe('Target 2.00R');
    expect(chooseLabel(labels, (s) => width(s) <= 200)).toBe('Target 2.00R +97.00');
    expect(chooseLabel(labels, () => false)).toBe('Target');
  });

  it('end a line whose outcome happened in lower case, as words, not a shout', () => {
    expect(toolText('Target 2.00R  +97.00 · HIT')).toBe('Target 2.00R +97.00, hit');
  });
});

describe('placing tool labels among the others', () => {
  const plot = { w: 300, h: 200 };
  it('falls back to a shorter wording when the fullest collides, before giving up', () => {
    const blocker = { x: 150, y: 50, w: 150, h: 13 };
    const full = { x: 120, y: 50, w: 176, h: 13 };
    const short = { x: 230, y: 50, w: 66, h: 13 };
    const res = placeChoices([{ choices: [{ candidates: [blocker] }] }, { choices: [{ candidates: [full] }, { candidates: [short] }] }], plot);
    expect(res[1]).toBeNull(); // the short wording sits on the blocker too
    // A blocker under the left half of the fullest wording only: the shorter one fits.
    const res2 = placeChoices([{ choices: [{ candidates: [{ x: 120, y: 50, w: 100, h: 13 }] }] }, { choices: [{ candidates: [full] }, { candidates: [short] }] }], plot);
    expect(res2[1]).toEqual({ choice: 1, box: short });
  });

  it('ranks the trade lines above every mark, then their captions, then next and waiting', () => {
    const marks = ['next', 'waiting', 'stop', 'entry', 'target', 'reference'].map(labelPriority);
    expect(Math.max(TOOL_PRIORITY.stop, TOOL_PRIORITY.entry, TOOL_PRIORITY.target)).toBeLessThan(TOOL_PRIORITY.caption);
    expect(TOOL_PRIORITY.caption).toBeLessThan(Math.min(...marks));
    expect(labelPriority('next')).toBe(labelPriority('waiting'));
  });
});

describe('captions', () => {
  it('read in sentence case', () => {
    expect(captionText(planned.captions.reward)).toBe('Planned reward 2.00R');
    expect(captionText(triggered.captions.risk)).toBe('Risk 1R');
  });

  it('show only in a zone tall enough to keep clear of the line labels, and wide enough for the words', () => {
    const text = { width: 110, height: 13 };
    expect(captionFits({ height: 60, width: 200 }, text)).toBe(true);
    expect(captionFits({ height: 40, width: 200 }, text)).toBe(false);
    expect(captionFits({ height: 60, width: 115 }, text)).toBe(false);
  });
});

describe('tool style', () => {
  it('is dashed while planned, and while the status is stale even when triggered', () => {
    expect(toolLineStyle(planned, 'stop', false).dashed).toBe(true);
    expect(toolLineStyle(triggered, 'stop', false).dashed).toBe(false);
    expect(toolLineStyle(triggered, 'stop', true).dashed).toBe(true);
  });

  it('draws the entry in the next style only when the next step waits on it', () => {
    expect(toolLineStyle(planned, 'entry', false).next).toBe(false);
    expect(toolLineStyle({ ...planned, entry_note: 'Next: 5m close below' }, 'entry', false).next).toBe(true);
    expect(toolLineStyle({ ...planned, entry_note: 'Next: 5m close below' }, 'stop', false).next).toBe(false);
  });

  it('puts the outcome diamond on the target or the stop, and nowhere while open', () => {
    expect(outcomePrice(triggered)).toBeNull();
    expect(outcomePrice({ ...triggered, outcome: 'target_reached' })).toBe(triggered.target);
    expect(outcomePrice({ ...triggered, outcome: 'stopped' })).toBe(triggered.stop);
  });
});
