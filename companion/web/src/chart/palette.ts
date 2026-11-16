// Canvas cannot read CSS variables, so the chart reads the resolved token values
// once per theme or scheme change, from its own element: a scheme may give the chart
// area its own tokens (TradingView: the trader's cream pane). tokens.css stays the only source.
import type { Semantic } from '../tones';

/** The chart canvas font: TradingView's stack (Trebuchet MS on Windows), the same as --font-sans in tokens.css. */
export const CHART_FONT = "-apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, sans-serif";

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
  /** The up candle's outline and wick: its own colour unless the scheme sets one (a pale body on a light pane). */
  upLine: string;
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

type ColourKey = Exclude<keyof Palette, 'hollowUp' | 'upLine' | 'downLine'>;

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
  out.upLine = style.getPropertyValue('--candle-up-line').trim() || out.up;
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

function luminance(hex: string): number {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return 0;
  const n = parseInt(m[1]!, 16);
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * ch[0]! + 0.7152 * ch[1]! + 0.0722 * ch[2]!;
}

/** WCAG contrast ratio of two "#RRGGBB" colours, 1 .. 21. */
export function contrastRatio(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p) as [number, number];
  return (x + 0.05) / (y + 0.05);
}

/** Ink of a plain reference level: the faint ink where it still reaches 3:1 on the pane, else the muted one. */
export function quietInk(p: Pick<Palette, 'faint' | 'muted' | 'surface'>): string {
  return contrastRatio(p.faint, p.surface) >= 3 ? p.faint : p.muted;
}
