// "Look for" on a pane, drawn by MarksPrimitive in the empty space between the last
// candle and the higher-timeframe column:
//  - setup pane: a faint box per option (the chosen one in the watch colour, the others
//    grey), the schematic C1 and C2 in outline inside the chosen box (the step awaited now
//    in the watch colour, a later one dimmer), and their names;
//  - entry pane: the "entry forms here" box, the stop hairline (the only red) and the entry
//    hairline, each named in words; the axis tags say "stop" and "entry", never a number,
//    because those prices depend on candles that have not formed.
// Quiet on purpose: boxes, hairlines and outlines only, no path drawn between them.
import type { ISeriesApi, SeriesType, Time } from 'lightweight-charts';
import { formatPrice } from '../format';
import type { LookFor } from '../wire';
import { candleEmphasis, chosenOption, entryCaption, entryGeometry, lookDecimals, paneFocus, projectedCandles, setupCaption, stopCaption, type Ohlc } from './look';
import type { Box, PendingLabel } from './marks';
import { withAlpha, type Palette } from './palette';

export interface LookScene {
  look: LookFor;
  /** The option the trader picked ("A" or "B"); client-only state. */
  choice: string;
  pane: 'setup' | 'entry';
}

/** What the layer needs from the chart, in media pixels. */
export interface LookEnv {
  series: ISeriesApi<SeriesType, Time>;
  palette: Palette;
  scene: LookScene;
  /** The region between the last candle and the column. */
  left: number;
  right: number;
  /** Centre of the last candle, where the entry chart's hairlines start. */
  lastX: number;
  barSpacing: number;
  labelH: number;
}

/** Labels rank after the trade's own lines and before the column's names. */
const LOOK_PRIORITY = 3.2;

export interface LookHit {
  box: Box;
  title: string;
  priority: number;
}

function rows(env: LookEnv) {
  const { look, choice, pane } = env.scene;
  const chosen = chosenOption(look, choice);
  return { look, chosen, pane };
}

/** Prices the layer needs on screen: the chosen box and what is drawn around it. */
export function lookPrices(scene: LookScene): number[] {
  const chosen = chosenOption(scene.look, scene.choice);
  if (!chosen) return [];
  if (scene.pane === 'entry') {
    const g = entryGeometry(chosen, scene.look.direction);
    return [g.top, g.bottom];
  }
  const [c1, c2] = projectedCandles(chosen, scene.look.direction);
  return [chosen.top, chosen.bottom, c1.high, c1.low, c2.high, c2.low];
}

/** The other options' prices, which widen the scale only when they are near (see MarksPrimitive). */
export function otherOptionPrices(scene: LookScene): number[] {
  if (scene.pane !== 'setup') return [];
  const chosen = chosenOption(scene.look, scene.choice);
  return scene.look.options.filter((o) => o !== chosen).flatMap((o) => [o.top, o.bottom]);
}

/** Box fills, behind the candles. */
export function drawLookFills(ctx: CanvasRenderingContext2D, hr: number, vr: number, env: LookEnv, hits: LookHit[]): void {
  const { look, chosen, pane } = rows(env);
  if (!chosen || env.right - env.left < 8) return;
  const p = env.palette;
  const fill = (top: number, bottom: number, color: string, alpha: number, border: number) => {
    const y1 = env.series.priceToCoordinate(top);
    const y2 = env.series.priceToCoordinate(bottom);
    if (y1 === null || y2 === null) return null;
    const x = Math.round(env.left * hr);
    const w = Math.round((env.right - env.left) * hr);
    const t = Math.round(Math.min(y1, y2) * vr);
    const h = Math.max(1, Math.round(Math.abs(y2 - y1) * vr));
    ctx.fillStyle = withAlpha(color, alpha);
    ctx.fillRect(x, t, w, h);
    if (border > 0) {
      const b = Math.max(1, Math.floor(hr));
      ctx.fillStyle = withAlpha(color, border);
      ctx.fillRect(x, t, w, b);
      ctx.fillRect(x, t + h - b, w, b);
      ctx.fillRect(x, t, b, h);
      ctx.fillRect(x + w - b, t, b, h);
    }
    return { x: env.left, y: Math.min(y1, y2), w: env.right - env.left, h: Math.max(2, Math.abs(y2 - y1)) };
  };
  if (pane === 'setup') {
    for (const o of look.options) {
      const isChosen = o === chosen;
      const box = fill(o.top, o.bottom, isChosen ? p.watch : p.muted, isChosen ? 0.1 : 0.07, isChosen ? 0.3 : 0);
      if (box) {
        const span = `${formatPrice(o.bottom, lookDecimals(look))} to ${formatPrice(o.top, lookDecimals(look))}`;
        hits.push({ box, title: `${o.key}: ${o.name}, ${span}${o.condition ? `, ${o.condition}` : ''}`, priority: LOOK_PRIORITY + 10 });
      }
    }
    return;
  }
  const g = entryGeometry(chosen, look.direction);
  const box = fill(g.top, g.bottom, p.watch, paneFocus(look).entry ? 0.1 : 0.06, 0);
  if (box) hits.push({ box, title: `${entryCaption(look)}: ${look.entry}`, priority: LOOK_PRIORITY + 10 });
}

/** An outlined candle at media x `cx`, `body` wide. */
export function drawOutlineCandle(ctx: CanvasRenderingContext2D, hr: number, vr: number, series: LookEnv['series'], c: Ohlc, cx: number, body: number, color: string): Box | null {
  const yH = series.priceToCoordinate(c.high);
  const yL = series.priceToCoordinate(c.low);
  const yO = series.priceToCoordinate(c.open);
  const yC = series.priceToCoordinate(c.close);
  if (yH === null || yL === null || yO === null || yC === null) return null;
  const x = Math.round(cx * hr);
  const bw = Math.max(3, Math.round(body * hr));
  const bx = x - Math.floor(bw / 2);
  const line = Math.max(1, Math.floor(hr));
  const top = Math.round(Math.min(yO, yC) * vr);
  const bottom = Math.max(top + 2, Math.round(Math.max(yO, yC) * vr));
  ctx.fillStyle = color;
  ctx.fillRect(x - Math.floor(line / 2), Math.round(yH * vr), line, Math.max(0, top - Math.round(yH * vr)));
  ctx.fillRect(x - Math.floor(line / 2), bottom, line, Math.max(0, Math.round(yL * vr) - bottom));
  ctx.fillRect(bx, top, bw, line);
  ctx.fillRect(bx, bottom - line, bw, line);
  ctx.fillRect(bx, top, line, bottom - top);
  ctx.fillRect(bx + bw - line, top, line, bottom - top);
  return { x: cx - body / 2 - 2, y: yH, w: body + 4, h: Math.max(2, yL - yH) };
}

/** Where the setup pane's C1 and C2 sit: inside the region, a third and two thirds across. */
function candleSlots(env: LookEnv): { x: number; body: number }[] {
  const w = env.right - env.left;
  const body = Math.max(4, Math.min(12, env.barSpacing * 0.8));
  return [
    { x: env.left + w * 0.35, body },
    { x: env.left + w * 0.65, body },
  ];
}

/** Outlines and hairlines, over the candles. Returns the boxes labels must keep clear of. */
export function drawLookStrokes(ctx: CanvasRenderingContext2D, hr: number, vr: number, env: LookEnv, hits: LookHit[]): Box[] {
  const { look, chosen, pane } = rows(env);
  if (!chosen || env.right - env.left < 8) return [];
  const p = env.palette;
  const obstacles: Box[] = [];
  if (pane === 'setup') {
    const emphasis = candleEmphasis(look);
    const candles = projectedCandles(chosen, look.direction);
    candleSlots(env).forEach((slot, k) => {
      const color = emphasis[k] ? p.watch : withAlpha(p.watch, 0.5);
      const box = drawOutlineCandle(ctx, hr, vr, env.series, candles[k]!, slot.x, slot.body, color);
      if (box) {
        obstacles.push(box);
        hits.push({ box, title: `${look.steps[k]?.label ?? `C${k + 1}`} (what to look for, not a forecast)`, priority: LOOK_PRIORITY });
      }
    });
    return obstacles;
  }
  // entry pane: stop and entry hairlines from the last candle to the region's end, dashed
  const g = entryGeometry(chosen, look.direction);
  const lw = Math.max(1, Math.floor(vr));
  const dash = Math.round(5 * hr);
  const gap = Math.round(4 * hr);
  const from = Math.round(env.lastX * hr);
  const to = Math.round(env.right * hr);
  for (const [price, color] of [
    [g.stop, p.risk],
    [g.entry, paneFocus(look).entry ? p.watch : withAlpha(p.watch, 0.6)],
  ] as const) {
    const y = env.series.priceToCoordinate(price);
    if (y === null) continue;
    const yb = Math.round(y * vr) - Math.floor(lw / 2);
    ctx.fillStyle = color;
    for (let x = from; x < to; x += dash + gap) ctx.fillRect(x, yb, Math.min(dash, to - x), lw);
    obstacles.push({ x: env.lastX, y: y - 1.5, w: env.right - env.lastX, h: 3 });
  }
  return obstacles;
}

/** The layer's words, for the label placer. */
export function lookLabels(env: LookEnv, plot: { w: number; h: number }, measure: (text: string, weight?: number) => number): PendingLabel[] {
  const { look, chosen, pane } = rows(env);
  if (!chosen || env.right - env.left < 8) return [];
  const p = env.palette;
  const LH = env.labelH;
  const out: PendingLabel[] = [];
  const y = (price: number) => env.series.priceToCoordinate(price);
  const at = (text: string, color: string, priority: number, spots: Box[], title = text): void => {
    out.push({ title, color, priority, choices: [{ text, w: spots[0]?.w ?? measure(text), candidates: spots }] });
  };

  if (pane === 'setup') {
    for (const o of look.options) {
      const yt = y(o.top);
      const yb = y(o.bottom);
      if (yt === null || yb === null) continue;
      const isChosen = o === chosen;
      const text = isChosen ? setupCaption(look, o) : o.key;
      const w = measure(text);
      const x = Math.max(2, Math.min(env.left + 2, plot.w - w - 2));
      const above: Box = { x, y: Math.min(yt, yb) - LH - 3, w, h: LH };
      const below: Box = { x, y: Math.max(yt, yb) + 3, w, h: LH };
      const before: Box = { x: env.left - w - 6, y: (yt + yb) / 2 - LH / 2, w, h: LH };
      const spots = look.direction === 'short' ? [above, before, below] : [below, before, above];
      at(text, isChosen ? p.watch : p.muted, LOOK_PRIORITY + (isChosen ? 0 : 0.3), isChosen ? spots : [below, above, before], isChosen ? text : `${o.key}: ${o.name}`);
    }
    const emphasis = candleEmphasis(look);
    const candles = projectedCandles(chosen, look.direction);
    candleSlots(env).forEach((slot, k) => {
      const c = candles[k]!;
      const yLow = y(c.low);
      const yHigh = y(c.high);
      if (yLow === null || yHigh === null) return;
      const text = `C${k + 1}`;
      const w = measure(text);
      const x = slot.x - w / 2;
      const under: Box = { x, y: Math.max(yLow, yHigh) + 3, w, h: LH };
      const over: Box = { x, y: Math.min(yLow, yHigh) - LH - 3, w, h: LH };
      at(text, emphasis[k] ? p.watch : p.muted, LOOK_PRIORITY + 0.1, look.direction === 'short' ? [under, over] : [over, under], look.steps[k]?.label ?? text);
    });
    return out;
  }

  // entry pane
  const g = entryGeometry(chosen, look.direction);
  const yStop = y(g.stop);
  const yEntry = y(g.entry);
  const yTop = y(g.top);
  const yBottom = y(g.bottom);
  const x = Math.max(2, env.left + 2);
  if (yStop !== null) {
    const text = stopCaption(look);
    const w = measure(text);
    const outward = look.direction === 'short' ? yStop - LH - 3 : yStop + 3;
    const inward = look.direction === 'short' ? yStop + 3 : yStop - LH - 3;
    at(text, p.risk, LOOK_PRIORITY - 0.2, [{ x, y: outward, w, h: LH }, { x, y: inward, w, h: LH }]);
  }
  if (yEntry !== null) {
    const text = look.entry;
    const w = measure(text);
    at(text, paneFocus(look).entry ? p.watch : p.muted, LOOK_PRIORITY - 0.1, [
      { x, y: yEntry - LH - 3, w, h: LH },
      { x, y: yEntry + 3, w, h: LH },
    ]);
  }
  if (yTop !== null && yBottom !== null) {
    const text = entryCaption(look);
    const w = measure(text);
    const lowY = Math.max(yTop, yBottom) + 3;
    const highY = Math.min(yTop, yBottom) - LH - 3;
    at(text, paneFocus(look).entry ? p.watch : p.muted, LOOK_PRIORITY, look.direction === 'short' ? [{ x, y: lowY, w, h: LH }, { x, y: highY, w, h: LH }] : [{ x, y: highY, w, h: LH }, { x, y: lowY, w, h: LH }]);
  }
  // the target in words, with the structural level's price and which way it lies
  if (look.target_price !== null) {
    const yt = y(look.target_price);
    const where = yt === null || yt > plot.h ? 'below' : yt < 0 ? 'above' : '';
    const text = `${look.target} ${formatPrice(look.target_price, lookDecimals(look))}${where ? ` ${where}` : ''}`;
    const w = measure(text);
    const ty = where === 'above' ? 4 : plot.h - LH - 4;
    const tx = Math.max(2, env.right - w - 2);
    at(text, p.muted, LOOK_PRIORITY + 0.4, [{ x: tx, y: ty, w, h: LH }]);
  }
  return out;
}

/** The entry pane's axis tags: words, not prices. */
export function lookAxisTags(scene: LookScene, palette: Palette): { price: number; text: string; back: string }[] {
  if (scene.pane !== 'entry') return [];
  const chosen = chosenOption(scene.look, scene.choice);
  if (!chosen) return [];
  const g = entryGeometry(chosen, scene.look.direction);
  return [
    { price: g.stop, text: 'stop', back: palette.risk },
    { price: g.entry, text: 'entry', back: palette.watch },
  ];
}
