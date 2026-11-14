import { describe, expect, it } from 'vitest';
import { lookLine, paneFocus } from '../chart/look';
import { lookScalePrices } from '../chart/LookLayer';
import { parseServerFrame, validateFrame } from '../wire';
import { snapshot } from './fixtures';
import { LOOK_FOR_SHORT } from './lookfor';
import { LOOK_FOR_REVERSAL, STORY, lookForReversalView } from './lookforReversal';

describe('a reversal look_for on the wire', () => {
  it('parses with its kind, on a no-trade verdict', () => {
    const r = validateFrame(JSON.stringify(snapshot(1, lookForReversalView())));
    expect(r.ok).toBe(true);
    if (r.ok && r.frame.type === 'snapshot') {
      expect(r.frame.view?.decision).toBe('no_trade');
      expect(r.frame.view?.look_for).toEqual(LOOK_FOR_REVERSAL);
      expect(r.frame.view?.look_for?.kind).toBe('reversal');
    }
  });

  it('reads a look_for without a kind (an older core) as a continuation', () => {
    const { kind: _gone, ...older } = LOOK_FOR_SHORT;
    const frame = parseServerFrame(JSON.stringify(snapshot(1, { ...lookForReversalView(), look_for: older } as never)), () => {});
    expect(frame?.type === 'snapshot' && frame.view?.look_for?.kind).toBe('continuation');
  });
});

describe('the headline line', () => {
  it('names a reversal, its side and the key level; a continuation keeps its POI line', () => {
    expect(lookLine(LOOK_FOR_REVERSAL, 'A')).toBe('Short reversal: 4h C1, C2 at the key level 27,400 to 27,480');
    expect(lookLine(LOOK_FOR_REVERSAL, 'B')).toBe('Short reversal: 4h C1, C2 at the key level 27,655 to 27,735');
    expect(lookLine({ ...LOOK_FOR_REVERSAL, direction: 'long' }, 'A')).toMatch(/^Long reversal: /);
    expect(lookLine(LOOK_FOR_SHORT, 'A')).toBe('1h C1, C2 at the POI 25,410 to 25,428');
  });
});

describe('the scale on each pane', () => {
  const band = { lo: 27100, hi: 27350 }; // the 15m candles, far below the key level
  const far = (prices: number[]) => prices.filter((p) => p > band.hi);

  it('a reversal waiting for its level does not stretch the entry pane to it', () => {
    expect(paneFocus(LOOK_FOR_REVERSAL)).toEqual({ setup: true, entry: false });
    expect(far(lookScalePrices({ look: LOOK_FOR_REVERSAL, choice: 'A', pane: 'entry' }, band))).toEqual([]);
    // the setup pane, where the step awaited now is, still shows the chosen level
    expect(lookScalePrices({ look: LOOK_FOR_REVERSAL, choice: 'A', pane: 'setup' }, band)).toContain(STORY.prevHigh);
  });

  it('once the entry is the step awaited, the entry pane shows its box wherever it is', () => {
    const entryNext = { ...LOOK_FOR_REVERSAL, steps: LOOK_FOR_REVERSAL.steps.map((s, i) => ({ ...s, status: i < 2 ? 'done' : 'next' }) as const) };
    expect(far(lookScalePrices({ look: entryNext, choice: 'A', pane: 'entry' }, band)).length).toBeGreaterThan(0);
  });

  it('a continuation entry pane is unchanged: its box always counts', () => {
    const shapes = lookScalePrices({ look: LOOK_FOR_SHORT, choice: 'A', pane: 'entry' }, { lo: 0, hi: 1 });
    expect(shapes.length).toBe(2);
  });

  it('the other option counts only inside the band, on any kind', () => {
    const setup = lookScalePrices({ look: LOOK_FOR_REVERSAL, choice: 'A', pane: 'setup' }, band);
    expect(setup).not.toContain(STORY.swingHigh);
    expect(lookScalePrices({ look: LOOK_FOR_REVERSAL, choice: 'A', pane: 'setup' }, null)).toContain(STORY.swingHigh);
  });
});

describe('the look-for-reversal sample', () => {
  const view = lookForReversalView();
  const chart = (role: string) => view.charts.find((c) => c.role === role)!;

  it('builds the last session of 4h candles from its 15m candles, so the panes agree', () => {
    const entry = chart('entry').candles;
    const setup = chart('setup').candles;
    for (const h of setup.slice(-5)) {
      const inside = entry.filter((b) => b.t >= h.t && b.t < h.t + 4 * 3600);
      expect(inside.length).toBeGreaterThan(0);
      expect(h.high).toBe(Math.max(...inside.map((b) => b.high)));
      expect(h.low).toBe(Math.min(...inside.map((b) => b.low)));
      expect(h.close).toBe(inside.at(-1)!.close);
    }
    expect(setup.at(-1)!.forming && entry.at(-1)!.forming).toBe(true);
  });

  it('builds the last three weeks from their 4h candles', () => {
    const weekly = chart('bias').candles;
    const setup = chart('setup').candles;
    for (const w of weekly.slice(-3)) {
      const next = weekly[weekly.indexOf(w) + 1];
      const inside = setup.filter((b) => b.t >= w.t && (!next || b.t < next.t));
      expect(inside.length).toBeGreaterThan(0);
      expect(w.high).toBe(Math.max(...inside.map((b) => b.high)));
      expect(w.low).toBe(Math.min(...inside.map((b) => b.low)));
    }
    expect(weekly.at(-1)!.forming).toBe(true);
  });

  it('matches its story: the week has not reached either key level, and the high is the nearer one', () => {
    const weekly = chart('bias').candles;
    const [previous, forming] = [weekly.at(-2)!, weekly.at(-1)!];
    expect([previous.high, previous.low]).toEqual([STORY.prevHigh, STORY.prevLow]);
    expect([forming.high, forming.low]).toEqual([STORY.weekHigh, STORY.weekLow]);
    const a = LOOK_FOR_REVERSAL.options[0]!;
    expect(forming.high).toBeLessThan(a.bottom); // not inside the band that counts as reaching it
    expect(previous.high - forming.high).toBeLessThan(forming.low - previous.low);
    expect(LOOK_FOR_REVERSAL.target_price).toBe((previous.high + previous.low) / 2);
  });

  it('option B is an untaken weekly swing high wholly beyond A', () => {
    const weekly = chart('bias').candles;
    const [a, b] = LOOK_FOR_REVERSAL.options;
    expect(b!.bottom).toBeGreaterThan(a!.top);
    const at = weekly.findIndex((w) => w.high === STORY.swingHigh);
    expect(at).toBeGreaterThan(0);
    expect(weekly[at - 1]!.high).toBeLessThan(STORY.swingHigh);
    expect(Math.max(...weekly.slice(at + 1).map((w) => w.high))).toBeLessThan(STORY.swingHigh);
  });

  it('says nothing in the look-for that prints a price of a candle not yet formed, and no em dash', () => {
    const words = [...LOOK_FOR_REVERSAL.steps.map((s) => s.label), LOOK_FOR_REVERSAL.entry, LOOK_FOR_REVERSAL.stop, LOOK_FOR_REVERSAL.target];
    for (const w of words) {
      expect(w).not.toMatch(/\d{3,}/u); // timeframes and "2R" only, never a price
      expect(w).not.toContain('—');
    }
  });
});
