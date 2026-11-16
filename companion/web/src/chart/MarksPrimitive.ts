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
import { begunLevels, bestJustBegunSpot, clearOfSpans, leastCoverSpot, nameAnswers, edgeGroups, foldInto, groupTexts, groupTitle, keyNameSpots, nearestAround, shownLevels, stackChips, thinByGap, type KeyFamily, type KeyGroup, type KeyLevel } from './keylevels';
import { candleEmphasis, candleSteps, chosenOption, projectedCandles, type Ohlc } from './look';
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
import { TOOL_PRIORITY, distinctTags, labelPriority, layoutWithKeyTags, markInRange, markerTextX, overlaps, placeChoices, placePreferring, type Box, type LabelChoice, type PendingLabel } from './marks';
import { CHART_FONT, quietInk, toneColor, withAlpha, type Palette } from './palette';
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
  /** Higher-timeframe key levels, one group per price; null when the layer is off. */
  keys?: readonly KeyGroup[] | null;
  /** The pane's timeframe and the column's, in minutes: how much time the visible bars span. */
  minutes?: number;
  htfMinutes?: number;
}

/** A key level group as this frame draws it: only the levels worth drawing at this zoom. */
interface KeyShown {
  group: KeyGroup;
  levels: KeyLevel[];
  /** Where its line starts: the earliest of the levels shown (null: before the loaded candles). */
  start: number | null;
}

/** The finer families: a line of theirs with no room for its name is not drawn (it joins a neighbour's hover). */
const FINE: ReadonlySet<KeyFamily> = new Set(['htf', 'session']);

/** What one frame draws of the key levels (see keyFrame). */
interface KeyFrame {
  /** Lines on the visible prices drawn this frame, with their y. */
  on: (KeyShown & { y: number })[];
  /** Every line on the visible prices after thinning, before fine lines with no room for a name are left out. */
  all: (KeyShown & { y: number })[];
  /** Nearest past the top and the bottom, nearest first: the edge chips. */
  above: KeyShown[];
  below: KeyShown[];
  /** Lines left out for being too close to a kept one, listed under it (for its hover). */
  near: Map<KeyShown, KeyShown[]>;
}

/** Dash and gap of a key level line, by its most senior level: the week's long, the day's even, finer levels dotted. */
const KEY_DASH: Record<KeyFamily, [number, number]> = { core: [4, 4], week: [8, 4], day: [4, 4], htf: [2, 3], session: [2, 3] };
/** Key level labels come after every mark's, the most senior first. */
const KEY_PRIORITY: Record<KeyFamily, number> = { core: 6, week: 6.1, day: 6.2, htf: 6.3, session: 6.4 };
/** Edge chips per edge, nearest first. */
const KEY_EDGE_MAX = 2;
/** Slots an edge's chips may use, counted from the edge: room to step past lines and wicks there. */
const KEY_EDGE_SLOTS = 6;
/** Clear space either side of another label that a key level's name keeps, so the two never read as one phrase. */
const KEY_LABEL_PAD = 8;

interface Resolved {
  mark: Mark;
  /** What is drawn beside the line or arrow; "" draws none (the title still shows on hover). */
  label: string;
  color: string;
  priority: number;
  /** A plain reference level (muted tone): dashed, behind the candles, with a light price tag. */
  quiet: boolean;
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
/** Column candle bodies at half strength: the higher timeframe is context, not the pane's price. */
const COLUMN_FILL_ALPHA = 0.5;
/** A price tag is drawn 21 px tall at 12 px axis text (12 + 2 x 2.5 padding + 2 x 2 primitive padding): tags are kept 22 px apart. */
const AXIS_TAG_GAP = 22;
/** Added to a reference level's label priority for its price tag: after every role level. */
const QUIET_RANK = 100;
/** The column candles' high / low hairlines across the bars they cover: 0.65 keeps them near 3:1 on cream. */
const SPAN_ALPHA = 0.65;
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
  /** The y of every price tag shown, for the axis to hide the ticks under them. */
  private tagYs: () => number[] = () => [];
  private hits: Hit[] = [];
  private zoneHits: Hit[] = [];
  /** Column candles drawn this frame, as label obstacles. */
  private columnBoxes: Box[] = [];
  /** "Look for" outlines and hairlines drawn this frame, as label obstacles. */
  private lookBoxes: Box[] = [];
  private topInset = 0;
  /** Bumped on every scene, so a frame's key levels are worked out again. */
  private sceneId = 0;
  private keyCache: { key: string; frame: KeyFrame | null } | null = null;
  /** The column hairlines drawn this frame (media px): no key name may sit on one. */
  private spanBoxes: (Box & { price: number })[] = [];
  /** For measuring a name's width outside a draw (deciding which fine lines can be named). */
  private measureCtx: CanvasRenderingContext2D | null = null;
  /**
   * Whether each fine line (by price and wording, so it lasts across ticks) had room for its name
   * when the label pass last placed every name: the line pass draws from this. It changes only when
   * the answer does (a pan, a zoom, a resize), never just because a tick came, so nothing flashes.
   */
  private fineNamed = new Map<string, boolean>();
  private fineVersion = 0;

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
    this.sceneId++;
    const { palette, direction, overlays } = scene;
    this.items = scene.marks
      .filter((m) => overlays.zones || m.kind !== 'zone')
      .map((mark) => ({
        mark,
        label: this.markLabel(mark, overlays),
        color: toneColor(palette, markTone(mark.role, direction)),
        priority: labelPriority(mark.role),
        quiet: markTone(mark.role, direction) === 'muted',
      }));
    this.lastClose = scene.candles[scene.candles.length - 1]?.close ?? null;
    this.axisViews = this.buildAxisViews();
    this.requestUpdate?.();
  }

  /** Media px at the top of the plot the pane's notes cover: the top edge chips start below them. */
  setTopInset(px: number): void {
    if (px === this.topInset) return;
    this.topInset = px;
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
    // A reference level ranks after every role level (QUIET_RANK), so it never wins a shared price
    // and never keeps its tag beside a role tag.
    const levels: { price: number; role: string; priority: number; color: string; quiet: boolean }[] = this.items
      .filter((it) => it.mark.kind === 'level' && it.mark.price !== null)
      .map((it) => ({ price: it.mark.price!, role: it.mark.role, priority: it.priority + (it.quiet ? QUIET_RANK : 0), color: it.color, quiet: it.quiet }));
    if (scene.tool) {
      for (const line of scene.tool.lines) levels.push({ price: line.price, role: line.role, priority: TOOL_PRIORITY[line.role], color: this.toolColor(line.role), quiet: false });
    }
    const ordered = distinctTags(levels, scene.decimals).sort((a, b) => a.priority - b.priority);
    type Tag = { price: number; text: string; textColor: string; backColor: string; quiet: boolean };
    const roleTags: Tag[] = ordered
      .filter((it) => !it.quiet)
      .map((it) => ({ price: it.price, text: formatPrice(it.price, scene.decimals), textColor: scene.palette.bg, backColor: it.color, quiet: false }));
    // "look for" names its stop and entry on the axis in words (their prices are not known yet): role tags too.
    const lookTags: Tag[] = scene.look
      ? lookAxisTags(scene.look, scene.palette).map((tag) => ({ price: tag.price, text: tag.text, textColor: scene.palette.bg, backColor: tag.back, quiet: false }))
      : [];
    // A plain reference level gets a light tag in pane ink, so the filled tags are the ones that matter.
    const quietTags: Tag[] = ordered
      .filter((it) => it.quiet)
      .map((it) => ({ price: it.price, text: formatPrice(it.price, scene.decimals), textColor: scene.palette.text, backColor: scene.palette.raised, quiet: true }));
    // Key levels: light tags too, the most senior first, each only while its group is drawn at this zoom.
    const keyTags: (Tag & { group: KeyGroup })[] = [...(scene.keys ?? [])]
      .sort((a, b) => keyRank(a) - keyRank(b))
      .map((group) => ({ price: group.price, text: formatPrice(group.price, scene.decimals), textColor: scene.palette.text, backColor: scene.palette.raised, quiet: true, group }));
    const all: (Tag & { group?: KeyGroup })[] = [...roleTags, ...lookTags, ...quietTags, ...keyTags];
    // Laid out on every frame (the scale moves): role tags spread apart where they would overlap, then a
    // reference tag only where it clears them. Drawn at exactly these places, and the ticks under them hidden.
    // Only one key level a side of the last close gets one (the nearest, else the next when the nearest
    // has no room), so the axis keeps its prices. Laid out once per frame and reused by every tag.
    let cache: { key: string; ys: (number | null)[] } | null = null;
    const layout = () => {
      const size = this.chart?.paneSize();
      const key = this.frameKey(size?.height ?? 0, size?.width ?? 0);
      if (cache && cache.key === key) return cache.ys;
      // the groups this frame draws (after thinning), so a tag never names a level with no line
      const frame = size ? this.keyFrame(size.height) : null;
      const live = frame ? frame.on.map((k) => k.group) : []; // a tag only for a level on the plot
      const near = this.lastClose === null ? { up: [], down: [] } : nearestAround(live, this.lastClose);
      const order = new Map<KeyGroup, { side: 0 | 1; order: number }>();
      near.up.forEach((g, k) => order.set(g, { side: 0, order: k }));
      near.down.forEach((g, k) => order.set(g, { side: 1, order: k }));
      const ys = layoutWithKeyTags(
        all.map((t) => {
          const key = t.group ? order.get(t.group) : undefined;
          return { y: t.group && !key ? null : series.priceToCoordinate(t.price), quiet: t.quiet, key };
        }),
        Math.round(AXIS_TAG_GAP * scene.scale),
      );
      cache = { key, ys };
      return ys;
    };
    this.tagYs = () => layout().filter((y): y is number => y !== null);
    const tags = all.map(
      (t, i): ISeriesPrimitiveAxisView => ({
        coordinate: () => series.priceToCoordinate(t.price) ?? -100,
        fixedCoordinate: () => layout()[i] ?? undefined,
        text: () => t.text,
        textColor: () => t.textColor,
        backColor: () => t.backColor,
        visible: () => layout()[i] !== null,
        tickVisible: () => false,
      }),
    );
    return tags;
  }

  /** The y of every price tag shown now, in media pixels. */
  shownTagYs(): number[] {
    return this.tagYs();
  }

  /** How far from a shown tag's centre an axis tick is hidden: half a tag plus half a tick label. */
  tickGap(): number {
    return Math.round((AXIS_TAG_GAP / 2 + 6) * (this.scene?.scale ?? 1));
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

  /** Minutes of time the visible bars span: what decides which key levels are worth drawing. */
  private spanMinutes(): number {
    const range = this.chart?.timeScale().getVisibleLogicalRange();
    const minutes = this.scene?.minutes ?? 0;
    if (!range) return 0;
    const bars = Math.max(1, Math.min(range.to, this.lastIndex()) - Math.max(range.from, 0));
    return bars * minutes;
  }

  /** What decides a frame's key levels: the scene, the visible bars and prices, the pane size, the notes, the last close. */
  private frameKey(height: number, width: number): string {
    const range = this.chart?.timeScale().getVisibleLogicalRange();
    const h = Math.round(height);
    const top = this.series?.coordinateToPrice(0) ?? null;
    const bottom = this.series?.coordinateToPrice(h) ?? null;
    return `${this.sceneId}|${range?.from}|${range?.to}|${top}|${bottom}|${h}|${Math.round(width)}|${this.topInset}|${this.lastClose}|${this.fineVersion}`;
  }

  /** A key line's identity across scenes and ticks: its price and its wordings. */
  private fineId(k: KeyShown): string {
    return `${k.group.price.toFixed(this.scene?.decimals ?? 2)}|${k.levels.map((l) => l.short).join('+')}`;
  }

  /** Width of a name drawn in the label font, as the label pass measures it. */
  private nameWidth(text: string): number {
    if (!this.measureCtx && typeof document !== 'undefined') this.measureCtx = document.createElement('canvas').getContext('2d');
    const ctx = this.measureCtx;
    if (!ctx) return text.length * 7 + 6;
    ctx.font = this.font(500);
    return ctx.measureText(text).width + 6;
  }

  /**
   * The key level groups worth drawing at this zoom, split into those on the visible prices and
   * the nearest past each edge. Worked out once per frame (the lines, labels and tags share it).
   */
  private keyFrame(height: number): KeyFrame | null {
    const key = this.frameKey(height, this.chart?.paneSize().width ?? 0);
    if (this.keyCache && this.keyCache.key === key) return this.keyCache.frame;
    const frame = this.buildKeyFrame(height);
    this.keyCache = { key, frame };
    return frame;
  }

  private buildKeyFrame(height: number): KeyFrame | null {
    const scene = this.scene;
    const series = this.series;
    if (!scene?.keys?.length || !series) return null;
    const span = this.spanMinutes();
    const on: (KeyShown & { y: number })[] = [];
    const off: (KeyShown & { price: number })[] = [];
    // A level whose period begins right of what is shown did not exist yet: no line, label, chip or tag.
    const right = this.chart ? this.keyRight(this.chart.paneSize().width) : Infinity;
    // Judged per level, so a later level merged at an older one's price is not named before it began.
    const xOf = (start: number) => this.x(start, Infinity) - this.halfBar();
    for (const group of scene.keys) {
      const levels = begunLevels(shownLevels(group, span, scene.htfMinutes ?? 0), xOf, right);
      if (levels.length === 0) continue;
      // the line starts with the earliest level shown, not one hidden at this zoom
      const start = levels.some((l) => l.start === null) ? null : Math.min(...levels.map((l) => l.start!));
      const y = series.priceToCoordinate(group.price);
      if (y !== null && y >= 0 && y <= height) on.push({ group, levels, start, y });
      else off.push({ group, levels, start, price: group.price });
    }
    const top = series.coordinateToPrice(0);
    const bottom = series.coordinateToPrice(height);
    const edges = top === null || bottom === null ? { above: [], below: [] } : edgeGroups(off, top, bottom, KEY_EDGE_MAX);
    // Levels closer than a label to a more senior one are left out: one line, one name, no pile-up.
    const thinned = thinByGap(on, this.labelH() + 6, this.lastClose);
    // A fine line with no room for its name is left out too (a bare dotted line is noise), under its
    // nearest neighbour with whatever that already held. The label pass's answer (fineNamed) decides;
    // a line it has not placed yet is judged on candles and key lines alone. With names off nothing is
    // named, so nothing is left out for it: the toggle hides names, not levels.
    const all = thinned.kept;
    const names = scene.overlays.levelNames;
    const guess = names ? this.nameable(all, height) : null;
    // The nearest level each side of the last close is never left out, named or not: it is what price
    // trades against, and its tag and hover say what it is.
    const keep = this.nearestEachSide(all);
    // A short senior stub (zoomed out, shorter than three of its names) is judged like a fine line: the
    // label pass's answer, else the guess. A longer senior line always stays, named or not (structure).
    const nameRight = right - 6; // where names end, as the label pass has it
    const shortStub = (k: KeyShown) => {
      const x = Math.max(0, k.start === null ? 0 : this.x(k.start, 0) - this.halfBar());
      const names = groupTexts(k.levels);
      return nameRight - x < 3 * this.nameWidth(names[names.length - 1] ?? '');
    };
    const leaveOut = (k: KeyShown & { y: number }) =>
      !!guess && !keep.has(k) && (FINE.has(k.levels[0]!.family) || shortStub(k)) && !(this.fineNamed.get(this.fineId(k)) ?? guess.has(k));
    const kept = foldInto(all, thinned.near, leaveOut);
    return { on: kept, all, near: thinned.near as Map<KeyShown, KeyShown[]>, ...edges };
  }

  /** The nearest line above the last close and the nearest below it. */
  private nearestEachSide<T extends KeyShown>(lines: readonly T[]): Set<T> {
    if (this.lastClose === null) return new Set();
    const { up, down } = nearestAround(
      lines.map((k) => ({ k, price: k.group.price })),
      this.lastClose,
      1,
    );
    return new Set([...up, ...down].map((x) => x.k));
  }

  /** The lines whose name (any wording) has a spot inside the plot clear of the candles and the other key lines. */
  private nameable<T extends KeyShown & { y: number }>(lines: readonly T[], height: number): Set<T> {
    const out = new Set<T>();
    if (!this.chart || !this.scene?.overlays.levelNames) return out;
    const width = this.chart.paneSize().width;
    const right = this.keyRight(width) - 6;
    const LH = this.labelH();
    // every column hairline too (all of them: which are skipped depends on this very frame), except
    // one at the line's own price, as the label pass does
    const candleOnly = this.candleBoxes();
    const allSpans = this.hairlines(width).map((s) => ({ x: s.x1, y: s.y - 1.5, w: s.x2 - s.x1, h: 3, price: s.price }));
    const dec = this.scene.decimals;
    const startX = (k: KeyShown) => Math.max(0, k.start === null ? 0 : this.x(k.start, 0) - this.halfBar());
    for (const k of lines) {
      const others = lines.filter((o) => o !== k).map((o) => ({ y: o.y, x: startX(o) }));
      const below = this.lastClose !== null && k.group.price < this.lastClose;
      const candles = [...candleOnly, ...allSpans.filter((s) => s.price.toFixed(dec) !== k.group.price.toFixed(dec))];
      const fits = groupTexts(k.levels).some((text) =>
        keyNameSpots({ x: startX(k), y: k.y }, others, this.nameWidth(text), right, LH, height, below, candles).some(
          (b) => b.x >= 0 && b.y >= 0 && b.x + b.w <= width && b.y + b.h <= height && !candles.some((c) => overlaps(c, b)),
        ),
      );
      if (fits) out.add(k);
    }
    return out;
  }

  /** Where key level lines end and their labels sit: the column's left edge, else the pane's right edge. */
  private keyRight(width: number): number {
    const left = this.columnLeft();
    return left === null ? width : Math.max(0, Math.min(width, left));
  }

  private labelH(): number {
    return Math.round(15 * (this.scene?.scale ?? 1));
  }

  private font(weight = 500): string {
    return `${weight} ${Math.round(12 * (this.scene?.scale ?? 1) * 10) / 10}px ${CHART_FONT}`;
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

  /** The visible candles' high-low boxes (body width + 2 px), in media pixels: what a label should not cover. */
  private candleBoxes(): Box[] {
    const series = this.series;
    const scene = this.scene;
    const range = this.chart?.timeScale().getVisibleLogicalRange();
    if (!series || !scene || !range) return [];
    const half = Math.max(2, this.halfBar() * 0.8) + 2;
    const out: Box[] = [];
    const from = Math.max(0, Math.floor(range.from));
    const to = Math.min(scene.candles.length - 1, Math.ceil(range.to));
    for (let i = from; i <= to; i++) {
      const c = scene.candles[i]!;
      const yH = series.priceToCoordinate(c.high);
      const yL = series.priceToCoordinate(c.low);
      if (yH === null || yL === null) continue;
      const x = this.x(i, -1);
      if (x < 0) continue;
      out.push({ x: x - half, y: yH - 2, w: 2 * half, h: yL - yH + 4 });
    }
    return out;
  }

  /** The visible candles' bodies (open to close, body width + 1 px), in media pixels: what a name never covers. */
  private bodyBoxes(): Box[] {
    const series = this.series;
    const scene = this.scene;
    const range = this.chart?.timeScale().getVisibleLogicalRange();
    if (!series || !scene || !range) return [];
    const half = Math.max(1.5, this.halfBar() * 0.8) + 1;
    const out: Box[] = [];
    for (let i = Math.max(0, Math.floor(range.from)); i <= Math.min(scene.candles.length - 1, Math.ceil(range.to)); i++) {
      const c = scene.candles[i]!;
      const yO = series.priceToCoordinate(c.open);
      const yC = series.priceToCoordinate(c.close);
      const x = this.x(i, -1);
      if (yO === null || yC === null || x < 0) continue;
      out.push({ x: x - half, y: Math.min(yO, yC) - 1, w: 2 * half, h: Math.abs(yC - yO) + 2 });
    }
    return out;
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
    const body = Math.max(3, Math.min(12, ts.options().barSpacing * COLUMN_SLOT * 0.5));
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

      // Plain reference levels: dashed, in the faint ink, behind the candles, so structure never reads as price.
      const lw = Math.max(1, Math.floor(vr));
      const dash = Math.round(4 * hr);
      ctx.fillStyle = quietInk(scene.palette);
      for (const { mark, quiet } of this.items) {
        if (!quiet || mark.kind !== 'level' || mark.price === null) continue;
        const y = series.priceToCoordinate(mark.price);
        if (y === null) continue;
        const x = Math.max(0, mark.start === null ? 0 : this.x(mark.start, 0) - this.halfBar());
        if (x >= width) continue;
        const yb = Math.round(y * vr) - Math.floor(lw / 2);
        for (let xb = Math.round(x * hr); xb < bitmapSize.width; xb += 2 * dash) ctx.fillRect(xb, yb, Math.min(dash, bitmapSize.width - xb), lw);
      }

      // Key levels: from where their period began to the column, dashed by how senior they are.
      const frame = this.keyFrame(bitmapSize.height / vr);
      if (frame) {
        const ink = quietInk(scene.palette);
        const right = Math.round(this.keyRight(width) * hr);
        for (const { start, levels, y } of frame.on) {
          const x = Math.round(Math.max(0, start === null ? 0 : this.x(start, 0) - this.halfBar()) * hr);
          if (x >= right) continue;
          const [on, off] = KEY_DASH[levels[0]!.family].map((n) => Math.max(1, Math.round(n * hr))) as [number, number];
          const yb = Math.round(y * vr) - Math.floor(lw / 2);
          ctx.fillStyle = ink;
          for (let xb = x; xb < right; xb += on + off) ctx.fillRect(xb, yb, Math.min(on, right - xb), lw);
        }
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
      for (const { mark, color, label, priority, quiet } of this.items) {
        if (mark.kind !== 'level' || mark.price === null) continue;
        const y = series.priceToCoordinate(mark.price);
        if (y === null) continue;
        const x = Math.max(0, mark.start === null ? 0 : this.x(mark.start, 0) - this.halfBar());
        if (x >= width) continue;
        const next = mark.role.trim().toLowerCase() === 'next';
        lines.push({ x, y, color, label, title: mark.title || mark.label, price: mark.price, priority, next });
        const lineWidth = Math.max(1, Math.floor(vr)) * (next ? 2 : 1);
        const yb = Math.round(y * vr) - Math.floor(lineWidth / 2);
        if (!quiet) {
          ctx.fillStyle = color;
          ctx.fillRect(Math.round(x * hr), yb, bitmapSize.width - Math.round(x * hr), lineWidth);
        }
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
      // Labels first look for a spot clear of the candles; one that finds none keeps its old place on its halo.
      const candleBoxes = this.candleBoxes();
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

      // ---- key levels: edge chips for the nearest past the prices shown, then a label at each line's right end ----
      // Their names are placed in a pass of their own, after every other label (see below).
      const keyTitles = new Map<KeyShown, string>();
      const chipBoxes: Box[] = [];
      let keyLabel: ((shown: KeyShown & { y: number }, set: readonly (KeyShown & { y: number })[]) => PendingLabel) | null = null;
      const frame = this.keyFrame(plot.h);
      if (frame) {
        const right = this.keyRight(plot.w) - 6;
        // The farthest level sits at the edge and the nearest inward, so the stack reads in price
        // order; a slot over a candle is skipped (a chip is opaque).
        // A chip never covers a candle or a line on screen (a key line, a trade line, the next level):
        // sitting on a line it would read as that line's name. Over a candle it slides left past it.
        const chipBlocks: Box[] = [
          ...candleBoxes,
          ...obstacles,
          ...frame.all.map((o) => {
            const x = Math.max(0, o.start === null ? 0 : this.x(o.start, 0) - this.halfBar());
            return { x, y: o.y - 2, w: Math.max(0, right + 6 - x), h: 4 };
          }),
        ];
        const chipText = (k: KeyShown) => `${k.levels[0]!.short}${k.levels.length > 1 ? ' +' + (k.levels.length - 1) : ''}  ${formatPrice(k.group.price, scene.decimals)}`;
        // The nearest levels get chips first (as many as find a slot), stacked with the farthest at the
        // edge so the stack reads in price order (stackChips). Chips avoid every thinned key line, drawn
        // or not (frame.all, not frame.on): which fine lines are drawn is the label pass's answer, and
        // the chips come before it, so they must not depend on it (no feedback between the two).
        const chips = (list: readonly KeyShown[], up: boolean) => {
          const slotY = (n: number) => {
            const y = up ? this.topInset + 4 + n * (LH + 3) : plot.h - 4 - LH - n * (LH + 3);
            if (y < 0 || y + LH > plot.h) return null;
            // never with a drawn key line between the chip and its edge: that line is priced nearer, and
            // reading down the edge the chip would sit on the wrong side of it
            const past = frame.all.some((o) => (up ? o.y < y : o.y > y + LH));
            return past ? null : y;
          };
          const boxes = stackChips(list.map((k) => measure(chipText(k)) + 12), slotY, right, LH, chipBlocks, KEY_EDGE_SLOTS);
          list.forEach((k, i) => {
            const box = boxes[i];
            if (box) chip(k, up, chipText(k), box);
          });
        };
        const chip = (k: KeyShown, up: boolean, text: string, box: Box) => {
          if (box.x < 4 || box.y < 0 || box.y + box.h > plot.h) return;
          ctx.fillStyle = scene.palette.raised;
          ctx.fillRect(box.x, box.y, box.w, box.h);
          // a small triangle pointing to where the level is
          const cx = box.x + 7;
          const cy = box.y + LH / 2;
          ctx.fillStyle = scene.palette.muted;
          ctx.beginPath();
          ctx.moveTo(cx, up ? cy - 3 : cy + 3);
          ctx.lineTo(cx - 3.5, up ? cy + 2.5 : cy - 2.5);
          ctx.lineTo(cx + 3.5, up ? cy + 2.5 : cy - 2.5);
          ctx.closePath();
          ctx.fill();
          ctx.font = this.font(500);
          ctx.fillStyle = scene.palette.text;
          ctx.fillText(text, box.x + 14, box.y + LH - Math.round(3 * scene.scale));
          obstacles.push({ x: box.x, y: box.y - 3, w: box.w, h: box.h + 6 }); // a little room above and below
          chipBoxes.push(box);
          hits.push({ box, title: `${up ? 'Above' : 'Below'} the prices shown: ${groupTitle(k.levels, k.group.price, scene.decimals)}`, priority: 8 });
        };
        chips(frame.above, true);
        chips(frame.below, false);
        const lineStart = (k: KeyShown) => Math.max(0, k.start === null ? 0 : this.x(k.start, 0) - this.halfBar());
        for (const shown of frame.on) {
          const { group, levels, y } = shown;
          // A level left out for being too close to this one is named in this one's hover.
          // ("nearby" within a few label heights; "also" for one only folded here for want of a closer line)
          const held = frame.near.get(shown) ?? [];
          // a level the core sent keeps its own name findable ("PD EQ 25,052.38 (... Respect level ...)")
          const word = (n: KeyShown) => {
            const core = n.levels.find((l) => l.coreSent || l.family === 'core');
            return `${n.levels.map((l) => l.short).join(' · ')} ${formatPrice(n.group.price, scene.decimals)}${core ? ` (${core.name})` : ''}`;
          };
          const close = held.filter((n) => {
            const ny = series.priceToCoordinate(n.group.price);
            return ny !== null && Math.abs(ny - y) <= 3 * LH;
          });
          const far = held.filter((n) => !close.includes(n));
          const title =
            groupTitle(levels, group.price, scene.decimals) +
            (close.length ? `; nearby: ${close.map(word).join(', ')}` : '') +
            (far.length ? `; also: ${far.map(word).join(', ')}` : '');
          const x = lineStart(shown);
          hits.push({ box: { x, y: y - 4, w: Math.max(0, right + 6 - x), h: 8 }, title, priority: 9 });
          keyTitles.set(shown, title);
        }
        // A name for a line among `set` (the lines that would be drawn): the spots keyNameSpots gives
        // (its doc says the order), so a name always sits in its own line's strip.
        keyLabel = (shown, set) => {
          const { group, levels, y } = shown;
          const x = lineStart(shown);
          const below = this.lastClose !== null && group.price < this.lastClose;
          const others = set.filter((o) => o !== shown).map((o) => ({ y: o.y, x: lineStart(o) }));
          // column hairlines bar a name, except at its own price (whether that one is drawn depends
          // on whether this line is, so ignoring it keeps the answer the same from any history)
          const choices = groupTexts(levels).map((text): LabelChoice => {
            const w = measure(text);
            const spots = keyNameSpots({ x, y }, others, w, right, LH, plot.h, below, candleBoxes);
            return { text, w, candidates: clearOfSpans(spots, this.spanBoxes, group.price, scene.decimals) };
          });
          const title = keyTitles.get(shown) ?? groupTitle(levels, group.price, scene.decimals);
          return { title, color: scene.palette.muted, priority: KEY_PRIORITY[levels[0]!.family], choices };
        };
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
      const placed = placePreferring(
        order.map((o) => o.l),
        plot,
        obstacles,
        candleBoxes,
      );
      // Key level names last, in their own pass: never on a candle (a name with no clear spot takes a
      // shorter wording, else is left out; its line, hover and tag stay), and a little clear of every
      // other label, so the two never read as one phrase.
      // every placed label and edge chip, padded, so a key name never reads as part of either
      const pad = (b: Box): Box => ({ x: b.x - KEY_LABEL_PAD, y: b.y - 2, w: b.w + 2 * KEY_LABEL_PAD, h: b.h + 4 });
      // an edge chip gets twice the side clearance: a name beside a chip on one row reads as one phrase
      const padChip = (b: Box): Box => ({ x: b.x - 2 * KEY_LABEL_PAD, y: b.y - 2, w: b.w + 4 * KEY_LABEL_PAD, h: b.h + 4 });
      const others = [...placed.flatMap((r) => (r ? [pad(r.box)] : [])), ...chipBoxes.map(padChip)];
      const hard = [...obstacles, ...candleBoxes, ...others];
      // Which fine lines have room for a name, against everything placed (trade lines, mark labels,
      // candles): place every name, leave out the fine lines whose name found no spot, and place again
      // without them (their lines no longer bar a spot) until nothing more is left out.
      let keyOrder: PendingLabel[] = [];
      let keyPlaced: ({ choice: number; box: Box } | null)[] = [];
      let keyLines: (KeyShown & { y: number })[] = [];
      // The whole placement is worked out over every thinned line (frame.all), whatever this frame
      // drew, so its answer does not depend on history; only the names of lines drawn are drawn.
      const keyRightX = this.keyRight(plot.w) - 6;
      const startOf = (k: KeyShown) => Math.max(0, k.start === null ? 0 : this.x(k.start, 0) - this.halfBar());
      const allNearest = frame ? this.nearestEachSide(frame.all) : new Set<KeyShown>();
      if (frame && keyLabel && scene.overlays.levelNames) {
        const left = new Set<KeyShown>();
        for (let pass = 0; pass < 4; pass++) {
          const set = frame.all.filter((k) => !left.has(k));
          // the nearest level each side of the last close is named first: it is what price trades against
          const first = (x: { k: KeyShown & { y: number } }) => (allNearest.has(x.k) ? 0 : 1);
          const labelled = set.map((k) => ({ k, l: keyLabel!(k, set) })).sort((a, b) => first(a) - first(b) || a.l.priority - b.l.priority);
          keyPlaced = placeChoices(labelled.map((x) => x.l), plot, hard);
          keyOrder = labelled.map((x) => x.l);
          keyLines = labelled.map((x) => x.k);
          let grew = false;
          labelled.forEach((x, i) => {
            if (!keyPlaced[i] && FINE.has(x.k.levels[0]!.family) && !left.has(x.k) && !allNearest.has(x.k)) {
              left.add(x.k);
              grew = true;
            }
          });
          if (!grew) break;
        }
      }
      const taken = keyPlaced.flatMap((r) => (r ? [r.box] : []));
      const bodies = this.bodyBoxes();
      // A week, day or core line whose period has only just begun (shorter than three of its names) and
      // whose name found no clear spot takes the spot covering the fewest candles (bestJustBegunSpot),
      // never over another label, a chip, a trade line or a column hairline.
      keyOrder.forEach((l, i) => {
        const k = keyLines[i];
        if (keyPlaced[i] || !k || FINE.has(k.levels[0]!.family)) return;
        const c = l.choices.length - 1; // the shortest wording
        const choice = l.choices[c]!;
        // how far into its period: the week's 10080 minutes, else a day's 1440 (day and core levels)
        const elapsed = k.start === null ? Infinity : (this.lastIndex() - k.start + 1) * (scene.minutes ?? 0);
        const period = k.levels[0]!.family === 'week' ? 10080 : 1440;
        // candle bodies are blocks too: only wicks may be crossed
        const blocks = [...obstacles, ...others, ...this.spansBut(k.group.price), ...taken, ...bodies];
        const box = bestJustBegunSpot(keyRightX - startOf(k), choice.w, LH, choice.candidates, plot, blocks, candleBoxes, elapsed, period);
        if (!box) return;
        keyPlaced[i] = { choice: c, box };
        taken.push(box);
      });
      // The nearest level each side of the last close (always drawn) with no clear spot takes the spot
      // crossing the fewest wicks, never a body: what price trades against is named.
      keyOrder.forEach((l, i) => {
        const k = keyLines[i];
        if (keyPlaced[i] || !k || !allNearest.has(k)) return;
        const blocks = [...obstacles, ...others, ...this.spansBut(k.group.price), ...taken, ...bodies];
        for (let c = l.choices.length - 1; c >= 0; c--) {
          const choice = l.choices[c]!;
          const spot = leastCoverSpot(choice.candidates, plot, blocks, candleBoxes);
          if (spot) {
            keyPlaced[i] = { choice: c, box: spot.box };
            taken.push(spot.box);
            return;
          }
        }
      });
      // Which lines have a name, for the line pass: a fine line, or a short senior stub (shorter than
      // three of its names: zoomed out, a period just begun) that is not the nearest each side, is left
      // out without one (a bare stub is noise); a long senior line stays as structure. Stored per level,
      // so the line pass reads it; when it changed, draw again (the axis formatter too, so a tick under
      // a tag's new place hides); a tick that leaves the answer as it was redraws nothing.
      if (frame && scene.overlays.levelNames) {
        let changed = false;
        // every eligible line of frame.all: one dropped during the passes above is not in keyOrder at
        // all, and must be recorded as unnamed too, or an earlier "named" would outlive it
        const placedLines = new Set(keyLines.filter((_, i) => !!keyPlaced[i]));
        const eligible = (k: KeyShown) => {
          const names = groupTexts(k.levels);
          return FINE.has(k.levels[0]!.family) || keyRightX - startOf(k) < 3 * this.nameWidth(names[names.length - 1] ?? '');
        };
        for (const [k, named] of nameAnswers(frame.all, placedLines, eligible)) {
          const id = this.fineId(k);
          if (this.fineNamed.get(id) !== named) {
            if (this.fineNamed.size > 256) this.fineNamed.delete(this.fineNamed.keys().next().value!); // the oldest
            this.fineNamed.set(id, named);
            changed = true;
          }
        }
        if (changed) {
          this.fineVersion++;
          // Lightweight Charts caches its axis tick labels until the price range or the formatter
          // changes; applying an empty localization re-runs the formatter, which hides the ticks under
          // the tags' new places. Queued, so it runs after this draw and not inside it.
          const chart = this.chart;
          queueMicrotask(() => chart?.applyOptions({ localization: {} }));
          this.requestUpdate?.();
        }
      }
      // Names only for lines drawn this frame.
      const drawn = new Set<KeyShown>(frame?.on ?? []);
      keyPlaced = keyPlaced.map((r, i) => (keyLines[i] && drawn.has(keyLines[i]!) ? r : null));
      const draw = (l: PendingLabel, r: { choice: number; box: Box } | null) => {
        if (!r) return;
        const { box } = r;
        // Halo in the pane colour keeps the label legible where it crosses a candle or a line.
        ctx.fillStyle = withAlpha(scene.palette.surface, l.caption ? 0.85 : 0.92);
        ctx.fillRect(box.x, box.y, box.w, box.h);
        ctx.font = this.font(l.caption ? 600 : 500);
        ctx.fillStyle = l.color;
        ctx.fillText(l.choices[r.choice]!.text, box.x + 3, box.y + LH - Math.round(3 * scene.scale));
        hits.push({ box, title: l.title, priority: l.priority });
      };
      order.forEach(({ l }, k) => draw(l, placed[k] ?? null));
      keyOrder.forEach((l, k) => draw(l, keyPlaced[k] ?? null));
    });

    this.hits = hits;
  }

  /**
   * Hairlines at each column candle's high and low, across the lower-timeframe bars it
   * covers, and a faint divider where the column begins. Behind the candles.
   */
  private drawSpans(ctx: CanvasRenderingContext2D, hr: number, vr: number, width: number, heightB: number): void {
    const scene = this.scene!;
    const column = scene.column;
    if (!column || column.bars.length === 0) return;
    const lw = Math.max(1, Math.floor(vr));
    ctx.fillStyle = withAlpha(scene.palette.muted, SPAN_ALPHA);
    // A hairline at a price a key level draws now is left out: that price is named already (the previous
    // candle's range is), and two line styles meeting at one price read as one line changing style.
    const frame = this.keyFrame(heightB / vr);
    const at = (p: number) => p.toFixed(scene.decimals);
    const drawnAt = new Set((frame ? [...frame.on, ...frame.above, ...frame.below] : []).map((k) => at(k.group.price)));
    this.spanBoxes = [];
    for (const { x1, x2, y, price } of this.hairlines(width)) {
      // a hairline at a price a key level draws is skipped (each on its own): one line style per price
      if (drawnAt.has(at(price))) continue;
      ctx.fillRect(Math.round(x1 * hr), Math.round(y * vr) - Math.floor(lw / 2), Math.round((x2 - x1) * hr), lw);
      // a key name must not sit on it either: it would read as that line's name
      this.spanBoxes.push({ x: x1, y: y - 1.5, w: x2 - x1, h: 3, price });
    }
    const left = this.columnLeft();
    if (left !== null && left > 0 && left < width) {
      ctx.fillStyle = withAlpha(scene.palette.faint, 0.5);
      ctx.fillRect(Math.round(left * hr), 0, Math.max(1, Math.floor(hr)), heightB);
    }
  }

  /** The column hairlines drawn this frame, except those at `price` (a line's own). */
  private spansBut(price: number): Box[] {
    const dec = this.scene?.decimals ?? 2;
    return this.spanBoxes.filter((s) => s.price.toFixed(dec) !== price.toFixed(dec));
  }

  /** Every column hairline in media px: the high and low of each column candle across the bars it covers. */
  private hairlines(width: number): { x1: number; x2: number; y: number; price: number }[] {
    const column = this.scene?.column;
    const series = this.series;
    if (!column || !series) return [];
    const half = this.halfBar();
    const out: { x1: number; x2: number; y: number; price: number }[] = [];
    for (const bar of column.bars) {
      if (bar.from === null || bar.to === null) continue;
      const x1 = Math.max(0, this.x(bar.from, 0) - half);
      const x2 = Math.min(width, this.x(bar.to, width) + half);
      if (x2 <= x1) continue;
      for (const price of [bar.candle.high, bar.candle.low]) {
        const y = series.priceToCoordinate(price);
        if (y !== null) out.push({ x1, x2, y, price });
      }
    }
    return out;
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
      const line = up ? p.upLine : p.downLine;
      ctx.fillStyle = line;
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
        // The body in the line colour, then a half-strength fill inside it: context, quieter than the pane's own candles.
        ctx.fillRect(bx, top, bw, bottom - top);
        if (bw > 2 && bottom - top > 2) {
          const b = Math.max(1, Math.floor(hr));
          ctx.fillStyle = p.surface;
          ctx.fillRect(bx + b, top + b, bw - 2 * b, bottom - top - 2 * b);
          ctx.fillStyle = withAlpha(color, COLUMN_FILL_ALPHA);
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
      title: (candleSteps(look.look)[k]?.label ?? 'C' + (k + 1)) + ' (what to look for, not a forecast)',
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
      if (yL < 0 || yH > plot.h) continue; // the outline is off the pane: no name floating at its edge
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

/** Order of a key level group's price tag: by its most senior level. */
function keyRank(g: KeyGroup): number {
  return KEY_PRIORITY[g.levels[0]?.family ?? 'session'];
}
