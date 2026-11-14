// "Look for" on the charts: pure geometry, kept apart from the canvas code so it can be
// tested. Nothing here predicts a price path. The option boxes are the core's zones; the
// outlined C1 / C2 and the entry box are a schematic of the shape to look for, placed
// inside and just beyond the chosen zone, and their prices are never printed (the axis
// tags say "stop" and "entry", not a number).
import type { LookFor, LookOption } from '../wire';

export interface Ohlc {
  open: number;
  high: number;
  low: number;
  close: number;
}

/** The option the trader picked, else A, else the first one. */
export function chosenOption(look: LookFor, choice: string): LookOption | null {
  return look.options.find((o) => o.key === choice) ?? look.options.find((o) => o.key === 'A') ?? look.options[0] ?? null;
}

/**
 * The edge of the zone a pullback reaches first and the edge beyond it, and the
 * pullback's direction in price: a short waits for price to come up into the zone.
 */
export function zoneEdges(option: LookOption, direction: LookFor['direction']): { near: number; far: number; dir: 1 | -1; h: number } {
  const h = Math.max(option.top - option.bottom, 1e-9);
  return direction === 'short' ? { near: option.bottom, far: option.top, dir: 1, h } : { near: option.top, far: option.bottom, dir: -1, h };
}

const ohlc = (open: number, close: number, a: number, b: number): Ohlc => ({
  open,
  close,
  high: Math.max(open, close, a, b),
  low: Math.min(open, close, a, b),
});

/**
 * The schematic C1 and C2 at a zone: C1 pushes into it from outside and closes inside;
 * C2 opens there, sweeps C1's extreme past the far edge and closes back toward the near
 * edge. Shapes only: they say what to look for, not where price will go.
 */
export function projectedCandles(option: LookOption, direction: LookFor['direction']): [Ohlc, Ohlc] {
  const { near, far, dir, h } = zoneEdges(option, direction);
  const c1Open = near - dir * 0.35 * h;
  const c1Close = near + dir * 0.45 * h;
  const c1 = ohlc(c1Open, c1Close, near + dir * 0.8 * h, c1Open - dir * 0.1 * h);
  const c2Close = near + dir * 0.15 * h;
  const c2 = ohlc(c1Close, c2Close, far + dir * 0.2 * h, c2Close - dir * 0.1 * h);
  return [c1, c2];
}

/**
 * Where the entry chart draws the stop and entry hairlines and the "entry forms here" box,
 * for the chosen zone: the stop just beyond C2's sweep, the entry where C2 closes back,
 * the box from the stop to a little past the entry.
 */
export function entryGeometry(option: LookOption, direction: LookFor['direction']): { stop: number; entry: number; top: number; bottom: number } {
  const { near, far, dir, h } = zoneEdges(option, direction);
  const stop = far + dir * 0.3 * h;
  const entry = near + dir * 0.15 * h;
  const past = near - dir * 0.35 * h;
  return { stop, entry, top: Math.max(stop, past), bottom: Math.min(stop, past) };
}

/** The caption over the chosen box on the setup chart: "A  look for 1h C1, then C2". */
export function setupCaption(look: LookFor, option: LookOption): string {
  return `${option.key}  look for ${look.timeframe} C1, then C2`;
}

/** "entry forms here, during the 1h C2", or "after the 1h C2" for the conservative entry */
export function entryCaption(look: LookFor): string {
  return `entry forms here, ${look.entry_during ? 'during' : 'after'} the ${look.timeframe} C2`;
}

/** "stop, above the 1h C2 high" */
export function stopCaption(look: LookFor): string {
  return `stop, ${look.stop}`;
}

/** Whether the setup chart's step is the one awaited now (C1 or C2), and the entry chart's. */
export function paneFocus(look: LookFor): { setup: boolean; entry: boolean } {
  const [c1, c2, entry] = look.steps;
  return { setup: c1?.status === 'next' || c2?.status === 'next', entry: entry?.status === 'next' };
}

/** Status of C1 and C2 (the first two steps): the next one is drawn amber, later ones dimmer. */
export function candleEmphasis(look: LookFor): [boolean, boolean] {
  return [look.steps[0]?.status === 'next', look.steps[1]?.status === 'next'];
}

/** Decimals for the panel's prices: whole numbers print bare, anything else with two. */
export function lookDecimals(look: LookFor): number {
  const prices = look.options.flatMap((o) => [o.top, o.bottom]);
  if (look.target_price !== null) prices.push(look.target_price);
  return prices.every((p) => Number.isInteger(p)) ? 0 : 2;
}
