import { describe, expect, it } from 'vitest';
import { DEFAULT_DISPLAY, DISPLAY_KEY, isDefault, layerMarks, loadDisplay, parseDisplay, saveDisplay, stepTextSize, textScale, type DisplayOptions } from './display';

class MemoryStorage {
  data = new Map<string, string>();
  getItem(k: string) {
    return this.data.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.data.set(k, v);
  }
  removeItem(k: string) {
    this.data.delete(k);
  }
}

const custom: DisplayOptions = { textSize: 'larger', scheme: 'blue-orange', overlays: { levelNames: false, zones: true, markerLabels: false, riskReward: true, sessionLevels: true } };

describe('display options persistence', () => {
  it('round-trips through storage', () => {
    const s = new MemoryStorage();
    saveDisplay(s, custom);
    expect(loadDisplay(s)).toEqual(custom);
  });

  it('stores the defaults as nothing, so a reset leaves no key behind', () => {
    const s = new MemoryStorage();
    saveDisplay(s, custom);
    saveDisplay(s, { ...DEFAULT_DISPLAY, overlays: { ...DEFAULT_DISPLAY.overlays } });
    expect(s.data.has(DISPLAY_KEY)).toBe(false);
    expect(loadDisplay(s)).toEqual(DEFAULT_DISPLAY);
  });

  it('falls back field by field when what is stored is broken or from another version', () => {
    expect(parseDisplay('{not json')).toEqual(DEFAULT_DISPLAY);
    expect(parseDisplay('null')).toEqual(DEFAULT_DISPLAY);
    const partial = parseDisplay(JSON.stringify({ scheme: 'mono', textSize: 'huge', overlays: { zones: false, levelNames: 'yes' } }));
    expect(partial).toEqual({ ...DEFAULT_DISPLAY, scheme: 'mono', overlays: { ...DEFAULT_DISPLAY.overlays, zones: false } });
  });

  it('works without storage', () => {
    expect(loadDisplay(null)).toEqual(DEFAULT_DISPLAY);
    const throwing = { getItem: () => { throw new Error('denied'); }, setItem: () => { throw new Error('denied'); }, removeItem: () => {} };
    expect(loadDisplay(throwing)).toEqual(DEFAULT_DISPLAY);
    expect(() => saveDisplay(throwing, custom)).not.toThrow();
  });

  it('knows when nothing differs from the defaults (Reset is then disabled)', () => {
    expect(isDefault(parseDisplay(null))).toBe(true);
    expect(isDefault({ ...DEFAULT_DISPLAY, overlays: { ...DEFAULT_DISPLAY.overlays, riskReward: false } })).toBe(false);
  });
});

describe('text size', () => {
  it('steps Normal, Large, Larger and stops at the ends (Ctrl+= and Ctrl+-)', () => {
    expect(stepTextSize('normal', 1)).toBe('large');
    expect(stepTextSize('large', 1)).toBe('larger');
    expect(stepTextSize('larger', 1)).toBe('larger');
    expect(stepTextSize('normal', -1)).toBe('normal');
    expect(['normal', 'large', 'larger'].map((s) => textScale(s as DisplayOptions['textSize']))).toEqual([1, 1.25, 1.5]);
  });
});

describe('the session levels layer', () => {
  const marks = [{ role: 'reference' }, { role: 'session' }, { role: 'entry' }];

  it('is off by default and keeps every other mark', () => {
    expect(DEFAULT_DISPLAY.overlays.sessionLevels).toBe(false);
    expect(layerMarks(marks, DEFAULT_DISPLAY.overlays).map((m) => m.role)).toEqual(['reference', 'entry']);
  });

  it('shows the session marks when turned on, and an older stored choice falls back to off', () => {
    expect(layerMarks(marks, { ...DEFAULT_DISPLAY.overlays, sessionLevels: true })).toHaveLength(3);
    expect(parseDisplay(JSON.stringify({ overlays: { zones: false } })).overlays.sessionLevels).toBe(false);
  });
});
