// The validator against the core's own saved snapshots (tests/companion/fixtures),
// and against frames from a core that predates the fields added within version 1.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { validateFrame, type SnapshotFrame } from './wire';

const fixture = (name: string) => readFileSync(new URL(`../../../tests/companion/fixtures/${name}.json`, import.meta.url), 'utf8');
const parse = (raw: string): SnapshotFrame => {
  const r = validateFrame(raw);
  if (!r.ok) throw new Error(r.reason);
  if (r.frame.type !== 'snapshot') throw new Error('not a snapshot');
  return r.frame;
};

describe.each(['snapshot_v1', 'snapshot_v1_triggered', 'snapshot_v1_planned'])('core fixture %s', (name) => {
  const frame = parse(fixture(name));
  const view = frame.view!;

  it('validates, with steps, a plan and the tool on the entry chart only', () => {
    expect(view.steps.length).toBeGreaterThan(0);
    expect(view.plan).not.toBeNull();
    expect(view.charts.filter((c) => c.tool !== null).map((c) => c.role)).toEqual(['entry']);
    expect(frame.timing?.load_ms).toBeGreaterThan(0);
  });

  it('carries every tool line with names fullest first, ending on the bare role word', () => {
    const tool = view.charts.find((c) => c.role === 'entry')!.tool!;
    expect(tool.lines.map((l) => l.role).sort()).toEqual(['entry', 'stop', 'target']);
    for (const l of tool.lines) {
      expect(l.names.at(-1)!.toLowerCase()).toBe(l.role);
      expect(l.names_worded.at(-1)!.toLowerCase()).toBe(l.role);
    }
  });
});

describe('the planned fixture', () => {
  const view = parse(fixture('snapshot_v1_planned')).view!;
  it('reads the plan as planned and the next step with its price and its chart line', () => {
    expect(view.plan!.state).toBe('planned');
    expect(view.steps.map((s) => s.status)).toEqual(['blocked', 'next', 'later']);
    const next = view.steps.find((s) => s.status === 'next')!;
    expect(next.price).toBe(24958.25);
    const setup = view.charts.find((c) => c.timeframe === next.timeframe)!;
    expect(setup.marks.filter((m) => m.role === 'next').map((m) => m.price)).toEqual([24958.25]);
  });
});

describe('a frame from an older core', () => {
  const raw = JSON.parse(fixture('snapshot_v1_planned'));
  const strip = (o: Record<string, unknown>, keys: string[]) => Object.fromEntries(Object.entries(o).filter(([k]) => !keys.includes(k)));
  const old = {
    ...raw,
    timing: strip(raw.timing, ['load_ms']),
    view: {
      ...strip(raw.view, ['requested', 'idea', 'suggestion', 'suggestion_tone', 'idea_state', 'idea_alert', 'auto_note', 'steps', 'plan']),
      charts: raw.view.charts.map((c: Record<string, unknown>) => strip(c, ['tool'])),
    },
  };

  it('still parses; the new fields take their empty values and the decision stands in for the suggestion', () => {
    const view = parse(JSON.stringify(old)).view!;
    expect(view.steps).toEqual([]);
    expect(view.plan).toBeNull();
    expect(view.charts.every((c) => c.tool === null)).toBe(true);
    expect([view.suggestion, view.suggestion_tone]).toEqual(['WATCH', 'watch']);
    expect(parse(JSON.stringify(old)).timing!.load_ms).toBeNull();
  });

  it('reads a state and options without the side as Auto', () => {
    const state = { symbol: 'NQ', stack: 's', style: 'x', data: 'history', when: '', follow: true, auto_refresh: true, busy: false, live: false };
    const options = { symbols: [], stacks: [], timeframes: [], styles: [], data: [] };
    const r = validateFrame(JSON.stringify({ type: 'hello', version: 1, options, state }));
    expect(r.ok && r.frame.type === 'hello' && [r.frame.state.side, r.frame.options.sides, r.frame.options.side_labels.short]).toEqual(['', ['', 'long', 'short'], 'Short']);
  });
});

describe('tolerance and strictness inside the new shapes', () => {
  const raw = JSON.parse(fixture('snapshot_v1_triggered'));
  const entry = raw.view.charts.findIndex((c: { role: string }) => c.role === 'entry');
  const withTool = (patch: (tool: Record<string, unknown>) => Record<string, unknown>) => {
    const charts = [...raw.view.charts];
    charts[entry] = { ...charts[entry], tool: patch(charts[entry].tool) };
    return JSON.stringify({ ...raw, view: { ...raw.view, charts } });
  };

  it('ignores unknown keys in the tool and a step', () => {
    const steps = raw.view.steps.map((s: object) => ({ ...s, glyph: '✓' }));
    expect(validateFrame(JSON.stringify({ ...raw, view: { ...raw.view, steps } })).ok).toBe(true);
    expect(validateFrame(withTool((t) => ({ ...t, hatch: 'diagonal' }))).ok).toBe(true);
  });

  it('uses the plain names when a line has no worded ones', () => {
    const json = withTool((t) => ({ ...t, lines: (t.lines as Record<string, unknown>[]).map((l) => ({ ...l, names_worded: undefined })) }));
    const tool = parse(json).view!.charts[entry]!.tool!;
    for (const l of tool.lines) expect(l.names_worded).toEqual(l.names);
  });

  it('drops a frame whose step status or tool role is outside the contract, naming the field', () => {
    const steps = [{ ...raw.view.steps[0], status: 'maybe' }];
    const r1 = validateFrame(JSON.stringify({ ...raw, view: { ...raw.view, steps } }));
    expect(!r1.ok && r1.reason).toContain('snapshot.view.steps[0].status');
    const r2 = validateFrame(withTool((t) => ({ ...t, lines: [{ role: 'take-profit', price: 1, names: ['x'] }] })));
    expect(!r2.ok && r2.reason).toContain('.tool.lines[0].role');
  });
});
