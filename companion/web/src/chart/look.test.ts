import { describe, expect, it } from 'vitest';
import { LOOK_FOR_SHORT } from '../demo/lookfor';
import type { LookFor } from '../wire';
import { candleEmphasis, candleSteps, chosenOption, entryCaption, entryGeometry, lookDecimals, paneFocus, projectedCandles, setupCaption, zoneEdges } from './look';

const SHORT = LOOK_FOR_SHORT;
const A = SHORT.options[0]!; // 25,410 to 25,428

describe('chosenOption', () => {
  it('takes the pick, falls back to A, and is null without options', () => {
    expect(chosenOption(SHORT, 'B')?.key).toBe('B');
    expect(chosenOption(SHORT, 'Z')?.key).toBe('A');
    expect(chosenOption({ ...SHORT, options: [] }, 'A')).toBeNull();
  });
});

describe('zoneEdges', () => {
  it('a short waits for price to come up into the zone; a long for it to come down', () => {
    expect(zoneEdges(A, 'short')).toMatchObject({ near: 25410, far: 25428, dir: 1, h: 18 });
    expect(zoneEdges(A, 'long')).toMatchObject({ near: 25428, far: 25410, dir: -1, h: 18 });
  });
});

describe('projectedCandles', () => {
  it('C1 pushes into the zone and closes inside; C2 sweeps past its extreme and the far edge, then closes back', () => {
    const [c1, c2] = projectedCandles(A, 'short');
    expect(c1.open).toBeLessThan(A.bottom); // from outside
    expect(c1.close).toBeGreaterThan(A.bottom);
    expect(c1.close).toBeLessThan(A.top); // closes inside
    expect(c2.open).toBe(c1.close);
    expect(c2.high).toBeGreaterThan(Math.max(c1.high, A.top)); // the sweep
    expect(c2.close).toBeLessThan(c2.open); // closes back down
  });
  it('mirrors for a long', () => {
    const [c1, c2] = projectedCandles(A, 'long');
    expect(c1.open).toBeGreaterThan(A.top);
    expect(c2.low).toBeLessThan(Math.min(c1.low, A.bottom));
    expect(c2.close).toBeGreaterThan(c2.open);
  });
  it('every candle is a valid bar', () => {
    for (const dir of ['short', 'long'] as const) {
      for (const c of projectedCandles(A, dir)) {
        expect(c.high).toBeGreaterThanOrEqual(Math.max(c.open, c.close));
        expect(c.low).toBeLessThanOrEqual(Math.min(c.open, c.close));
      }
    }
  });
});

describe('entryGeometry', () => {
  it('puts the stop beyond the C2 sweep and the entry where C2 closes back, inside the box', () => {
    const [, c2] = projectedCandles(A, 'short');
    const g = entryGeometry(A, 'short');
    expect(g.stop).toBeGreaterThan(c2.high);
    expect(g.entry).toBeCloseTo(c2.close);
    expect(g.top).toBe(g.stop);
    expect(g.bottom).toBeLessThan(g.entry);
    const long = entryGeometry(A, 'long');
    expect(long.stop).toBeLessThan(A.bottom);
    expect(long.bottom).toBe(long.stop);
  });
});

describe('words', () => {
  it('names the box and the pane that is awaited now', () => {
    expect(setupCaption(SHORT, A)).toBe('A  look for 1h C1, then C2');
    expect(paneFocus(SHORT)).toEqual({ setup: true, entry: false });
    const entryNext: LookFor = { ...SHORT, steps: SHORT.steps.map((s, i) => ({ ...s, status: i < 2 ? 'done' : 'next' })) };
    expect(paneFocus(entryNext)).toEqual({ setup: false, entry: true });
  });
  it('says the entry forms during the C2, or after it for the conservative entry', () => {
    expect(entryCaption(SHORT)).toBe('entry forms here, during the 1h C2');
    expect(entryCaption({ ...SHORT, entry_during: false })).toBe('entry forms here, after the 1h C2');
  });
  it('prints whole prices bare and anything else with two decimals', () => {
    expect(lookDecimals(SHORT)).toBe(0);
    expect(lookDecimals({ ...SHORT, target_price: 25360.25 })).toBe(2);
  });
  it('carries no em or en dash in any word it draws', () => {
    const words = [setupCaption(SHORT, A), ...SHORT.steps.map((s) => s.label), SHORT.entry, SHORT.stop, SHORT.target];
    for (const w of words) expect(w).not.toMatch(/[–—]/);
  });
});

describe('which step each projected candle stands for', () => {
  const step = (label: string, status: 'done' | 'next' | 'later') => ({ label, status });
  const base = { ...LOOK_FOR_SHORT };
  it('a continuation: C1 and C2 are its first two steps', () => {
    const look = { ...base, steps: [step('1h C1', 'next'), step('1h C2', 'later'), step('5m entry', 'later')] };
    expect(candleEmphasis(look)).toEqual([true, false]);
    expect(candleSteps(look).map((s) => s?.label)).toEqual(['1h C1', '1h C2']);
  });
  it('a reversal: neither is amber while the bias candle is still heading for the level, both once C1 / C2 is awaited', () => {
    const waiting = { ...base, kind: 'reversal' as const, steps: [step('1W trades up into the previous 1W high', 'next'), step('4h C1 / C2 there', 'later'), step('4h turns down', 'later')] };
    expect(candleEmphasis(waiting)).toEqual([false, false]);
    expect(candleSteps(waiting).map((s) => s?.label)).toEqual(['4h C1 / C2 there', '4h C1 / C2 there']);
    const there = { ...waiting, steps: [step('1W trades up into the previous 1W high', 'done'), step('4h C1 / C2 there', 'next'), step('4h turns down', 'later')] };
    expect(candleEmphasis(there)).toEqual([true, true]);
  });
});
