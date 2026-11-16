// Pure chart logic, kept apart from the canvas code so it can be tested.
import { formatPrice } from '../format';
import type { Candle, Mark } from '../wire';

/** Prices a mark occupies on the vertical axis. */
export function markPrices(mark: Mark): number[] {
  if (mark.kind === 'zone') return [mark.top, mark.bottom].filter((p): p is number => p !== null);
  return mark.price === null ? [] : [mark.price];
}

export interface Partition {
  /** Marks drawn on the chart; their prices widen the autoscale. */
  shown: Mark[];
  /** Levels too far above or below the candles to fit without squashing them. */
  above: Mark[];
  below: Mark[];
}

/**
 * Levels within `reach` x the candle range of the candles stay on the chart and
 * pull the scale out to include them. Anything further is listed as off-scale, so
 * one distant level does not flatten the candles. The trade's own levels (waiting,
 * stop, entry, target) get `tradeReach` instead: on a short window the target can
 * be a full range away and still belongs on the chart. Zones and markers always show.
 */
export function partitionMarks(candles: readonly Candle[], marks: readonly Mark[], reach = 0.15, tradeReach = 1): Partition {
  if (candles.length === 0) return { shown: [...marks], above: [], below: [] };
  let lo = Infinity;
  let hi = -Infinity;
  for (const c of candles) {
    if (c.low < lo) lo = c.low;
    if (c.high > hi) hi = c.high;
  }
  const range = Math.max(hi - lo, 1e-9);
  const shown: Mark[] = [];
  const above: Mark[] = [];
  const below: Mark[] = [];
  for (const m of marks) {
    const pad = range * (labelPriority(m.role) <= 3 ? Math.max(reach, tradeReach) : reach);
    if (m.kind !== 'level' || m.price === null) {
      shown.push(m);
    } else if (m.price > hi + pad) {
      above.push(m);
    } else if (m.price < lo - pad) {
      below.push(m);
    } else {
      shown.push(m);
    }
  }
  return { shown, above, below };
}

/** "Above the scale: Target 2 at 25,612.50" */
export function offScaleNotes(p: Partition, decimals = 2): string[] {
  const list = (ms: Mark[]) => ms.map((m) => `${m.label || m.title} at ${formatPrice(m.price ?? 0, decimals)}`).join(', ');
  const out: string[] = [];
  if (p.above.length) out.push(`Above the scale: ${list(p.above)}`);
  if (p.below.length) out.push(`Below the scale: ${list(p.below)}`);
  return out;
}

export type CandleDiff = { kind: 'none' } | { kind: 'reset' } | { kind: 'update'; from: number };

/**
 * How to bring the chart from `prev` to `next`. Ticks replace or append only at
 * the tail and keep earlier candle objects, so an identical prefix means the chart
 * can update in place; anything else (a new snapshot) redraws.
 */
export function diffCandles(prev: readonly Candle[], next: readonly Candle[]): CandleDiff {
  if (prev === next) return { kind: 'none' };
  if (prev.length === 0 || next.length < prev.length) return { kind: 'reset' };
  let i = 0;
  while (i < prev.length && prev[i] === next[i]) i++;
  if (i === prev.length && next.length === prev.length) return { kind: 'none' };
  if (i < prev.length - 1) return { kind: 'reset' };
  // A replaced last bar must keep its time; appended bars must move forward.
  let prevT = i > 0 ? next[i - 1]!.t : -Infinity;
  for (let j = i; j < next.length; j++) {
    const t = next[j]!.t;
    const ok = j === prev.length - 1 ? t === prev[j]!.t : t > prevT;
    if (!ok) return { kind: 'reset' };
    prevT = t;
  }
  return { kind: 'update', from: i };
}

// ---------- opening window ----------

/**
 * First candle index of the window a chart opens on: the last `bars` candles, widened
 * to the left so the start of every mark (a few candles before it) is in view. The
 * rest of the history stays reachable by scrolling.
 */
export function initialWindowStart(count: number, marks: readonly Pick<Mark, 'start'>[], bars: number, lead = 2): number {
  if (count <= bars) return 0;
  let from = count - bars;
  for (const m of marks) {
    if (m.start !== null && m.start >= 0 && m.start < count) from = Math.min(from, m.start - lead);
  }
  return Math.max(0, from);
}

/** Whether a mark draws anything between candle indexes `from` and `to` (logical, inclusive). */
export function markInRange(mark: Mark, from: number, to: number): boolean {
  const start = mark.start ?? -Infinity;
  // Levels run from their start to the right edge; zones to `end` or the right edge.
  const end = mark.kind === 'level' ? Infinity : (mark.end ?? (mark.kind === 'marker' ? start : Infinity));
  return start <= to && end >= from;
}

// ---------- labels ----------

/**
 * Which label survives when two collide: the plan's own lines first (TOOL_PRIORITY),
 * then waiting and next, stop, entry, target, then the rest.
 */
export function labelPriority(role: string): number {
  switch (role.trim().toLowerCase()) {
    case 'waiting':
    case 'next':
      return 0;
    case 'stop':
      return 1;
    case 'entry':
      return 2;
    case 'target':
      return 3;
    default:
      return 4;
  }
}

/** The risk / reward tool's lines outrank every mark; its zone captions come right after them. */
export const TOOL_PRIORITY = { stop: -4, entry: -3, target: -2, caption: -1 } as const;

export interface Box {
  x: number;
  y: number; // top
  w: number;
  h: number;
}

export interface LabelChoice {
  text: string;
  w: number;
  candidates: Box[];
}

/** A label waiting for its place: its wordings, fullest first, each with the spots it may take. */
export interface PendingLabel {
  title: string;
  color: string;
  priority: number;
  choices: LabelChoice[];
  /** Captions are drawn in a heavier weight. */
  caption?: boolean;
}

export const overlaps = (a: Box, b: Box, pad = 1): boolean =>
  a.x < b.x + b.w + pad && b.x < a.x + a.w + pad && a.y < b.y + b.h + pad && b.y < a.y + a.h + pad;

/**
 * Greedy placement. `labels` arrive in priority order (most important first); each
 * takes the first of its candidate boxes that is inside the plot and clear of the
 * labels already placed, or is dropped (`null`). Its line and price tag still show.
 */
export function placeLabels(labels: readonly { candidates: readonly Box[] }[], plot: { w: number; h: number }): (Box | null)[] {
  return placeChoices(
    labels.map((l) => ({ choices: [{ candidates: l.candidates }] })),
    plot,
  ).map((r) => r?.box ?? null);
}

/**
 * placeLabels for labels that have several wordings: each label tries its choices
 * in order (fullest wording first), each choice its candidate boxes, and takes the
 * first box inside the plot and clear of the labels already placed and of the
 * `obstacles` (lines no label may cover).
 */
export function placeChoices(
  labels: readonly { choices: readonly { candidates: readonly Box[] }[] }[],
  plot: { w: number; h: number },
  obstacles: readonly Box[] = [],
): ({ choice: number; box: Box } | null)[] {
  const placed: Box[] = [...obstacles];
  return labels.map(({ choices }) => {
    for (let c = 0; c < choices.length; c++) {
      for (const b of choices[c]!.candidates) {
        const inside = b.x >= 0 && b.y >= 0 && b.x + b.w <= plot.w && b.y + b.h <= plot.h;
        if (!inside) continue;
        if (placed.some((p) => overlaps(p, b))) continue;
        placed.push(b);
        return { choice: c, box: b };
      }
    }
    return null;
  });
}

/**
 * Left edge of a marker's text of width `w` centred on `x`. Near the right edge of
 * the plot it flips to end just left of the anchor (`gap` clear of the arrow); near the
 * left edge it is clamped inside.
 */
export function markerTextX(x: number, w: number, plotWidth: number, gap = 8, margin = 4): number {
  if (x + w / 2 > plotWidth - margin) return Math.max(margin, x - gap - w);
  return Math.max(margin, x - w / 2);
}

/** One price tag per distinct price: two levels at the same price keep the more important one. */
export function distinctTags<T extends { price: number; role: string; priority?: number }>(items: readonly T[], decimals: number): T[] {
  const rank = (it: T) => it.priority ?? labelPriority(it.role);
  const best = new Map<string, T>();
  for (const it of items) {
    const key = it.price.toFixed(decimals);
    const prev = best.get(key);
    if (!prev || rank(it) < rank(prev)) best.set(key, it);
  }
  return [...best.values()];
}

/**
 * placeChoices with a soft preference: labels are placed one at a time in the order given
 * (most important first). Each takes a spot clear of `hard` and `soft` (the candles) if it has
 * one, else a spot clear of `hard` alone, before the next label is tried. So a less important
 * label can never take the place a more important one needed.
 */
export function placePreferring(
  labels: readonly { choices: readonly { candidates: readonly Box[] }[] }[],
  plot: { w: number; h: number },
  hard: readonly Box[],
  soft: readonly Box[],
): ({ choice: number; box: Box } | null)[] {
  const taken: Box[] = [];
  return labels.map((label) => {
    const r = placeChoices([label], plot, [...hard, ...soft, ...taken])[0] ?? placeChoices([label], plot, [...hard, ...taken])[0] ?? null;
    if (r) taken.push(r.box);
    return r;
  });
}

/** Whether an axis tick at `y` sits under a shown price tag (within `gap` px of its centre): it is then not drawn, as in TradingView. */
export function tickCovered(y: number | null, tagYs: readonly number[], gap: number): boolean {
  return y !== null && tagYs.some((t) => Math.abs(t - y) < gap);
}

/**
 * layoutTags with key level tags: each `key` tag says which side of the last close it is on and
 * how near (0 = nearest). The other tags are laid out first; then on each side the key tags are
 * tried nearest first and the first that finds room is kept, so a farther level can never take
 * the place the nearest one needed. At most one key tag a side is drawn.
 */
export function layoutWithKeyTags(
  tags: readonly { y: number | null; quiet: boolean; key?: { side: 0 | 1; order: number } }[],
  gap: number,
): (number | null)[] {
  const inputs = tags.map((t) => (t.key ? { y: null, quiet: true } : { y: t.y, quiet: t.quiet }));
  for (const side of [0, 1] as const) {
    const tries = tags
      .map((t, i) => ({ t, i }))
      .filter(({ t }) => t.key?.side === side && t.y !== null)
      .sort((a, b) => a.t.key!.order - b.t.key!.order);
    for (const { t, i } of tries) {
      const trial = inputs.map((v, j) => (j === i ? { y: t.y, quiet: true } : v));
      if (layoutTags(trial, gap)[i] !== null) {
        inputs[i] = trial[i]!;
        break;
      }
    }
  }
  return layoutTags(inputs, gap);
}

/**
 * Where each price tag is drawn, or null when it is not: given each tag's price y (null: off
 * the scale) in order, role tags first. Role tags that would overlap are spread `gap` apart
 * around their group's centre (as Lightweight Charts aligns labels); a reference tag is then
 * drawn only where it clears every role tag's final place and every reference tag already
 * admitted. The same places are used to draw the tags and to hide the ticks under them.
 */
export function layoutTags(tags: readonly { y: number | null; quiet: boolean }[], gap: number): (number | null)[] {
  const out: (number | null)[] = tags.map(() => null);
  const roles = tags.flatMap((t, i) => (t.y !== null && !t.quiet ? [{ i, y: t.y }] : [])).sort((a, b) => a.y - b.y);
  // groups of chained overlaps, each laid out evenly around its mean; merge until none overlap
  let groups = roles.map((r) => ({ members: [r], centre: r.y }));
  const top = (g: { members: unknown[]; centre: number }) => g.centre - ((g.members.length - 1) * gap) / 2;
  const bottom = (g: { members: unknown[]; centre: number }) => g.centre + ((g.members.length - 1) * gap) / 2;
  for (let merged = true; merged; ) {
    merged = false;
    for (let k = 0; k + 1 < groups.length; k++) {
      const a = groups[k]!;
      const b = groups[k + 1]!;
      if (top(b) - bottom(a) < gap) {
        const members = [...a.members, ...b.members];
        groups = [...groups.slice(0, k), { members, centre: members.reduce((sum, m) => sum + m.y, 0) / members.length }, ...groups.slice(k + 2)];
        merged = true;
        break;
      }
    }
  }
  const placed: number[] = [];
  for (const g of groups) g.members.forEach((m, k) => placed.push((out[m.i] = top(g) + k * gap)));
  tags.forEach((t, i) => {
    if (t.y === null || !t.quiet) return;
    if (placed.some((y) => Math.abs(y - t.y!) < gap)) return;
    placed.push((out[i] = t.y));
  });
  return out;
}
