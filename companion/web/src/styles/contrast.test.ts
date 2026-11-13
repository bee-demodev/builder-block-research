// WCAG AA for every text colour on every background it is used on, and 3:1 for the
// graphics a trader must see (candles, also over the risk / reward zones), in both
// themes and every direction-colour scheme. Read straight from tokens.css so a token
// edit cannot slip past.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { SCHEMES } from '../display';
import { ZONE_ALPHA } from '../chart/tool';

const css = readFileSync(fileURLToPath(new URL('./tokens.css', import.meta.url)), 'utf8');

/** The hex tokens of the first rule whose selector is exactly `selector`. */
function block(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`no rule ${selector}`);
  const open = css.indexOf('{', start);
  const close = css.indexOf('}', open);
  const out: Record<string, string> = {};
  for (const m of css.slice(open + 1, close).matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})/gi)) out[m[1]!] = m[2]!;
  return out;
}

const SCHEME_TOKENS = ['long', 'short', 'bull', 'bear', 'watch', 'reward', 'risk', 'candle-up', 'candle-down'] as const;
const TEXT_TOKENS = ['text', 'muted', 'long', 'short', 'bull', 'bear', 'watch', 'reward', 'risk'] as const;

const baseLight = block(':root');
const baseDark = block(":root[data-theme='dark']");

function tokens(scheme: string, theme: 'light' | 'dark'): Record<string, string> {
  const base = theme === 'light' ? baseLight : baseDark;
  if (scheme === 'grey') return base;
  const own = theme === 'light' ? block(`:root[data-scheme='${scheme}']`) : block(`:root[data-scheme='${scheme}'][data-theme='dark']`);
  return { ...base, ...own };
}

const lum = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * ch[0]! + 0.7152 * ch[1]! + 0.0722 * ch[2]!;
};
const ratio = (a: string, b: string) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p) as [number, number];
  return (x + 0.05) / (y + 0.05);
};
/** Colour of `fg` at `alpha` over `bg`, for tints and zone fills. */
const over = (fg: string, alpha: number, bg: string) => {
  const f = parseInt(fg.slice(1), 16);
  const b = parseInt(bg.slice(1), 16);
  const mix = (sh: number) => Math.round(((f >> sh) & 255) * alpha + ((b >> sh) & 255) * (1 - alpha));
  return `#${[16, 8, 0].map((sh) => mix(sh).toString(16).padStart(2, '0')).join('')}`;
};

const cases = SCHEMES.flatMap((s) => (['light', 'dark'] as const).map((theme) => [`${s.value} ${theme}`, tokens(s.value, theme)] as const));

describe.each(cases)('%s', (_name, t) => {
  it('sets every token', () => {
    for (const k of ['bg', 'surface', 'raised', ...SCHEME_TOKENS]) expect(t[k], k).toMatch(/^#/);
  });

  it.each(TEXT_TOKENS)('%s passes AA on bg, surface and raised', (fg) => {
    for (const bg of ['bg', 'surface', 'raised']) {
      expect(ratio(t[fg]!, t[bg]!), `${fg} on ${bg}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('text and status words pass AA on the 11% tints they sit on (alerts, the next step)', () => {
    for (const tone of ['watch', 'bear', 'bull']) {
      const tint = over(t[tone]!, 0.11, t.surface!);
      for (const fg of ['text', 'muted', tone]) expect(ratio(t[fg]!, tint), `${fg} on ${tone} tint`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('the primary button label and every price tag pass AA', () => {
    expect(ratio(t.bg!, t.text!)).toBeGreaterThanOrEqual(4.5);
    for (const tag of ['watch', 'bull', 'bear', 'muted', 'long', 'short', 'reward', 'risk']) {
      expect(ratio(t.bg!, t[tag]!), `bg on ${tag} tag`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('zone captions pass AA on their zone, and candles keep 3:1 on the pane and over both zones', () => {
    for (const zone of ['reward', 'risk']) {
      const fill = over(t[zone]!, ZONE_ALPHA, t.surface!);
      expect(ratio(t[zone]!, fill), `${zone} caption on its zone`).toBeGreaterThanOrEqual(4.5);
      for (const c of ['candle-up', 'candle-down']) expect(ratio(t[c]!, fill), `${c} over the ${zone} zone`).toBeGreaterThanOrEqual(3);
    }
    for (const c of ['candle-up', 'candle-down']) expect(ratio(t[c]!, t.surface!), `${c} on the pane`).toBeGreaterThanOrEqual(3);
  });
});

describe('token blocks', () => {
  it.each(SCHEMES.map((s) => s.value))('%s: the system-dark copy matches the explicit dark block', (scheme) => {
    const media = css.indexOf('@media (prefers-color-scheme: dark)', scheme === 'grey' ? 0 : css.indexOf(`[data-scheme='${scheme}']`));
    const selector = scheme === 'grey' ? ":root:not([data-theme='light'])" : `:root[data-scheme='${scheme}']:not([data-theme='light'])`;
    expect(css.indexOf(selector, media)).toBeGreaterThan(media);
    const explicit = scheme === 'grey' ? baseDark : block(`:root[data-scheme='${scheme}'][data-theme='dark']`);
    expect(block(selector)).toEqual(explicit);
  });
});
