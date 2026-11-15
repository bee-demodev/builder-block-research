// The TCM Expansions chart: candles up to the replay cursor, and over them the range the
// trader picked (a box from the first expansion candle), its levels (range high and low,
// EQ, 50% of the last candle, CSD, then entry and stop) and a marker on each candle where
// a rule was decided. Drawn through a series primitive so it moves with scroll and zoom.
// A click on a candle picks the expansion it belongs to.
import {
  type AutoscaleInfo,
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type IChartApi,
  type IChartApiBase,
  type IPrimitivePaneRenderer,
  type IPrimitivePaneView,
  type ISeriesApi,
  type ISeriesPrimitive,
  type Logical,
  type MouseEventParams,
  type PrimitivePaneViewZOrder,
  type SeriesAttachedParameter,
  type SeriesType,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import { formatPrice } from '../format';
import { quietInk, toneColor, withAlpha, type Palette } from '../chart/palette';
import { drawOutlineCandle } from '../chart/LookLayer';
import type { Bar, EventKey, LevelKey, Reading } from './expansion';
import type { LessonMark, MarkTone } from './lessons';
import { SHADOW_SEMANTIC, type ShadowBranch } from './shadow';

type CanvasRenderingTarget2D = Parameters<IPrimitivePaneRenderer['draw']>[0];

/** Canvas text follows the Display menu's text size, as the rest of the companion's charts do. */
const font = (s: { scale: number }, bold = false) => `${bold ? 600 : 500} ${Math.round(12 * s.scale)}px 'Geist', sans-serif`;
const lh = (s: { scale: number }) => Math.round(15 * s.scale);

interface Scene {
  reading: Reading;
  palette: Palette;
  decimals: number;
  /** Last candle shown. */
  cursor: number;
  /** The shadow branch on show, drawn one slot right of the last candle. */
  shadow: ShadowBranch | null;
  /** Both branches' ghosts while the shadow is on: the scale spans both, so A and B never rescale the chart. */
  ghosts: readonly Bar[];
  /** The levels drawn are a shadow branch's ("Extends" redraws the range): their labels say so. */
  hypothetical: boolean;
  /** Text size (Display menu). */
  scale: number;
  /** A lesson's own drawings, already limited to the ones the replay has reached. */
  marks: readonly LessonMark[];
  /** Line labels carry their price ("EQ 21,591") only when asked (Settings); by default just the name. */
  showPrices: boolean;
  /** How far boxes and lines reach to the right (Settings), as TradingView's "extend" choice. */
  extend: ExtendMode;
}

/**
 * How far the range box, its levels and a lesson's open-ended zones and levels reach to the right:
 * to the last candle shown, a few candles past it (the default), or to the pane's right edge.
 */
export type ExtendMode = 'candle' | 'bars' | 'edge';
export const EXTEND_BARS = 5;

/** A line's label: its name, and its price when the setting asks for it. */
function lineLabel(name: string, price: number, s: Scene): string {
  return s.showPrices ? `${name} ${formatPrice(price, s.decimals)}` : name;
}

function markColor(tone: MarkTone | undefined, p: Palette): string {
  return tone === 'watch' ? p.watch : tone === 'bull' ? p.bull : tone === 'bear' ? p.bear : quietInk(p);
}

interface LineStyleSpec {
  color: string;
  width: number;
  dash: number[];
}

function levelStyle(key: LevelKey, s: Scene): LineStyleSpec {
  const p = s.palette;
  const ink = quietInk(p);
  const idea = s.reading.idea === 'long' ? p.long : p.short;
  switch (key) {
    case 'high':
    case 'low':
      return { color: p.text, width: 1, dash: [] };
    case 'eq':
      return { color: ink, width: 1.5, dash: [6, 4] };
    case 'half':
      return { color: ink, width: 1, dash: [2, 3] };
    case 'csd':
      return { color: p.watch, width: 2, dash: [] };
    case 'entry':
      return { color: idea, width: 2, dash: [] };
    case 'stop':
      return { color: p.risk, width: 1.5, dash: [4, 3] };
  }
}

function eventColor(key: EventKey, s: Scene): string {
  const p = s.palette;
  if (key === 'void') return p.bear;
  if (key === 'fill' || key === 'target') return s.reading.idea === 'long' ? p.long : p.short;
  if (key === 'csd') return p.watch;
  return p.text;
}

class RangePrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApiBase<Time> | null = null;
  private series: ISeriesApi<SeriesType, Time> | null = null;
  private requestUpdate: (() => void) | null = null;
  private scene: Scene | null = null;
  private bars: readonly Bar[] = [];

  private readonly boxView: IPrimitivePaneView = {
    zOrder: (): PrimitivePaneViewZOrder => 'bottom',
    renderer: (): IPrimitivePaneRenderer => ({ draw: () => {}, drawBackground: (t) => this.drawBox(t) }),
  };
  private readonly topView: IPrimitivePaneView = {
    zOrder: (): PrimitivePaneViewZOrder => 'top',
    renderer: (): IPrimitivePaneRenderer => ({ draw: (t) => this.drawTop(t) }),
  };

  attached(param: SeriesAttachedParameter<Time>): void {
    this.chart = param.chart;
    this.series = param.series;
    this.requestUpdate = param.requestUpdate;
  }

  detached(): void {
    this.chart = this.series = this.requestUpdate = null;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return [this.boxView, this.topView];
  }

  /**
   * While a shadow is shown, the scale spans both ghosts and the whole range, so neither ghost is cut off,
   * switching A and B never rescales, and the target a ghost heads for is always in view.
   */
  autoscaleInfo(): AutoscaleInfo | null {
    const s = this.scene;
    if (!s) return null;
    // a lesson's levels and zones are drawn where the lesson needs them: keep them in view too
    const prices = s.marks.flatMap((m) => (m.kind === 'level' ? [m.price] : m.kind === 'zone' ? [m.top, m.bottom] : []));
    if (s.ghosts.length) prices.push(s.reading.range.low, s.reading.range.high, ...s.ghosts.flatMap((c) => [c.low, c.high]));
    return prices.length ? { priceRange: { minValue: Math.min(...prices), maxValue: Math.max(...prices) } } : null;
  }

  set(scene: Scene | null, bars: readonly Bar[]): void {
    this.scene = scene;
    this.bars = bars;
    this.requestUpdate?.();
  }

  private x(i: number): number | null {
    return this.chart?.timeScale().logicalToCoordinate(i as Logical) ?? null;
  }

  private half(): number {
    return Math.max(2, (this.chart?.timeScale().options().barSpacing ?? 6) / 2);
  }

  /** Where boxes and lines stop on the right, in media pixels, for the chosen extend mode. */
  private reach(s: Scene, width: number): number {
    if (s.extend === 'edge') return width;
    const x = this.x(s.cursor + (s.extend === 'bars' ? EXTEND_BARS : 0));
    return x === null ? width : Math.min(width, x + this.half());
  }

  private drawBox(target: CanvasRenderingTarget2D): void {
    const s = this.scene;
    const series = this.series;
    if (!s || !series) return;
    const { range, voidAt } = s.reading;
    target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      const x0 = this.x(range.start);
      const yA = series.priceToCoordinate(range.high);
      const yB = series.priceToCoordinate(range.low);
      if (x0 === null || yA === null || yB === null) return;
      const left = x0 - this.half();
      const endX = voidAt !== null ? this.x(voidAt) : null;
      const right = endX !== null ? endX + this.half() : this.reach(s, mediaSize.width);
      const top = Math.min(yA, yB);
      const h = Math.abs(yB - yA);
      ctx.fillStyle = withAlpha(s.palette.text, 0.07);
      ctx.fillRect(left, top, right - left, h);
      // The expansion candles themselves, a shade darker: the run that made the range.
      const xe = this.x(range.end);
      if (xe !== null) {
        ctx.fillStyle = withAlpha(s.palette.text, 0.06);
        ctx.fillRect(left, top, xe + this.half() - left, h);
      }
      // A lesson's zones (order blocks, FVGs, key levels), faint, with their name in the top left corner,
      // and its session times as dashed verticals named at the foot of the pane.
      for (const m of s.marks) {
        if (m.kind === 'zone') {
          const xa = this.x(m.from);
          const xb = m.to !== undefined ? this.x(m.to) : null;
          const ya = series.priceToCoordinate(m.top);
          const yb = series.priceToCoordinate(m.bottom);
          if (xa === null || ya === null || yb === null) continue;
          const color = markColor(m.tone, s.palette);
          const zl = xa - this.half();
          const zr = xb !== null ? xb + this.half() : this.reach(s, mediaSize.width);
          ctx.fillStyle = withAlpha(color, 0.12);
          ctx.fillRect(zl, Math.min(ya, yb), zr - zl, Math.max(1, Math.abs(yb - ya)));
        } else if (m.kind === 'time') {
          const xt = this.x(m.index);
          if (xt === null) continue;
          const xx = Math.round(xt - this.half()) + 0.5;
          ctx.save();
          ctx.strokeStyle = quietInk(s.palette);
          ctx.setLineDash([3, 3]);
          ctx.beginPath();
          ctx.moveTo(xx, 0);
          ctx.lineTo(xx, mediaSize.height);
          ctx.stroke();
          ctx.restore();
          ctx.font = font(s, true);
          ctx.textAlign = 'left';
          ctx.textBaseline = 'bottom';
          ctx.fillStyle = s.palette.muted;
          ctx.fillText(m.label, xx + 4, mediaSize.height - 4);
        }
      }
      // The shadow's column: the one slot the next candle will take, full height, faint.
      const xs = s.shadow ? this.x(s.cursor + 1) : null;
      if (xs !== null) {
        const w = Math.max(16, this.half() * 3.2);
        ctx.fillStyle = withAlpha(s.palette.text, 0.045);
        ctx.fillRect(xs - w / 2, 0, w, mediaSize.height);
      }
    });
  }

  private drawTop(target: CanvasRenderingTarget2D): void {
    const s = this.scene;
    const series = this.series;
    if (!s || !series) return;
    const { reading } = s;
    if (s.shadow) this.drawGhost(target, s.shadow, s);
    target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      const right = mediaSize.width;
      // where lines stop (Settings: extend), and where a void range's levels stop (where it died)
      const end = this.reach(s, right);
      const voidX = reading.voidAt !== null ? this.x(reading.voidAt) : null;
      const lineEnd = voidX !== null ? Math.min(voidX + this.half(), end) : end;
      // Lines, then their labels at the right end, spread apart so none overlap.
      const labels: { y: number; text: string; color: string; bold: boolean }[] = [];
      for (const level of reading.levels) {
        const y = series.priceToCoordinate(level.price);
        const x0 = this.x(level.from);
        if (y === null || x0 === null) continue;
        const st = levelStyle(level.key, s);
        ctx.save();
        ctx.strokeStyle = st.color;
        ctx.lineWidth = st.width;
        ctx.setLineDash(st.dash);
        ctx.beginPath();
        const yy = Math.round(y) + (st.width % 2 ? 0.5 : 0);
        ctx.moveTo(x0 - this.half(), yy);
        ctx.lineTo(lineEnd, yy);
        ctx.stroke();
        if (lineEnd < end) {
          // A void range: the level stops where it died; a faint dotted lead takes it to its label.
          ctx.globalAlpha = 0.35;
          ctx.lineWidth = 1;
          ctx.setLineDash([1, 3]);
          ctx.beginPath();
          ctx.moveTo(lineEnd, yy);
          ctx.lineTo(end, yy);
          ctx.stroke();
        }
        ctx.restore();
        labels.push({ y, text: `${s.hypothetical ? 'If B: ' : ''}${lineLabel(level.label, level.price, s)}`, color: st.color === s.palette.text ? s.palette.text : st.color, bold: level.key === 'csd' || level.key === 'entry' });
      }
      placeLabels(labels, lh(s) + 1);

      // A lesson's zone names, over the candles (the fills are drawn behind them), on a backing.
      for (const m of s.marks) {
        if (m.kind !== 'zone') continue;
        const xa = this.x(m.from);
        const ya = series.priceToCoordinate(m.top);
        if (xa === null || ya === null) continue;
        const zl = xa - this.half();
        ctx.font = font(s);
        ctx.textAlign = 'left';
        ctx.textBaseline = 'bottom';
        const lw = ctx.measureText(m.label).width;
        ctx.fillStyle = withAlpha(s.palette.surface, 0.88);
        ctx.fillRect(zl + 1, ya - lh(s) - 1, lw + 6, lh(s));
        ctx.fillStyle = markColor(m.tone, s.palette);
        ctx.fillText(m.label, zl + 4, ya - 3);
      }

      // A lesson's reference levels: dashed, named at their left end, above the line.
      for (const m of s.marks) {
        if (m.kind !== 'level') continue;
        const y = series.priceToCoordinate(m.price);
        const x0 = this.x(m.from);
        if (y === null || x0 === null) continue;
        const color = markColor(m.tone, s.palette);
        const yy = Math.round(y) + 0.5;
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.moveTo(x0 - this.half(), yy);
        ctx.lineTo(Math.max(end, x0 + this.half()), yy);
        ctx.stroke();
        ctx.restore();
        ctx.font = font(s);
        ctx.textAlign = 'left';
        ctx.textBaseline = 'bottom';
        const text = lineLabel(m.label, m.price, s);
        const tw = ctx.measureText(text).width;
        ctx.fillStyle = withAlpha(s.palette.surface, 0.88);
        ctx.fillRect(x0 - this.half() + 1, yy - lh(s) - 1, tw + 6, lh(s));
        ctx.fillStyle = color;
        ctx.fillText(text, x0 - this.half() + 4, yy - 3);
      }
      // Labels sit at the end of their line, as TradingView names a line at its right end; at the pane's
      // edge (extend to the edge, or a line ending too close to it) they are right-aligned inside it.
      ctx.textBaseline = 'middle';
      for (const l of labels) {
        ctx.font = font(s, l.bold);
        const w = ctx.measureText(l.text).width;
        const afterLine = s.extend !== 'edge' && end + 6 + w + 4 <= right - 4;
        const x = afterLine ? end + 6 : right - 8 - w;
        ctx.fillStyle = withAlpha(s.palette.surface, 0.88);
        ctx.fillRect(x - 4, l.y - lh(s) / 2, w + 8, lh(s));
        ctx.textAlign = 'left';
        ctx.fillStyle = l.color;
        ctx.fillText(l.text, x, l.y + 0.5);
      }

      // The shadow's chip and the column's "What if" (the ghost itself is drawn in bitmap space below).
      if (s.shadow) this.drawGhostLabels(ctx, s.shadow, s);

      // A short tick and a word on each candle where a rule was decided. A word that would
      // touch one already drawn moves further from the candle.
      ctx.textAlign = 'center';
      ctx.font = font(s, true);
      const placed: { l: number; r: number; t: number; b: number }[] = [];
      const hits = (bx: { l: number; r: number; t: number; b: number }) => placed.some((o) => bx.l < o.r && bx.r > o.l && bx.t < o.b && bx.b > o.t);
      // the rules' own markers, then a lesson's words on its candles (failure swing, breaker, ...)
      const words = [
        ...reading.events.map((ev) => ({ index: ev.index, label: ev.label, above: ev.above, color: eventColor(ev.key, s) })),
        ...s.marks.flatMap((m) => (m.kind === 'tag' ? [{ index: m.index, label: m.label, above: m.above, color: markColor(m.tone, s.palette) }] : [])),
      ];
      for (const ev of words) {
        const bar = this.bars[ev.index];
        const x = this.x(ev.index);
        if (!bar || x === null || ev.index > s.cursor) continue;
        const edge = series.priceToCoordinate(ev.above ? bar.high : bar.low);
        if (edge === null) continue;
        const dir = ev.above ? -1 : 1;
        const w = ctx.measureText(ev.label).width + 6;
        let cy = 0;
        let box = { l: 0, r: 0, t: 0, b: 0 };
        for (let n = 0; n < 8; n++) {
          cy = edge + dir * (12 + n * (lh(s) + 2) + lh(s) / 2);
          box = { l: x - w / 2, r: x + w / 2, t: cy - lh(s) / 2, b: cy + lh(s) / 2 };
          if (!hits(box)) break;
        }
        placed.push(box);
        const color = ev.color;
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(Math.round(x) + 0.5, edge + dir * 4);
        ctx.lineTo(Math.round(x) + 0.5, edge + dir * 10);
        ctx.stroke();
        ctx.fillStyle = withAlpha(s.palette.surface, 0.9);
        ctx.fillRect(box.l, box.t, w, lh(s));
        ctx.fillStyle = color;
        ctx.fillText(ev.label, x, cy + 0.5);
      }
      if (s.shadow) this.drawWhatIf(ctx, s);
    });
  }

  /**
   * The shadow's ghost candle, drawn as the TTrades panes draw a projected candle: a
   * crisp outline (drawOutlineCandle, bitmap space), here in the candle's own direction
   * colour with a pale body, so up still reads as up. Whether the branch is on plan is
   * said by the lettered chip above it and the caption, never by the candle's colour.
   */
  private drawGhost(target: CanvasRenderingTarget2D, branch: ShadowBranch, s: Scene): void {
    const series = this.series;
    const x = this.x(s.cursor + 1);
    if (!series || x === null) return;
    const c = branch.candle;
    const p = s.palette;
    const upCandle = c.close >= c.open;
    const body = Math.max(5, this.half() * 1.5);
    target.useBitmapCoordinateSpace(({ context: ctx, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
      const yO = series.priceToCoordinate(c.open);
      const yC = series.priceToCoordinate(c.close);
      if (yO === null || yC === null) return;
      const bw = Math.max(3, Math.round(body * hr));
      const bx = Math.round(x * hr) - Math.floor(bw / 2);
      const top = Math.round(Math.min(yO, yC) * vr);
      const bottom = Math.max(top + 2, Math.round(Math.max(yO, yC) * vr));
      // the body, paler than a real candle: up keeps its own fill (none when the scheme draws up candles hollow)
      if (!(upCandle && p.hollowUp)) {
        ctx.fillStyle = withAlpha(upCandle ? p.up : p.down, upCandle ? 0.28 : 0.16);
        ctx.fillRect(bx, top, bw, bottom - top);
      }
      drawOutlineCandle(ctx, hr, vr, series, c, x, body, withAlpha(upCandle ? p.upLine : p.downLine, 0.6));
    });
  }

  /** The chip with the branch's letter above the ghost, and the column's "What if". */
  private drawGhostLabels(ctx: CanvasRenderingContext2D, branch: ShadowBranch, s: Scene): void {
    const series = this.series;
    const x = this.x(s.cursor + 1);
    if (!series || x === null) return;
    const yH = series.priceToCoordinate(branch.candle.high);
    if (yH === null) return;
    const color = toneColor(s.palette, SHADOW_SEMANTIC[branch.tone]);
    ctx.save();
    ctx.font = font(s, true);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const w = ctx.measureText(branch.key).width + 10;
    // Above the ghost's high, moved further up while it would sit on a level line.
    const lines = s.reading.levels.flatMap((l) => {
      const y = series.priceToCoordinate(l.price);
      return y === null ? [] : [y as number];
    });
    let cy = yH - 6 - lh(s) / 2;
    for (let n = 0; n < 4 && lines.some((y) => Math.abs(y - cy) < lh(s) / 2 + 2); n++) cy -= lh(s) / 2 + 3;
    ctx.fillStyle = s.palette.surface;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(Math.round(x - w / 2) + 0.5, Math.round(cy - lh(s) / 2) + 0.5, Math.round(w), lh(s), 3);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.fillText(branch.key, x, cy + 0.5);
    ctx.restore();
  }

  /** The column's "What if", drawn after everything else on a pane-coloured backing, so no label covers it. */
  private drawWhatIf(ctx: CanvasRenderingContext2D, s: Scene): void {
    const x = this.x(s.cursor + 1);
    if (x === null) return;
    ctx.save();
    ctx.font = font(s);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const w = ctx.measureText('What if').width + 8;
    ctx.fillStyle = withAlpha(s.palette.surface, 0.92);
    ctx.fillRect(Math.round(x - w / 2), 4, Math.round(w), lh(s));
    ctx.fillStyle = s.palette.muted;
    ctx.fillText('What if', x, 6);
    ctx.restore();
  }
}

/** Move labels apart (in place) so no two are closer than `gap`, keeping their order by y. */
export function placeLabels<T extends { y: number }>(labels: T[], gap: number): void {
  labels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) {
    const prev = labels[i - 1]!;
    const cur = labels[i]!;
    if (cur.y - prev.y < gap) cur.y = prev.y + gap;
  }
}

export class RangeChart {
  private readonly chart: IChartApi;
  private readonly series: ISeriesApi<'Candlestick', Time>;
  private readonly primitive = new RangePrimitive();
  private bars: readonly Bar[] = [];
  private cursor = -1;
  private fitKey = '';
  private reading: Reading | null = null;
  private shadow: ShadowBranch | null = null;
  private ghosts: readonly Bar[] = [];
  private hypothetical = false;
  private marks: readonly LessonMark[] = [];
  private showPrices = false;
  private extend: ExtendMode = 'bars';
  private scale = 1;
  private decimals = 2;

  constructor(
    container: HTMLElement,
    private palette: Palette,
    private readonly onPick: (index: number) => void,
    private readonly onHover: (index: number | null) => void,
  ) {
    this.chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: palette.surface },
        textColor: palette.text,
        fontFamily: "'Geist Mono', ui-monospace, monospace",
        fontSize: 12,
        attributionLogo: false,
      },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.12, bottom: 0.12 } },
      // A replay appends candles: the view stays put so the expansion does not slide away.
      timeScale: { borderVisible: false, rightOffset: 14, timeVisible: true, secondsVisible: false, shiftVisibleRangeOnNewBar: false },
      localization: { priceFormatter: (p: number) => formatPrice(p, this.decimals) },
      crosshair: { mode: CrosshairMode.Normal },
    });
    this.series = this.chart.addSeries(CandlestickSeries, { lastValueVisible: false, priceLineVisible: false, borderVisible: true, wickVisible: true });
    this.series.attachPrimitive(this.primitive);
    this.applyPalette();
    this.chart.subscribeClick(this.handleClick);
    this.chart.subscribeCrosshairMove(this.handleMove);
  }

  destroy(): void {
    this.chart.unsubscribeClick(this.handleClick);
    this.chart.unsubscribeCrosshairMove(this.handleMove);
    this.chart.remove();
  }

  setPalette(palette: Palette): void {
    this.palette = palette;
    this.applyPalette();
    this.pushScene();
  }

  /**
   * Show bars[0..cursor]. `fitKey` names the data set: a new key (another lesson, symbol
   * or chart) refits the view; the same one keeps the trader's zoom and scroll. New
   * candles on the end of the same data are appended in place. `follow` (live, at the
   * latest candle): the view moves with each new candle.
   */
  setBars(bars: readonly Bar[], cursor: number, decimals: number, fitKey: string, follow = false): void {
    const old = this.bars;
    const appended =
      fitKey === this.fitKey &&
      cursor >= this.cursor &&
      this.cursor >= 0 &&
      bars[0]?.t === old[0]?.t &&
      bars[this.cursor]?.t === old[this.cursor]?.t;
    this.chart.timeScale().applyOptions({ shiftVisibleRangeOnNewBar: follow });
    if (decimals !== this.decimals || !appended) {
      this.series.applyOptions({ priceFormat: { type: 'price', precision: decimals, minMove: 1 / 10 ** decimals } });
    }
    this.decimals = decimals;
    if (appended) {
      // the last shown candle may have changed (a tick), then any new ones
      for (let i = this.cursor; i <= cursor; i++) this.series.update(toData(bars[i]!));
    } else {
      this.series.setData(bars.slice(0, cursor + 1).map(toData));
    }
    this.bars = bars;
    this.cursor = cursor;
    if (fitKey !== this.fitKey) {
      this.fitKey = fitKey;
      // Room for every candle of the data set, so stepping a replay fills the space on the right.
      const n = bars.length;
      const show = Math.min(n, 70);
      this.chart.timeScale().setVisibleLogicalRange({ from: n - show - 0.5, to: n - 1 + 14 });
    } else if (!appended && follow) {
      this.chart.timeScale().scrollToRealTime();
    }
    this.pushScene();
  }

  setReading(reading: Reading | null, shadow: ShadowBranch | null = null, ghosts: readonly Bar[] = [], hypothetical = false): void {
    this.reading = reading;
    this.shadow = shadow;
    this.ghosts = shadow ? ghosts : [];
    this.hypothetical = !!shadow && hypothetical;
    this.pushScene();
  }

  /** A lesson's drawings the replay has reached (none outside practice). */
  setMarks(marks: readonly LessonMark[]): void {
    this.marks = marks;
    this.pushScene();
  }

  /** Prices on the line labels (Settings, off by default); the price axis always shows them. */
  setShowPrices(show: boolean): void {
    if (show === this.showPrices) return;
    this.showPrices = show;
    this.pushScene();
  }

  /** How far boxes and lines reach to the right (Settings). */
  setExtend(extend: ExtendMode): void {
    if (extend === this.extend) return;
    this.extend = extend;
    this.pushScene();
  }

  /** Text size from the Display menu: the axis and every label on the canvas follow it. */
  setScale(scale: number): void {
    if (scale === this.scale) return;
    this.scale = scale;
    this.chart.applyOptions({ layout: { fontSize: Math.round(12 * scale) } });
    this.pushScene();
  }

  private pushScene(): void {
    this.primitive.set(this.reading ? { reading: this.reading, palette: this.palette, decimals: this.decimals, cursor: this.cursor, shadow: this.shadow, ghosts: this.ghosts, hypothetical: this.hypothetical, scale: this.scale, marks: this.marks, showPrices: this.showPrices, extend: this.extend } : null, this.bars);
  }

  private applyPalette(): void {
    const p = this.palette;
    this.chart.applyOptions({
      layout: { background: { type: ColorType.Solid, color: p.surface }, textColor: p.text },
      crosshair: {
        vertLine: { color: p.faint, style: LineStyle.Dashed, width: 1, labelBackgroundColor: p.raised },
        horzLine: { color: p.faint, style: LineStyle.Dashed, width: 1, labelBackgroundColor: p.raised },
      },
    });
    this.series.applyOptions({
      upColor: p.hollowUp ? withAlpha(p.surface, 0) : p.up,
      downColor: p.down,
      borderUpColor: p.upLine,
      borderDownColor: p.downLine,
      wickUpColor: p.upLine,
      wickDownColor: p.downLine,
    });
  }

  private indexAt(param: MouseEventParams<Time>): number | null {
    if (param.logical === undefined || !param.point) return null;
    const i = Math.round(param.logical);
    return i >= 0 && i <= this.cursor ? i : null;
  }

  private readonly handleClick = (param: MouseEventParams<Time>): void => {
    const i = this.indexAt(param);
    if (i !== null) this.onPick(i);
  };

  private readonly handleMove = (param: MouseEventParams<Time>): void => {
    this.onHover(this.indexAt(param));
  };
}

const toData = (b: Bar) => ({ time: b.t as UTCTimestamp, open: b.open, high: b.high, low: b.low, close: b.close });
