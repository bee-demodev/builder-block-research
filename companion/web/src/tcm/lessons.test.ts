import { describe, expect, it } from 'vitest';
import { detectRange, readRange } from './expansion';
import { LESSONS } from './lessons';

/** The expansion a lesson reads at a candle, as the tab picks it. */
const anchorAt = (key: string, cursor: number) => {
  const l = LESSONS.find((x) => x.key === key)!;
  return [...(l.next ?? [])].filter((n) => n.at <= cursor).pop()?.anchor ?? l.anchor;
};

/** Where each lesson ends up, read by the rules on its last candle: what its narration builds to. */
const ENDS: Record<string, string> = {
  'scalp-only': 'Scalp only',
  'too-small': 'Range too small',
  'no-chase': 'Target reached',
  'ob-candidate': 'Range void',
  void: 'Target reached',
  'h1-order-block': 'Target reached',
  'olr-hold': 'Target reached',
  'failure-swing-olr': 'Target reached',
  'zoom-fractal': 'Target reached',
  'fvg-open': 'Target reached',
  'fvg-closed': 'Target reached',
  'bearish-context': 'Range void',
  continuation: 'Target reached',
  'multi-candle-csd': 'Target reached',
  'failed-to-eq': 'Target reached',
  'inside-range': 'Long, hold',
  'short-mirror': 'Target reached',
  'gap-eq': 'Scalp only',
  'ny-session': 'Target reached',
  'nine-fifty-five': 'Target reached',
  heavy: 'Target reached',
  'no-trade': 'Watch, long',
};

describe('practice lessons', () => {
  it('cover the video in order, one lesson per situation, each with a timestamp', () => {
    expect(LESSONS).toHaveLength(22);
    expect(new Set(LESSONS.map((l) => l.key)).size).toBe(22);
    const minutes = LESSONS.map((l) => Number(l.ref.split(':')[0]) * 60 + Number(l.ref.split(':')[1]));
    expect([...minutes].sort((a, b) => a - b)).toEqual(minutes);
    expect(Object.keys(ENDS).sort()).toEqual(LESSONS.map((l) => l.key).sort());
  });

  it('are well formed: valid candles in time order, notes in order, drawings on the chart', () => {
    for (const l of LESSONS) {
      const n = l.bars.length;
      l.bars.forEach((b, i) => {
        expect(b.high, `${l.key} #${i} high`).toBeGreaterThanOrEqual(Math.max(b.open, b.close));
        expect(b.low, `${l.key} #${i} low`).toBeLessThanOrEqual(Math.min(b.open, b.close));
        if (i > 0) expect(b.t - l.bars[i - 1]!.t, `${l.key} #${i} time`).toBe(l.minutes * 60);
      });
      expect(l.start, `${l.key} start`).toBeLessThan(n);
      expect(l.notes.length, `${l.key} notes`).toBeGreaterThan(1);
      l.notes.forEach((note, i) => {
        expect(note.at, `${l.key} note ${i}`).toBeLessThan(n);
        if (i > 0) expect(note.at, `${l.key} note ${i} order`).toBeGreaterThan(l.notes[i - 1]!.at);
      });
      for (const m of l.marks ?? []) {
        const at = m.kind === 'time' || m.kind === 'tag' ? m.index : m.from;
        expect(at, `${l.key} ${m.label}`).toBeLessThan(n);
        if (m.kind === 'zone') expect(m.top, `${l.key} ${m.label}`).toBeGreaterThan(m.bottom);
        if (m.at !== undefined) expect(m.at, `${l.key} ${m.label} at`).toBeLessThan(n);
      }
      for (const nx of l.next ?? []) {
        expect(nx.anchor, `${l.key} next`).toBeLessThanOrEqual(nx.at);
        expect(detectRange(l.bars, nx.anchor, nx.at), `${l.key} next range`).not.toBeNull();
      }
    }
  });

  it('end where their narration says, by the rules', () => {
    for (const l of LESSONS) {
      const last = l.bars.length - 1;
      const range = detectRange(l.bars, anchorAt(l.key, last), last)!;
      const reading = readRange(l.bars, range, last, { minSize: l.minSize ?? 30, decimals: 0 });
      expect(reading.verdict.word, l.key).toBe(ENDS[l.key]);
    }
  });

  it('read an expansion at every candle from where it has formed', () => {
    for (const l of LESSONS) {
      for (let cursor = l.start; cursor < l.bars.length; cursor++) {
        const anchor = anchorAt(l.key, cursor);
        if (anchor > cursor) continue;
        // before its expansion has two candles a lesson shows the candles only; after that, a range
        if (cursor > anchor) expect(detectRange(l.bars, anchor, cursor), `${l.key} @${cursor}`).not.toBeNull();
      }
    }
  });

  it('a gap past EQ is not a close above it (the daily lesson)', () => {
    const l = LESSONS.find((x) => x.key === 'gap-eq')!;
    const range = detectRange(l.bars, l.anchor)!;
    const at8 = readRange(l.bars, range, 8, { minSize: 100, decimals: 0 });
    expect(at8.steps.find((s) => s.key === 'eq')!.status).toBe('waiting');
  });
});
