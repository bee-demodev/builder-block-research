// Levels, zones, markers and the plan's risk / reward tool, drawn through Lightweight
// Charts' series-primitive API so they move with the chart on scroll and zoom (no DOM
// overlay that drifts). The drawing order is fixed:
//   1. zones (the core's zones, then the tool's reward and risk zones), behind the candles;
//   2. the candles (the series itself);
//   3. lines (levels, the "next" level, then the tool's target, stop and entry), markers
//      and the outcome diamond;
//   4. labels, last, each on a halo in the pane colour.
// The higher-timeframe column (see htf.ts) sits right of the last candle: its span
// hairlines draw with the zones, behind the candles; its candles with the lines; its
// C1 / C2 / C3 names with the labels. The risk / reward tool stops short of it.
// "Look for" (see LookLayer.ts) uses the room between the last candle and the column.
//  - zone: shaded band between top and bottom, from its start candle to its end
//    candle or the right edge, its name inside its right end (or beside it).
//  - level: a 1 px line (2 px for the "next" level) from its start candle to the right
//    edge, the short label above or below it, and a price tag in the role colour.
//  - marker: an arrow above or below its candle with the short label beside it.
//  - tool: reward and risk zones from its start candle to the right edge, 2 px entry,
//    stop and target lines over that span (dashed while planned or stale), captions
//    inside the zones when they have room, the fullest line name that fits.
// Labels never leave the plot: they are placed in priority order (the tool's lines,
// its captions, waiting and next, stop, entry, target, then the rest) and a label that
// would collide with one already placed tries its other spots and shorter wordings,
// then is dropped. Its line, arrow and price tag stay, and the full title shows on
// hover (see titleAt).
import type {
  AutoscaleInfo,
  IChartApiBase,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesApi,
  ISeriesPrimitive,
  ISeriesPrimitiveAxisView,
  Logical,
  PrimitivePaneViewZOrder,
  SeriesAttachedParameter,
  SeriesType,
  Time,
} from 'lightweight-charts';
import type { Overlays } from '../display';
import { formatPrice, sentenceCase } from '../format';
import { directionTone, markTone } from '../tones';
import type { Candle, Direction, Mark, Tool, ToolLine, ToolRole } from '../wire';
import { COLUMN_GAP, COLUMN_SLOT, barTitle, cappedRange, slotLogical, type Band, type HtfColumn } from './htf';
import { candleEmphasis, chosenOption, projectedCandles, type Ohlc } from './look';
import {
  drawLookFills,
  drawLookStrokes,
  drawOutlineCandle,
  lookAxisTags,
  lookLabels,
  lookScalePrices,
  type LookEnv,
  type LookScene,
} from './LookLayer';
import { TOOL_PRIORITY, distinctTags, labelPriority, markInRange, markerTextX, placeChoices, type Box, type LabelChoice, type PendingLabel } from './marks';
import { toneColor, withAlpha, type Palette } from './palette';
import { ZONE_ALPHA, captionFits, captionText, outcomePrice, toolLineLabels, toolLineStyle } from './tool';

type CanvasRenderingTarget2D = Parameters<IPrimitivePaneRenderer['draw']>[0];

export interface Scene {
  marks: readonly Mark[];
  tool: Tool | null;
  candles: readonly Candle[];
  direction: Direction;
  palette: Palette;
  decimals: number;
  overlays: Overlays;
  stale: boolean;
  /** Text size multiplier from the display options. */
  scale: number;
  /** The timeframe above, drawn right of the last candle; null for none. */
  column?: HtfColumn | null;
  /** Prices the column may widen the scale to (see capBand). */
  columnBand?: Band | null;
  /** What to look for, on this pane; null for none. */
  look?: LookScene | null;
}

interface Resolved {
  mark: Mark;
  /** What is drawn beside the line or arrow; "" draws none (the title still shows on hover). */
  label: string;
  color: string;
  priority: number;
}

interface Hit {
  box: Box;
  title: string;
  priority: number;
}


const ARROW_GAP = 4; // candle extreme to arrow tip
const ARROW_LEN = 11;
const ARROW_HALF_W = 4.5;
const TRADE_ROLES = new Set(['entry', 'stop', 'target']);
/** With a risk / reward tool the column sits further out, so the tool keeps room for its captions. */
const COLUMN_GAP_TOOL = 8;
/** Column candles' names rank after the trade's own labels and before the rest. */
const COLUMN_LABEL_PRIORITY = 3.5;

/** With "look for" the column sits further out still: its boxes and outlines need the room. */
const COLUMN_GAP_LOOK = 14;

/** Bars between the last candle and the column. */
export function columnGap(hasTool: boolean, hasLook = false): number {
  return hasLook ? COLUMN_GAP_LOOK : hasTool ? COLUMN_GAP_TOOL : COLUMN_GAP;
}

/** Outlined candles the entry pane's column adds for the setup's C1 and C2 while they are looked for. */
export function projectedSlots(look: LookScene | null | undefined): number {
  return look?.pane === 'entry' && look.look.options.length ? 2 : 0;
}

export class MarksPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApiBase<Time> | null = null;
  private series: ISeriesApi<SeriesType, Time> | null = null;
  private requestUpdate: (() => void) | null = null;
  private scene: Scene | null = null;
  private items: Resolved[] = [];
  private lastClose: number | null = null;
  private axisViews: ISeriesPrimitiveAxisView[] = [];
  private hits: Hit[] = [];
  private zoneHits: Hit[] = [];
  /** Column candles drawn this frame, as label obstacles. */
  private columnBoxes: Box[] = [];
  /** "Look for" outlines and hairlines drawn this frame, as label obstacles. */
  private lookBoxes: Box[] = [];

  private readonly zonesView: IPrimitivePaneView = {
    zOrder: (): PrimitivePaneViewZOrder => 'bottom',
    renderer: (): IPrimitivePaneRenderer => ({ draw: () => {}, drawBackground: (t) => this.drawZones(t) }),
  };
  private readonly linesView: IPrimitivePaneView = {
    zOrder: (): PrimitivePaneViewZOrder => 'top',
    renderer: (): IPrimitivePaneRenderer => ({ draw: (t) => this.drawTop(t) }),
  };

  setScene(scene: Scene): void {
    this.scene = scene;
    const { palette, direction, overlays } = scene;
    this.items = scene.marks
      .filter((m) => overlays.zones || m.kind !== 'zone')
      .map((mark) => ({
        mark,
        label: this.markLabel(mark, overlays),
        color: toneColor(palette, markTone(mark.role, direction)),
        priority: labelPriority(mark.role),
      }));
    this.lastClose = scene.candles[scene.candles.length - 1]?.close ?? null;
    this.axisViews = this.buildAxisViews();
    this.requestUpdate?.();
  }

  setCandles(candles: readonly Candle[]): void {
    if (!this.scene) return;
    this.scene = { ...this.scene, candles };
    this.lastClose = candles[candles.length - 1]?.close ?? null;
  }

  attached(param: SeriesAttachedParameter<Time>): void {
    this.chart = param.chart;
    this.series = param.series;
    this.requestUpdate = param.requestUpdate;
    this.axisViews = this.buildAxisViews();
  }

  detached(): void {
    this.chart = null;
    this.series = null;
    this.requestUpdate = null;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return [this.zonesView, this.linesView];
  }

  /** One tag per distinct price; Lightweight Charts moves overlapping tags apart. */
  priceAxisViews(): readonly ISeriesPrimitiveAxisView[] {
    return this.axisViews;
  }

  private markLabel(mark: Mark, overlays: Overlays): string {
    const text = mark.label || mark.title;
    if (mark.kind === 'marker') return overlays.markerLabels ? text : '';
    if (mark.kind === 'zone') return overlays.levelNames ? text : '';
    if (mark.kind === 'level' && !overlays.levelNames) {
      // Entry, stop and target keep their bare word: those lines always stay named.
      const role = mark.role.trim().toLowerCase();
      return TRADE_ROLES.has(role) ? sentenceCase(role) : '';
    }
    return text;
  }

  private toolColor(role: ToolRole): string {
    const s = this.scene!;
    const tool = s.tool!;
    if (role === 'stop') return s.palette.risk;
    if (role === 'target') return s.palette.reward;
    if (toolLineStyle(tool, 'entry', s.stale).next) return s.palette.watch;
    return toneColor(s.palette, directionTone(tool.direction));
  }

  private buildAxisViews(): ISeriesPrimitiveAxisView[] {
    const series = this.series;
    const scene = this.scene;
    if (!series || !scene) return [];
    const levels: { price: number; role: string; priority: number; color: string }[] = this.items
      .filter((it) => it.mark.kind === 'level' && it.mark.price !== null)
      .map((it) => ({ price: it.mark.price!, role: it.mark.role, priority: it.priority, color: it.color }));
    if (scene.tool) {
      for (const line of scene.tool.lines) levels.push({ price: line.price, role: line.role, priority: TOOL_PRIORITY[line.role], color: this.toolColor(line.role) });
    }
    const tags = distinctTags(levels, scene.decimals)
      .sort((a, b) => a.priority - b.priority)
      .map((it): ISeriesPrimitiveAxisView => ({
        coordinate: () => series.priceToCoordinate(it.price) ?? -100,
        text: () => formatPrice(it.price, scene.decimals),
        textColor: () => scene.palette.bg,
        backColor: () => it.color,
        visible: () => series.priceToCoordinate(it.price) !== null,
        tickVisible: () => false,
      }));
    // "look for" names its stop and entry on the axis in words: their prices are not known yet
    if (scene.look) {
      for (const tag of lookAxisTags(scene.look, scene.palette)) {
        tags.push({
          coordinate: () => series.priceToCoordinate(tag.price) ?? -100,
          text: () => tag.text,
          textColor: () => scene.palette.bg,
          backColor: () => tag.back,
          visible: () => series.priceToCoordinate(tag.price) !== null,
          tickVisible: () => false,
        });
      }
    }
    return tags;
  }

  /** Marks and the tool in the visible range widen the price scale so they are on screen. */
  autoscaleInfo(startTimePoint: Logical, endTimePoint: Logical): AutoscaleInfo | null {
    let min = Infinity;
    let max = -Infinity;
    let above = 0;
    let below = 0;
    const take = (p: number | null) => {
      if (p === null) return;
      if (p < min) min = p;
      if (p > max) max = p;
    };
    const room = ARROW_GAP + ARROW_LEN + this.labelH() + 4;
    for (const { mark } of this.items) {
      if (!markInRange(mark, startTimePoint, endTimePoint)) continue;
      if (mark.kind === 'marker') {
        // Room for the arrow and its label beyond the candle.
        if (this.markerAbove(mark)) above = room;
        else below = room;
        continue;
      }
      for (const p of mark.kind === 'zone' ? [mark.top, mark.bottom] : [mark.price]) take(p);
    }
    const tool = this.scene?.tool;
    if (tool && tool.start <= endTimePoint) {
      for (const p of [tool.entry, tool.stop, tool.target, tool.risk_zone.top, tool.risk_zone.bottom, tool.reward_zone.top, tool.reward_zone.bottom]) take(p);
    }
    // The column widens the scale only inside its band, so a tall daily candle cannot
    // flatten the 1h candles; the part past the band is cut at the pane edge.
    const column = this.scene?.column;
    if (column && column.bars.length && this.columnStart() <= endTimePoint) {
      const r = cappedRange(column, this.scene?.columnBand ?? null);
      if (r) {
        take(r.lo);
        take(r.hi);
      }
    }
    const look = this.scene?.look;
    if (look && this.lastIndex() <= endTimePoint) {
      // the other options (and a far reversal level on the entry pane) widen the scale only as far as the column may
      for (const p of lookScalePrices(look, this.scene?.columnBand ?? null)) take(p);
    }
    if (!Number.isFinite(min) && above === 0 && below === 0) return null;
    return {
      priceRange: Number.isFinite(min) ? { minValue: min, maxValue: max } : null,
      margins: above || below ? { above, below } : undefined,
    };
  }

  /**
   * The full titles of the marks under (x, y) in pane pixels, most important first,
   * one per line, for the hover tooltip. Two levels at one price both show here even
   * when only one of their labels fits on the chart.
   */
  titleAt(x: number, y: number): string | null {
    const under = this.hits
      .filter(({ box: b }) => x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h)
      .sort((a, b) => a.priority - b.priority);
    const titles = [...new Set(under.map((h) => h.title))];
    return titles.length ? titles.join('\n') : null;
  }

  private labelH(): number {
    return Math.round(13 * (this.scene?.scale ?? 1));
  }

  private font(weight = 500): string {
    return `${weight} ${Math.round(11 * (this.scene?.scale ?? 1) * 10) / 10}px Geist, system-ui, sans-serif`;
  }

  private markerAbove(mark: Mark): boolean {
    const c = mark.start !== null ? this.scene?.candles[mark.start] : undefined;
    if (!c) return true;
    return mark.price !== null ? mark.price >= (c.high + c.low) / 2 : true;
  }

  private x(index: number | null, fallback: number): number {
    if (index === null || !this.chart) return fallback;
    const x = this.chart.timeScale().logicalToCoordinate(index as Logical);
    return x === null ? fallback : x;
  }

  private halfBar(): number {
    return (this.chart?.timeScale().options().barSpacing ?? 6) / 2;
  }

  /** Left edge of the tool, in media pixels. */
  private toolLeft(tool: Tool): number {
    return Math.max(0, this.x(tool.start, 0) - this.halfBar());
  }

  /** Right edge of the tool: the column's left edge when there is one, else the pane's. */
  private toolRight(width: number): number {
    const left = this.columnLeft();
    return left === null ? width : Math.max(0, Math.min(width, left));
  }

  private lastIndex(): number {
    return (this.scene?.candles.length ?? 0) - 1;
  }

  /** Logical index where the column begins (its divider). */
  private columnStart(): number {
    return this.lastIndex() + this.gap() - 0.5;
  }

  private gap(): number {
    return columnGap(!!this.scene?.tool, !!this.scene?.look);
  }

  /** The room "look for" draws in: from just right of the last candle to just left of the column. */
  private lookEnv(width: number): LookEnv | null {
    const scene = this.scene;
    const series = this.series;
    if (!scene?.look || !series || !this.chart) return null;
    const lastX = this.x(this.lastIndex(), NaN);
    if (!Number.isFinite(lastX)) return null;
    const spacing = this.chart.timeScale().options().barSpacing;
    const columnLeft = this.columnLeft();
    return {
      series,
      palette: scene.palette,
      scene: scene.look,
      left: lastX + spacing,
      right: Math.min(width, columnLeft === null ? width : columnLeft) - 8,
      lastX,
      barSpacing: spacing,
      labelH: this.labelH(),
    };
  }

  /** The column's left edge in media pixels, or null without a column. */
  private columnLeft(): number | null {
    const column = this.scene?.column;
    if (!column || column.bars.length === 0 || !this.chart) return null;
    return this.logicalX(this.columnStart());
  }

  /**
   * Media x of a fractional logical index. Lightweight Charts maps only whole indexes
   * (it returns 0 for any other), so the fraction is added in bar spacings.
   */
  private logicalX(logical: number): number | null {
    if (!this.chart) return null;
    const ts = this.chart.timeScale();
    const whole = Math.floor(logical);
    const x = ts.logicalToCoordinate(whole as Logical);
    return x === null ? null : x + (logical - whole) * ts.options().barSpacing;
  }

  /** Centre and body width of a column candle, in media pixels. */
  private slotGeometry(slot: number): { x: number; body: number } | null {
    if (!this.chart) return null;
    const ts = this.chart.timeScale();
    const x = this.logicalX(slotLogical(this.lastIndex(), slot, this.gap()));
    if (x === null) return null;
    const body = Math.max(3, Math.min(16, ts.options().barSpacing * COLUMN_SLOT * 0.5));
    return { x, body };
  }

  private toolZones(tool: Tool): { kind: 'reward' | 'risk'; top: number; bottom: number; color: string; caption: string }[] {
    const s = this.scene!;
    return [
      { kind: 'reward', top: tool.reward_zone.top, bottom: tool.reward_zone.bottom, color: s.palette.reward, caption: captionText(tool.captions.reward) },
      { kind: 'risk', top: tool.risk_zone.top, bottom: tool.risk_zone.bottom, color: s.palette.risk, caption: captionText(tool.captions.risk) },
    ];
  }

  private drawZones(target: CanvasRenderingTarget2D): void {
    const series = this.series;
    const scene = this.scene;
    if (!series || !scene) return;
    const zoneHits: Hit[] = [];
    target.useBitmapCoordinateSpace(({ context: ctx, bitmapSize, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
      const width = bitmapSize.width / hr;
      for (const { mark, color, priority } of this.items) {
        if (mark.kind !== 'zone' || mark.top === null || mark.bottom === null) continue;
        const y1 = series.priceToCoordinate(mark.top);
        const y2 = series.priceToCoordinate(mark.bottom);
        if (y1 === null || y2 === null) continue;
        const x1 = Math.max(0, this.x(mark.start, 0) - this.halfBar());
        const x2 = Math.min(width, mark.end === null ? width : this.x(mark.end, width) + this.halfBar());
        if (x2 <= x1) continue;
        ctx.fillStyle = withAlpha(color, 0.11);
        const top = Math.round(Math.min(y1, y2) * vr);
        const bottom = Math.round(Math.max(y1, y2) * vr);
        ctx.fillRect(Math.round(x1 * hr), top, Math.round((x2 - x1) * hr), Math.max(1, bottom - top));
        const title = mark.title || mark.label;
        if (title) zoneHits.push({ box: { x: x1, y: Math.min(y1, y2), w: x2 - x1, h: Math.max(2, Math.abs(y2 - y1)) }, title, priority: priority + 10 });
      }

      this.drawSpans(ctx, hr, vr, width, bitmapSize.height);
      const env = this.lookEnv(width);
      if (env) drawLookFills(ctx, hr, vr, env, zoneHits);

      const tool = scene.tool;
      if (!tool || !scene.overlays.riskReward) return;
      const x1 = this.toolLeft(tool);
      const right = this.toolRight(width);
      if (x1 >= right) return;
      const hatched = toolLineStyle(tool, 'entry', scene.stale).dashed;
      for (const z of this.toolZones(tool)) {
        const y1 = series.priceToCoordinate(z.top);
        const y2 = series.priceToCoordinate(z.bottom);
        if (y1 === null || y2 === null) continue;
        const top = Math.round(Math.min(y1, y2) * vr);
        const bottom = Math.round(Math.max(y1, y2) * vr);
        const left = Math.round(x1 * hr);
        const w = Math.round(right * hr) - left;
        const h = Math.max(1, bottom - top);
        // Planned or stale: a lighter fill with diagonal hatching, as the window draws it.
        ctx.fillStyle = withAlpha(z.color, hatched ? ZONE_ALPHA * 0.6 : ZONE_ALPHA);
        ctx.fillRect(left, top, w, h);
        if (hatched) {
          ctx.save();
          ctx.beginPath();
          ctx.rect(left, top, w, h);
          ctx.clip();
          ctx.strokeStyle = withAlpha(z.color, 0.28);
          ctx.lineWidth = Math.max(1, Math.floor(hr));
          const step = Math.round(7 * hr);
          ctx.beginPath();
          for (let d = -h; d < w; d += step) {
            ctx.moveTo(left + d, bottom);
            ctx.lineTo(left + d + h, top);
          }
          ctx.stroke();
          ctx.restore();
        }
        const points = z.kind === 'reward' ? tool.reward_points : tool.risk_points;
        zoneHits.push({
          box: { x: x1, y: Math.min(y1, y2), w: right - x1, h: Math.max(2, Math.abs(y2 - y1)) },
          title: `${z.caption}, ${formatPrice(points, scene.decimals)} points`,
          priority: TOOL_PRIORITY.caption + 10,
        });
      }
    });
    // Zones draw first in a frame; the top pass starts from these.
    this.zoneHits = zoneHits;
  }

  private drawTop(target: CanvasRenderingTarget2D): void {
    const series = this.series;
    const scene = this.scene;
    if (!series || !scene) return;
    const hits: Hit[] = [...this.zoneHits];
    const lines: { x: number; y: number; color: string; label: string; title: string; price: number; priority: number; next: boolean }[] = [];
    const tool = scene.tool;
    const toolLines: { line: ToolLine; y: number; color: string }[] = [];

    // Lines in bitmap space so they stay sharp: levels first, the tool's lines over them.
    target.useBitmapCoordinateSpace(({ context: ctx, bitmapSize, horizontalPixelRatio: hr, verticalPixelRatio: vr }) => {
      const width = bitmapSize.width / hr;
      for (const { mark, color, label, priority } of this.items) {
        if (mark.kind !== 'level' || mark.price === null) continue;
        const y = series.priceToCoordinate(mark.price);
        if (y === null) continue;
        const x = Math.max(0, mark.start === null ? 0 : this.x(mark.start, 0) - this.halfBar());
        if (x >= width) continue;
        const next = mark.role.trim().toLowerCase() === 'next';
        lines.push({ x, y, color, label, title: mark.title || mark.label, price: mark.price, priority, next });
        const lineWidth = Math.max(1, Math.floor(vr)) * (next ? 2 : 1);
        const yb = Math.round(y * vr) - Math.floor(lineWidth / 2);
        ctx.fillStyle = color;
        ctx.fillRect(Math.round(x * hr), yb, bitmapSize.width - Math.round(x * hr), lineWidth);
        const title = mark.title || mark.label;
        if (title) hits.push({ box: { x, y: y - 4, w: width - x, h: 8 }, title, priority: priority + 5 });
      }

      this.drawColumn(ctx, hr, vr, hits);
      const lookEnv = this.lookEnv(width);
      this.lookBoxes = lookEnv ? drawLookStrokes(ctx, hr, vr, lookEnv, hits) : [];

      if (!tool) return;
      const x1 = this.toolLeft(tool);
      const right = this.toolRight(width);
      if (x1 >= right) return;
      const rightB = Math.round(right * hr);
      // Target and stop first, the entry last so it is never under them.
      const order: ToolRole[] = ['target', 'stop', 'entry'];
      for (const role of order) {
        const line = tool.lines.find((l) => l.role === role);
        if (!line) continue;
        const y = series.priceToCoordinate(line.price);
        if (y === null) continue;
        const color = this.toolColor(role);
        const style = toolLineStyle(tool, role, scene.stale);
        const lw = Math.max(2, Math.round(2 * vr));
        const yb = Math.round(y * vr) - Math.floor(lw / 2);
        ctx.fillStyle = color;
        const left = Math.round(x1 * hr);
        if (style.dashed) {
          const dash = Math.round(6 * hr);
          const gap = Math.round(4 * hr);
          for (let x = left; x < rightB; x += dash + gap) ctx.fillRect(x, yb, Math.min(dash, rightB - x), lw);
        } else {
          ctx.fillRect(left, yb, rightB - left, lw);
        }
        toolLines.push({ line, y, color });
        hits.push({ box: { x: x1, y: y - 5, w: right - x1, h: 10 }, title: `${line.names[0] ?? role} at ${formatPrice(line.price, scene.decimals)}`, priority: TOOL_PRIORITY[role] + 5 });
      }
    });

    target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      const plot = { w: mediaSize.width, h: mediaSize.height };
      const LH = this.labelH();
      ctx.textBaseline = 'alphabetic';
      const pending: PendingLabel[] = [];
      // No label may cover a trade line or the next level: they are what the trader acts on.
      const obstacles: Box[] = lines.filter((l) => l.next).map((l) => ({ x: l.x, y: l.y - 1.5, w: plot.w - l.x, h: 3 }));
      const toolRight = this.toolRight(plot.w);
      if (tool) {
        const x1 = this.toolLeft(tool);
        for (const { y } of toolLines) obstacles.push({ x: x1, y: y - 1.5, w: toolRight - x1, h: 3 });
      }
      // Nor a column candle, nor what "look for" draws.
      obstacles.push(...this.columnBoxes, ...this.lookBoxes);
      const measure = (text: string, weight = 500) => {
        ctx.font = this.font(weight);
        return ctx.measureText(text).width + 6;
      };

      // ---- the tool: captions, then its line labels ----
      if (tool && toolLines.length) {
        const x1 = this.toolLeft(tool);
        const zoneW = toolRight - x1;
        const shown: Record<'reward' | 'risk', boolean> = { reward: false, risk: false };
        if (scene.overlays.riskReward) {
          for (const z of this.toolZones(tool)) {
            const ya = series.priceToCoordinate(z.top);
            const yb = series.priceToCoordinate(z.bottom);
            if (ya === null || yb === null || !z.caption) continue;
            const w = measure(z.caption, 600);
            const h = Math.abs(yb - ya);
            if (!captionFits({ height: h, width: zoneW }, { width: w, height: LH })) continue;
            shown[z.kind] = true;
            const box = { x: x1 + 6, y: Math.min(ya, yb) + h / 2 - LH / 2, w, h: LH };
            pending.push({ title: z.caption, color: z.color, priority: TOOL_PRIORITY.caption, caption: true, choices: [{ text: z.caption, w, candidates: [box] }] });
          }
        }
        for (const { line, y, color } of toolLines) {
          const zone = line.role === 'stop' ? 'risk' : line.role === 'target' ? 'reward' : null;
          const texts = toolLineLabels(tool, line, { named: scene.overlays.levelNames, captionShown: zone ? shown[zone] : true });
          // Outside the tool first for the stop and target (away from the entry), so the
          // zone keeps room for its caption; the entry prefers the reward side. When the
          // zones are too thin for that, the label sits just left of the tool, on its line.
          const up = line.role === 'entry' ? tool.reward_zone.top > tool.entry : line.price > tool.entry;
          const choices = texts.map((text): LabelChoice => {
            const w = measure(text);
            const rightX = toolRight - w - 4;
            const above: Box = { x: rightX, y: y - 4 - LH, w, h: LH };
            const below: Box = { x: rightX, y: y + 4, w, h: LH };
            const before: Box = { x: x1 - w - 6, y: y - LH / 2, w, h: LH };
            return { text, w, candidates: up ? [above, below, before] : [below, above, before] };
          });
          pending.push({ title: line.names[0] ?? line.role, color, priority: TOOL_PRIORITY[line.role], choices });
        }
      }

      // ---- levels ----
      for (const { x, y, color, label, title, price, priority } of lines) {
        if (!label) continue;
        const w = measure(label);
        // Above the line when price is above the last close, below it otherwise; the
        // other side is the fallback when that spot is taken.
        const aboveBox = (lx: number): Box => ({ x: lx, y: y - 4 - LH, w, h: LH });
        const belowBox = (lx: number): Box => ({ x: lx, y: y + 3, w, h: LH });
        // A line that starts late (recent levels) gets its label just left of the start,
        // so it sits over empty history rather than on the newest candles.
        const leftOfStart = x > plot.w * 0.55 && x - w - 6 > 4;
        const lx = leftOfStart ? x - w - 6 : Math.min(Math.max(x + 2, 4), plot.w - w - 4);
        const below = this.lastClose !== null && price < this.lastClose;
        const candidates = below ? [belowBox(lx), aboveBox(lx)] : [aboveBox(lx), belowBox(lx)];
        pending.push({ title: title || label, color, priority, choices: [{ text: label, w, candidates }] });
      }

      // ---- zone names: inside the zone at its right end when it is tall enough, else beside it ----
      for (const { mark, color, label, priority } of this.items) {
        if (mark.kind !== 'zone' || !label || mark.top === null || mark.bottom === null) continue;
        const ya = series.priceToCoordinate(mark.top);
        const yb = series.priceToCoordinate(mark.bottom);
        if (ya === null || yb === null) continue;
        const x1 = Math.max(0, this.x(mark.start, 0) - this.halfBar());
        const x2 = Math.min(plot.w, mark.end === null ? plot.w : this.x(mark.end, plot.w) + this.halfBar());
        if (x2 <= x1) continue;
        const top = Math.min(ya, yb);
        const bottom = Math.max(ya, yb);
        const w = measure(label);
        const right = Math.min(x2, plot.w) - w - 4;
        const left = x1 + 4;
        const candidates: Box[] = [];
        if (bottom - top >= LH + 4) candidates.push({ x: right, y: top + 2, w, h: LH }, { x: left, y: top + 2, w, h: LH });
        candidates.push({ x: right, y: bottom + 3, w, h: LH }, { x: right, y: top - 3 - LH, w, h: LH }, { x: left, y: bottom + 3, w, h: LH }, { x: left, y: top - 3 - LH, w, h: LH });
        pending.push({ title: mark.title || label, color, priority: priority + 0.5, choices: [{ text: label, w, candidates }] });
      }

      // ---- markers, and the outcome diamond ----
      for (const { mark, color, label, priority } of this.items) {
        if (mark.kind !== 'marker' || mark.start === null) continue;
        const c = scene.candles[mark.start];
        if (!c) continue;
        const x = this.x(mark.start, NaN);
        if (!Number.isFinite(x) || x < -10 || x > plot.w + 10) continue;
        const above = this.markerAbove(mark);
        const yEdge = series.priceToCoordinate(above ? c.high : c.low);
        if (yEdge === null) continue;
        const tip = above ? yEdge - ARROW_GAP : yEdge + ARROW_GAP;
        this.drawArrow(ctx, x, tip, above, color);
        const title = mark.title || mark.label;
        const arrowTop = above ? tip - ARROW_LEN : tip;
        if (title) hits.push({ box: { x: x - 6, y: arrowTop - 2, w: 12, h: ARROW_LEN + 4 }, title, priority });
        if (!label) continue;
        const w = measure(label);
        const mid = arrowTop + ARROW_LEN / 2 - LH / 2;
        const outward = above ? arrowTop - 2 - LH : arrowTop + ARROW_LEN + 2;
        const tx = markerTextX(x, w, plot.w);
        pending.push({
          title: title || label,
          color,
          priority,
          choices: [
            {
              text: label,
              w,
              candidates: [
                { x: tx, y: outward, w, h: LH },
                { x: x - 8 - w, y: mid, w, h: LH },
                { x: x + 8, y: mid, w, h: LH },
                { x: tx, y: above ? outward - LH - 2 : outward + LH + 2, w, h: LH },
              ],
            },
          ],
        });
      }
      if (tool && tool.outcome_at !== null) {
        const price = outcomePrice(tool);
        const x = this.x(tool.outcome_at, NaN);
        const y = price === null ? null : series.priceToCoordinate(price);
        if (price !== null && y !== null && Number.isFinite(x)) {
          const color = tool.outcome === 'target_reached' ? scene.palette.reward : scene.palette.risk;
          this.drawDiamond(ctx, x, y, color, scene.palette.surface);
          const word = tool.outcome === 'target_reached' ? 'Target reached' : 'Stopped';
          hits.push({ box: { x: x - 7, y: y - 7, w: 14, h: 14 }, title: `${word} at ${formatPrice(price, scene.decimals)}`, priority: TOOL_PRIORITY.stop });
        }
      }

      // ---- the column's numbered candles (C1, C2, C3) and its timeframe ----
      this.columnLabels(ctx, plot, pending, measure);

      // ---- what to look for ----
      const lookEnv = this.lookEnv(plot.w);
      if (lookEnv) pending.push(...lookLabels(lookEnv, plot, measure));

      // ---- labels, last: most important first; ties keep their order ----
      const order = pending.map((l, i) => ({ l, i })).sort((a, b) => a.l.priority - b.l.priority || a.i - b.i);
      const placed = placeChoices(
        order.map((o) => o.l),
        plot,
        obstacles,
      );
      order.forEach(({ l }, k) => {
        const r = placed[k];
        if (!r) return;
        const { box } = r;
        // Halo in the pane colour keeps the label legible where it crosses a candle or a line.
        ctx.fillStyle = withAlpha(scene.palette.surface, l.caption ? 0.7 : 0.82);
        ctx.fillRect(box.x, box.y, box.w, box.h);
        ctx.font = this.font(l.caption ? 600 : 500);
        ctx.fillStyle = l.color;
        ctx.fillText(l.choices[r.choice]!.text, box.x + 3, box.y + LH - Math.round(3 * scene.scale));
        hits.push({ box, title: l.title, priority: l.priority });
      });
    });

    this.hits = hits;
  }

  /**
   * Hairlines at each column candle's high and low, across the lower-timeframe bars it
   * covers, and a faint divider where the column begins. Behind the candles.
   */
  private drawSpans(ctx: CanvasRenderingContext2D, hr: number, vr: number, width: number, heightB: number): void {
    const scene = this.scene!;
    const series = this.series!;
    const column = scene.column;
    if (!column || column.bars.length === 0) return;
    const half = this.halfBar();
    const lw = Math.max(1, Math.floor(vr));
    ctx.fillStyle = withAlpha(scene.palette.muted, 0.32);
    for (const bar of column.bars) {
      if (bar.from === null || bar.to === null) continue;
      const x1 = Math.max(0, this.x(bar.from, 0) - half);
      const x2 = Math.min(width, this.x(bar.to, width) + half);
      if (x2 <= x1) continue;
      for (const price of [bar.candle.high, bar.candle.low]) {
        const y = series.priceToCoordinate(price);
        if (y === null) continue;
        ctx.fillRect(Math.round(x1 * hr), Math.round(y * vr) - Math.floor(lw / 2), Math.round((x2 - x1) * hr), lw);
      }
    }
    const left = this.columnLeft();
    if (left !== null && left > 0 && left < width) {
      ctx.fillStyle = withAlpha(scene.palette.faint, 0.5);
      ctx.fillRect(Math.round(left * hr), 0, Math.max(1, Math.floor(hr)), heightB);
    }
  }

  /** The column's candles, in the pane's own candle colours; the forming one in outline. */
  private drawColumn(ctx: CanvasRenderingContext2D, hr: number, vr: number, hits: Hit[]): void {
    const scene = this.scene!;
    const series = this.series!;
    const column = scene.column;
    this.columnBoxes = [];
    if (!column) return;
    const p = scene.palette;
    for (const bar of column.bars) {
      const g = this.slotGeometry(bar.slot);
      const c = bar.candle;
      if (!g) continue;
      const yH = series.priceToCoordinate(c.high);
      const yL = series.priceToCoordinate(c.low);
      const yO = series.priceToCoordinate(c.open);
      const yC = series.priceToCoordinate(c.close);
      if (yH === null || yL === null || yO === null || yC === null) continue;
      const up = c.close >= c.open;
      const color = up ? p.up : p.down;
      const hollow = c.forming || (up && p.hollowUp);
      const cx = Math.round(g.x * hr);
      const bw = Math.max(3, Math.round(g.body * hr));
      const bx = cx - Math.floor(bw / 2);
      const wick = Math.max(1, Math.floor(hr));
      const top = Math.round(Math.min(yO, yC) * vr);
      const bottom = Math.max(top + 1, Math.round(Math.max(yO, yC) * vr));
      const yHb = Math.round(yH * vr);
      const yLb = Math.round(yL * vr);
      ctx.fillStyle = up ? color : p.downLine;
      // Wick above and below the body, not through it, so a hollow body stays hollow.
      ctx.fillRect(cx - Math.floor(wick / 2), yHb, wick, Math.max(0, top - yHb));
      ctx.fillRect(cx - Math.floor(wick / 2), bottom, wick, Math.max(0, yLb - bottom));
      if (hollow) {
        const b = Math.max(1, Math.floor(hr));
        ctx.fillRect(bx, top, bw, b);
        ctx.fillRect(bx, bottom - b, bw, b);
        ctx.fillRect(bx, top, b, bottom - top);
        ctx.fillRect(bx + bw - b, top, b, bottom - top);
      } else {
        // the body in the line colour, then the fill inside it: a black down body keeps a visible edge
        ctx.fillRect(bx, top, bw, bottom - top);
        if (!up && p.downLine !== color && bw > 2 && bottom - top > 2) {
          const b = Math.max(1, Math.floor(hr));
          ctx.fillStyle = color;
          ctx.fillRect(bx + b, top + b, bw - 2 * b, bottom - top - 2 * b);
        }
      }
      const box: Box = { x: g.x - g.body / 2 - 2, y: yH, w: g.body + 4, h: Math.max(2, yL - yH) };
      this.columnBoxes.push(box);
      hits.push({ box, title: barTitle(bar, column.timeframe, scene.decimals), priority: COLUMN_LABEL_PRIORITY });
    }
    // the setup's C1 and C2 still to come, in outline after the real candles
    for (const { slot, candle, color, title } of this.projectedColumn()) {
      const g = this.slotGeometry(slot);
      if (!g) continue;
      const box = drawOutlineCandle(ctx, hr, vr, series, candle, g.x, g.body, color);
      if (!box) continue;
      this.columnBoxes.push(box);
      hits.push({ box, title, priority: COLUMN_LABEL_PRIORITY });
    }
  }

  /** The entry pane's column: the setup's C1 and C2 to look for, after its real candles. */
  private projectedColumn(): { slot: number; candle: Ohlc; color: string; textColor: string; title: string; label: string }[] {
    const scene = this.scene;
    const look = scene?.look;
    const column = scene?.column;
    if (!scene || !look || !column || projectedSlots(look) === 0) return [];
    const chosen = chosenOption(look.look, look.choice);
    if (!chosen) return [];
    const emphasis = candleEmphasis(look.look);
    return projectedCandles(chosen, look.look.direction).map((candle, k) => ({
      slot: column.bars.length + k,
      candle,
      color: emphasis[k] ? scene.palette.watch : withAlpha(scene.palette.watch, 0.5),
      textColor: emphasis[k] ? scene.palette.watch : scene.palette.muted,
      title: (look.look.steps[k]?.label ?? 'C' + (k + 1)) + ' (what to look for, not a forecast)',
      label: 'C' + (k + 1),
    }));
  }

  /** C1 / C2 / C3 above (else beside, else below) their column candle; the timeframe at the column's foot. */
  private columnLabels(
    ctx: CanvasRenderingContext2D,
    plot: { w: number; h: number },
    pending: PendingLabel[],
    measure: (text: string, weight?: number) => number,
  ): void {
    const scene = this.scene!;
    const series = this.series!;
    const column = scene.column;
    if (!column || column.bars.length === 0) return;
    const LH = this.labelH();
    for (const bar of column.bars) {
      if (!bar.label) continue;
      const g = this.slotGeometry(bar.slot);
      const yH = series.priceToCoordinate(bar.candle.high);
      const yL = series.priceToCoordinate(bar.candle.low);
      if (!g || yH === null || yL === null) continue;
      const w = measure(bar.label);
      const x = Math.min(Math.max(g.x - w / 2, 2), plot.w - w - 2);
      // A wick cut at the pane edge keeps the name just inside that edge.
      const above: Box = { x, y: Math.max(2, yH - 4 - LH), w, h: LH };
      const beside: Box = { x: g.x + g.body / 2 + 3, y: Math.max(2, yH), w, h: LH };
      const below: Box = { x, y: Math.min(plot.h - LH - 2, yL + 4), w, h: LH };
      pending.push({
        title: barTitle(bar, column.timeframe, scene.decimals),
        color: scene.palette.text,
        priority: COLUMN_LABEL_PRIORITY,
        choices: [{ text: bar.label, w, candidates: [above, beside, below] }],
      });
    }
    for (const p of this.projectedColumn()) {
      const g = this.slotGeometry(p.slot);
      const yH = series.priceToCoordinate(p.candle.high);
      const yL = series.priceToCoordinate(p.candle.low);
      if (!g || yH === null || yL === null) continue;
      const w = measure(p.label);
      const x = Math.min(Math.max(g.x - w / 2, 2), plot.w - w - 2);
      pending.push({
        title: p.title,
        color: p.textColor,
        priority: COLUMN_LABEL_PRIORITY,
        choices: [{ text: p.label, w, candidates: [{ x, y: Math.max(2, yH - 4 - LH), w, h: LH }, { x, y: Math.min(plot.h - LH - 2, yL + 4), w, h: LH }] }],
      });
    }
    // The timeframe, small and quiet, at the foot of the column.
    const first = this.slotGeometry(0);
    if (first) {
      ctx.font = this.font(500);
      ctx.fillStyle = scene.palette.muted;
      const text = column.timeframe;
      const x = Math.min(first.x - first.body / 2, plot.w - ctx.measureText(text).width - 2);
      if (x > 0) ctx.fillText(text, x, plot.h - 4);
    }
  }

  private drawArrow(ctx: CanvasRenderingContext2D, x: number, tip: number, pointsDown: boolean, color: string): void {
    const dir = pointsDown ? -1 : 1; // the arrow body lies on this side of the tip
    const head = 5;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(x, tip);
    ctx.lineTo(x - ARROW_HALF_W, tip + dir * head);
    ctx.lineTo(x + ARROW_HALF_W, tip + dir * head);
    ctx.closePath();
    ctx.fill();
    const shaftTop = Math.min(tip + dir * head, tip + dir * ARROW_LEN);
    ctx.fillRect(Math.round(x) - 1, shaftTop, 2, ARROW_LEN - head);
  }

  private drawDiamond(ctx: CanvasRenderingContext2D, x: number, y: number, color: string, ring: string): void {
    const r = 5.5;
    ctx.beginPath();
    ctx.moveTo(x, y - r);
    ctx.lineTo(x + r, y);
    ctx.lineTo(x, y + r);
    ctx.lineTo(x - r, y);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = ring;
    ctx.stroke();
  }
}
