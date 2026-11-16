// One reducer for everything the server says. The live socket and demo mode both
// feed it the same validated frames. The server is the source of truth: nothing
// here guesses at the outcome of a client request.
import type {
  Candle,
  ChartView,
  Options,
  ServerFrame,
  ServerState,
  Status,
  TickFrame,
  Timing,
  VerdictView,
} from './wire';

export type Link = 'connecting' | 'open' | 'down';

export interface Model {
  link: Link;
  /** True once any hello has arrived; distinguishes first connect from a drop. */
  everConnected: boolean;
  /** Epoch ms of the next reconnect attempt while the link is down. */
  retryAt: number | null;
  options: Options | null;
  server: ServerState | null;
  status: Status | null;
  /** Highest snapshot seq shown since the last hello; -1 before the first. */
  seq: number;
  snapshotReceived: boolean;
  /** Last good verdict. Kept on screen when a later snapshot carries only an error. */
  view: VerdictView | null;
  /** True when `view` did not come from the latest snapshot. */
  viewStale: boolean;
  error: string;
  offerHistory: boolean;
  timing: Timing | null;
  /** Latest traded price per timeframe, from ticks. */
  lastPrice: Record<string, number>;
  /** Message from the most recent `error` frame, until dismissed. */
  notice: string | null;
  /** How many `error` frames have arrived: a repeat of the same message still counts (bar replay stops on one). */
  errors: number;
}

export const initialModel: Model = {
  link: 'connecting',
  everConnected: false,
  retryAt: null,
  options: null,
  server: null,
  status: null,
  seq: -1,
  snapshotReceived: false,
  view: null,
  viewStale: false,
  error: '',
  offerHistory: false,
  timing: null,
  lastPrice: {},
  notice: null,
  errors: 0,
};

export type Action =
  | { type: 'frame'; frame: ServerFrame }
  | { type: 'link'; link: 'connecting' | 'open' }
  | { type: 'down'; retryAt: number }
  | { type: 'dismissNotice' };

export function reduce(model: Model, action: Action): Model {
  switch (action.type) {
    case 'link':
      return { ...model, link: action.link, retryAt: action.link === 'open' ? null : model.retryAt };
    case 'down':
      return { ...model, link: 'down', retryAt: action.retryAt };
    case 'dismissNotice':
      return model.notice === null ? model : { ...model, notice: null };
    case 'frame':
      return reduceFrame(model, action.frame);
  }
}

function reduceFrame(model: Model, frame: ServerFrame): Model {
  switch (frame.type) {
    case 'hello':
      // A hello starts a new session. The core may have restarted and begun its
      // seq again, so the ordering baseline resets; the last verdict stays visible
      // until the new session sends a snapshot.
      return {
        ...model,
        link: 'open',
        everConnected: true,
        retryAt: null,
        options: frame.options,
        server: frame.state,
        seq: -1,
      };
    case 'state':
      return { ...model, server: frame.state };
    case 'status':
      return { ...model, status: frame.status };
    case 'error':
      return { ...model, notice: frame.message, errors: model.errors + 1 };
    case 'tick': {
      const lastPrice = { ...model.lastPrice, [frame.timeframe]: frame.last };
      const view = model.view ? applyTick(model.view, frame) : null;
      return { ...model, lastPrice, view };
    }
    case 'snapshot': {
      if (frame.seq < model.seq) return model;
      const base = {
        ...model,
        seq: frame.seq,
        snapshotReceived: true,
        error: frame.error,
        offerHistory: frame.offer_history,
        status: frame.status,
        timing: frame.timing,
      };
      if (frame.view) return { ...base, view: frame.view, viewStale: false };
      if (frame.error) return { ...base, viewStale: model.view !== null };
      // No verdict and no error: nothing has been checked for this selection yet.
      return { ...base, view: null, viewStale: false };
    }
  }
}

/**
 * Apply a tick to every chart of that timeframe. Same open time: replace the last
 * candle. Later open time: the previous candle closed, append. Older: ignore.
 * The tick also moves the forming candle of every higher timeframe it falls inside
 * (high and low widen, close follows), so panes drawn on one price scale keep agreeing
 * between checks. Earlier candles keep their identity so the chart can update in place.
 */
export function applyTick(view: VerdictView, tick: TickFrame): VerdictView {
  const own = view.charts.find((c) => c.timeframe === tick.timeframe);
  let changed = false;
  const charts = view.charts.map((chart) => {
    let candles: Candle[];
    if (chart.timeframe === tick.timeframe) candles = mergeCandle(chart.candles, tick.candle);
    else if (own && chart.minutes > own.minutes) candles = foldIntoForming(chart.candles, chart.minutes, tick.candle);
    else return chart;
    if (candles === chart.candles) return chart;
    changed = true;
    return { ...chart, candles };
  });
  return changed ? { ...view, charts } : view;
}

/**
 * A lower-timeframe candle folded into the forming candle of a higher timeframe of
 * `minutes`, when it opened inside that candle. Anything else (a closed last candle, a
 * tick from before it or past its length) leaves the candles as they are: the next
 * check brings the new candle.
 */
export function foldIntoForming(candles: readonly Candle[], minutes: number, next: Candle): Candle[] {
  const last = candles[candles.length - 1];
  if (!last || !last.forming || next.t < last.t || next.t >= last.t + minutes * 60) return candles as Candle[];
  const high = Math.max(last.high, next.high);
  const low = Math.min(last.low, next.low);
  if (high === last.high && low === last.low && next.close === last.close) return candles as Candle[];
  return [...candles.slice(0, -1), { ...last, high, low, close: next.close }];
}

export function mergeCandle(candles: readonly Candle[], next: Candle): Candle[] {
  const last = candles[candles.length - 1];
  if (!last) return [next];
  if (next.t === last.t) return [...candles.slice(0, -1), next];
  if (next.t > last.t) {
    const closed = last.forming ? { ...last, forming: false } : last;
    return [...candles.slice(0, -1), closed, next];
  }
  return candles as Candle[];
}

// ---------- selectors ----------

/** The verdict on screen is not current: kept after an error, flagged by the server, or the link is down. */
export function isStale(model: Model): boolean {
  if (!model.view) return false;
  return model.viewStale || (model.status?.stale ?? false) || model.link !== 'open';
}

export function chartFor(view: VerdictView | null, role: string): ChartView | undefined {
  return view?.charts.find((c) => c.role === role);
}
