// Canvas cannot read CSS variables, so the chart reads the resolved token values
// from the document once per theme or scheme change. tokens.css stays the only source.
import type { Semantic } from '../tones';

export interface Palette {
  bg: string;
  surface: string;
  raised: string;
  line: string;
  text: string;
  muted: string;
  faint: string;
  up: string;
  down: string;
  /** The down candle's outline and wick: its own colour unless the scheme sets one (a black body on a dark pane). */
  downLine: string;
  watch: string;
  bull: string;
  bear: string;
  long: string;
  short: string;
  reward: string;
  risk: string;
  /** Monochrome: up candles are drawn hollow, down candles filled. */
  hollowUp: boolean;
}

type ColourKey = Exclude<keyof Palette, 'hollowUp' | 'downLine'>;

const VARS: Record<ColourKey, string> = {
  bg: '--bg',
  surface: '--surface',
  raised: '--raised',
  line: '--line',
  text: '--text',
  muted: '--muted',
  faint: '--faint',
  up: '--candle-up',
  down: '--candle-down',
  watch: '--watch',
  bull: '--bull',
  bear: '--bear',
  long: '--long',
  short: '--short',
  reward: '--reward',
  risk: '--risk',
};

export function readPalette(el: Element = document.documentElement): Palette {
  const style = getComputedStyle(el);
  const out = {} as Palette;
  for (const key of Object.keys(VARS) as ColourKey[]) {
    out[key] = style.getPropertyValue(VARS[key]).trim() || '#888888';
  }
  out.downLine = style.getPropertyValue('--candle-down-line').trim() || out.down;
  out.hollowUp = style.getPropertyValue('--candle-up-hollow').trim() === '1';
  return out;
}

export function toneColor(p: Palette, tone: Semantic): string {
  return tone === 'muted' ? p.muted : p[tone];
}

/** "#RRGGBB" + alpha -> "rgba(...)". Soft tints are the status colour at about 11%. */
export function withAlpha(hex: string, alpha: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return hex;
  const n = parseInt(m[1]!, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}
