// One Lightweight Charts instance per pane. Created once per mount; snapshots and
// ticks update it. A tick replaces or appends the last bar with series.update()
// instead of rebuilding the chart.
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  LineStyle,
  TickMarkType,
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import { DEFAULT_DISPLAY, layerMarks, type Overlays } from '../display';
import { axisLabel, crosshairLabel, formatPrice, priceDecimals } from '../format';
import type { Candle, ChartView, Direction, Mark, Tool } from '../wire';
import { COLUMN_SLOT, type Band, type HtfColumn } from './htf';
import type { LookScene } from './LookLayer';
import { MarksPrimitive, columnGap, projectedSlots } from './MarksPrimitive';
import { diffCandles, initialWindowStart, partitionMarks } from './marks';
import { withAlpha, type Palette } from './palette';

/** What the chart draws besides the candles, from the display options and the status. */
export interface ChartOptions {
  overlays: Overlays;
  stale: boolean;
  scale: number;
}

/** Bars of empty space right of the last candle; more on a chart with a plan, so its zones have room. */
const RIGHT_PAD = 4;
const RIGHT_PAD_TOOL = 20;

export interface MarkHover {
  title: string;
  x: number;
  y: number;
}

export class CandleChart {
  private readonly chart: IChartApi;
  private readonly series: ISeriesApi<'Candlestick', Time>;
  private readonly marksPrimitive = new MarksPrimitive();
  private candles: readonly Candle[] = [];
  private marks: readonly Mark[] | null = null;
  private tool: Tool | null = null;
  private column: HtfColumn | null = null;
  private columnBand: Band | null = null;
  private look: LookScene | null = null;
  private direction: Direction = '';
  private opts: ChartOptions = { overlays: DEFAULT_DISPLAY.overlays, stale: false, scale: 1 };
  private byTime = new Map<number, Candle>();
  private decimals = 2;
  private intraday = true;

  constructor(
    container: HTMLElement,
    private palette: Palette,
    private readonly onHover: (candle: Candle | null) => void,
    /** Candles the chart opens on; the rest is reachable by scrolling. */
    private readonly visibleBars: number,
    private readonly onMarkHover: (hover: MarkHover | null) => void = () => {},
  ) {
    this.chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: palette.surface },
        textColor: palette.muted,
        fontFamily: "'Geist Mono', ui-monospace, monospace",
        fontSize: 10,
        // Attribution is given in the footer with a link to tradingview.com and in
        // the NOTICE file, as the licence asks; the on-chart logo is turned off.
        attributionLogo: false,
      },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.08, bottom: 0.08 } },
      timeScale: {
        borderVisible: false,
        rightOffset: RIGHT_PAD,
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: Time, type: TickMarkType) => this.tickLabel(time, type),
      },
      localization: {
        priceFormatter: (p: number) => formatPrice(p, this.decimals),
        tickmarksPriceFormatter: (ps: number[]) => ps.map((p) => formatPrice(p, 0)),
        timeFormatter: (time: Time) => crosshairLabel(time as number, this.intraday),
      },
      crosshair: { mode: CrosshairMode.Normal },
    });
    this.series = this.chart.addSeries(CandlestickSeries, {
      lastValueVisible: false,
      priceLineVisible: false,
      borderVisible: true,
      wickVisible: true,
    });
    this.series.attachPrimitive(this.marksPrimitive);
    this.applyPalette();
    this.chart.subscribeCrosshairMove(this.handleCrosshair);
  }

  destroy(): void {
    this.chart.unsubscribeCrosshairMove(this.handleCrosshair);
    this.chart.remove();
  }

  setPalette(palette: Palette): void {
    this.palette = palette;
    this.applyPalette();
    this.series.setData(this.candles.map((c) => this.bar(c)));
    this.applyMarks();
  }

  /** Display options or staleness changed: redraw the marks and the tool, keep the candles. */
  setOptions(opts: ChartOptions): void {
    if (opts.scale !== this.opts.scale) this.chart.applyOptions({ layout: { fontSize: Math.round(10 * opts.scale) } });
    this.opts = opts;
    this.applyMarks();
  }

  /**
   * Bring the chart to `view`. A snapshot redraws; a tick updates the tail in place.
   * `column` is the timeframe above, drawn right of the last candle (see htf.ts), held
   * to `band` on the price scale. `look` is what to look for on this pane (LookLayer.ts).
   */
  setView(view: ChartView, direction: Direction, column: HtfColumn | null = null, band: Band | null = null, look: LookScene | null = null): void {
    const diff = diffCandles(this.candles, view.candles);
    const columnChanged = column !== this.column || band !== this.columnBand || look !== this.look;
    this.column = column;
    this.columnBand = band;
    this.look = look;
    const marksChanged = view.marks !== this.marks || view.tool !== this.tool || direction !== this.direction || columnChanged;
    this.intraday = view.minutes < 1440;
    if (diff.kind === 'reset') {
      this.decimals = priceDecimals(view.candles.flatMap((c) => [c.open, c.close]).slice(-200));
      this.series.applyOptions({ priceFormat: { type: 'price', precision: this.decimals, minMove: 1 / 10 ** this.decimals } });
      this.series.setData(view.candles.map((c) => this.bar(c)));
    } else if (diff.kind === 'update') {
      for (let i = diff.from; i < view.candles.length; i++) this.series.update(this.bar(view.candles[i]!));
    }
    this.candles = view.candles;
    this.byTime = new Map(view.candles.map((c) => [c.t, c]));
    if (diff.kind === 'update') this.marksPrimitive.setCandles(view.candles);
    if (marksChanged || diff.kind === 'reset') {
      this.marks = view.marks;
      this.tool = view.tool;
      this.direction = direction;
      this.applyMarks();
    }
    if (diff.kind === 'reset') this.fit();
    else if (this.chart.timeScale().options().rightOffset !== this.rightPad()) {
      // the column grew (a new higher-timeframe candle) or "look for" came or went: keep its room
      this.chart.timeScale().applyOptions({ rightOffset: this.rightPad() });
    }
  }

  /** Open on the recent window (plus the start of every mark); older candles scroll into view. */
  private fit(): void {
    const count = this.candles.length;
    const from = initialWindowStart(count, this.starts(), this.visibleBars);
    const pad = this.rightPad();
    const ts = this.chart.timeScale();
    ts.applyOptions({ rightOffset: pad });
    if (from === 0 && count <= this.visibleBars && !this.tool && !this.column?.bars.length) ts.fitContent();
    else ts.setVisibleLogicalRange({ from: from - 0.5, to: count - 1 + pad });
  }

  /** Empty bars right of the last candle: room for the tool's zones, or for the column. */
  private rightPad(): number {
    const base = this.tool ? RIGHT_PAD_TOOL : RIGHT_PAD;
    const n = (this.column?.bars.length ?? 0) + projectedSlots(this.look);
    if (n === 0) return this.look ? Math.max(base, columnGap(!!this.tool, true)) : base;
    return Math.max(base, columnGap(!!this.tool, !!this.look) + COLUMN_SLOT * n + 1.5);
  }

  /** Every mark start, and the tool's, for the opening window. */
  private starts(): { start: number | null }[] {
    const starts: { start: number | null }[] = layerMarks(this.marks ?? [], this.opts.overlays);
    if (this.tool) starts.push({ start: this.tool.start });
    return starts;
  }

  private applyPalette(): void {
    const p = this.palette;
    this.chart.applyOptions({
      layout: { background: { type: ColorType.Solid, color: p.surface }, textColor: p.muted },
      crosshair: {
        vertLine: { color: p.faint, style: LineStyle.Dashed, width: 1, labelBackgroundColor: p.raised },
        horzLine: { color: p.faint, style: LineStyle.Dashed, width: 1, labelBackgroundColor: p.raised },
      },
    });
    // Crosshair labels use layout.textColor on labelBackgroundColor: muted on raised passes AA.
    this.series.applyOptions({
      // Monochrome: up candles hollow (outline only), down candles filled.
      upColor: p.hollowUp ? withAlpha(p.surface, 0) : p.up,
      downColor: p.down,
      borderUpColor: p.up,
      borderDownColor: p.downLine,
      wickUpColor: p.up,
      wickDownColor: p.downLine,
    });
  }

  private applyMarks(): void {
    const marks = layerMarks(this.marks ?? [], this.opts.overlays);
    // Which levels are too far away to draw is judged against the window the chart
    // opens on, so a level near old prices cannot squash the recent candles.
    const from = initialWindowStart(this.candles.length, this.starts(), this.visibleBars);
    const { shown } = partitionMarks(this.candles.slice(from), marks);
    this.marksPrimitive.setScene({
      marks: shown,
      tool: this.tool,
      candles: this.candles,
      direction: this.direction,
      palette: this.palette,
      decimals: this.decimals,
      overlays: this.opts.overlays,
      stale: this.opts.stale,
      scale: this.opts.scale,
      column: this.column,
      columnBand: this.columnBand,
      look: this.look,
    });
  }

  /** Forming candle: outline only, so it reads as not yet closed. */
  private bar(c: Candle): CandlestickData<Time> {
    const base: CandlestickData<Time> = { time: c.t as UTCTimestamp, open: c.open, high: c.high, low: c.low, close: c.close };
    if (!c.forming) return base;
    const color = c.close >= c.open ? this.palette.up : this.palette.down;
    return { ...base, color: withAlpha(this.palette.surface, 0), borderColor: color, wickColor: color };
  }

  private tickLabel(time: Time, type: TickMarkType): string {
    const t = time as number;
    switch (type) {
      case TickMarkType.Year:
        return axisLabel(t, 'year', this.intraday);
      case TickMarkType.Month:
        return axisLabel(t, 'month', this.intraday);
      case TickMarkType.DayOfMonth:
        return axisLabel(t, 'day', this.intraday);
      default:
        return axisLabel(t, 'time', this.intraday);
    }
  }

  private readonly handleCrosshair = (param: MouseEventParams<Time>): void => {
    const point = param.point;
    const title = point ? this.marksPrimitive.titleAt(point.x, point.y) : null;
    this.onMarkHover(point && title ? { title, x: point.x, y: point.y } : null);
    if (param.time === undefined || !point) {
      this.onHover(null);
      return;
    }
    this.onHover(this.byTime.get(param.time as number) ?? null);
  };
}
