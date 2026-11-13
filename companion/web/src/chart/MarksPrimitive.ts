// Levels, zones, markers and the plan's risk / reward tool, drawn through Lightweight
// Charts' series-primitive API so they move with the chart on scroll and zoom (no DOM
// overlay that drifts). The drawing order is fixed:
//   1. zones (the core's zones, then the tool's reward and risk zones), behind the candles;
//   2. the candles (the series itself);
//   3. lines (levels, the "next" level, then the tool's target, stop and entry), markers
//      and the outcome diamond;
//   4. labels, last, each on a halo in the pane colour.
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
import { TOOL_PRIORITY, distinctTags, labelPriority, markInRange, markerTextX, placeChoices, type Box } from './marks';
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

interface LabelChoice {
  text: string;
  w: number;
  candidates: Box[];
}

interface PendingLabel {
  title: string;
  color: string;
  priority: number;
  choices: LabelChoice[];
  /** Captions are drawn in a heavier weight. */
  caption?: boolean;
}

const ARROW_GAP = 4; // candle extreme to arrow tip
const ARROW_LEN = 11;
const ARROW_HALF_W = 4.5;
const TRADE_ROLES = new Set(['entry', 'stop', 'target']);

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
    return distinctTags(levels, scene.decimals)
      .sort((a, b) => a.priority - b.priority)
      .map((it): ISeriesPrimitiveAxisView => ({
        coordinate: () => series.priceToCoordinate(it.price) ?? -100,
        text: () => formatPrice(it.price, scene.decimals),
        textColor: () => scene.palette.bg,
        backColor: () => it.color,
        visible: () => series.priceToCoordinate(it.price) !== null,
        tickVisible: () => false,
      }));
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

      const tool = scene.tool;
      if (!tool || !scene.overlays.riskReward) return;
      const x1 = this.toolLeft(tool);
      if (x1 >= width) return;
      const hatched = toolLineStyle(tool, 'entry', scene.stale).dashed;
      for (const z of this.toolZones(tool)) {
        const y1 = series.priceToCoordinate(z.top);
        const y2 = series.priceToCoordinate(z.bottom);
        if (y1 === null || y2 === null) continue;
        const top = Math.round(Math.min(y1, y2) * vr);
        const bottom = Math.round(Math.max(y1, y2) * vr);
        const left = Math.round(x1 * hr);
        const w = bitmapSize.width - left;
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
          box: { x: x1, y: Math.min(y1, y2), w: width - x1, h: Math.max(2, Math.abs(y2 - y1)) },
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

      if (!tool) return;
      const x1 = this.toolLeft(tool);
      if (x1 >= width) return;
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
          for (let x = left; x < bitmapSize.width; x += dash + gap) ctx.fillRect(x, yb, Math.min(dash, bitmapSize.width - x), lw);
        } else {
          ctx.fillRect(left, yb, bitmapSize.width - left, lw);
        }
        toolLines.push({ line, y, color });
        hits.push({ box: { x: x1, y: y - 5, w: width - x1, h: 10 }, title: `${line.names[0] ?? role} at ${formatPrice(line.price, scene.decimals)}`, priority: TOOL_PRIORITY[role] + 5 });
      }
    });

    target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      const plot = { w: mediaSize.width, h: mediaSize.height };
      const LH = this.labelH();
      ctx.textBaseline = 'alphabetic';
      const pending: PendingLabel[] = [];
      // No label may cover a trade line or the next level: they are what the trader acts on.
      const obstacles: Box[] = lines.filter((l) => l.next).map((l) => ({ x: l.x, y: l.y - 1.5, w: plot.w - l.x, h: 3 }));
      if (tool) {
        const x1 = this.toolLeft(tool);
        for (const { y } of toolLines) obstacles.push({ x: x1, y: y - 1.5, w: plot.w - x1, h: 3 });
      }
      const measure = (text: string, weight = 500) => {
        ctx.font = this.font(weight);
        return ctx.measureText(text).width + 6;
      };

      // ---- the tool: captions, then its line labels ----
      if (tool && toolLines.length) {
        const x1 = this.toolLeft(tool);
        const zoneW = plot.w - x1;
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
            const rightX = plot.w - w - 4;
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
