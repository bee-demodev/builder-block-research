// Demo mode: a stand-in for the Python core. It speaks wire contract v1 as JSON
// text through a socket-shaped object, so frames take the same path as live ones
// (validation, reducer, render). All content is SAMPLE DATA from ./fixtures.
import type { SocketLike } from '../connection';
import type { Candle, ChartView, ClientFrame, ServerFrame, ServerState, SnapshotFrame, Status, VerdictView } from '../wire';
import {
  chartProblemView,
  demoOptions,
  demoState,
  errorStaleExtra,
  liveStatus,
  longView,
  sideView,
  snapshot,
  watchView,
} from './fixtures';
import { LOOK_WHEN, lookForView } from './lookfor';
import { LOOK_REVERSAL_STACK, LOOK_REVERSAL_WHEN, lookForReversalView } from './lookforReversal';
import { loadRealSnapshot, realStates, type RealScenario } from './real';
import { rng, roundTick } from './seeded';

export const DEMO_SCENARIOS = ['tour', 'watch', 'long', 'error', 'chart-problem', 'no-verdict', 'history', 'connecting', 'drop', 'real', 'real-triggered', 'real-planned', 'look-for', 'look-for-reversal'] as const;
export type DemoScenario = (typeof DEMO_SCENARIOS)[number];

type Step = 'watch' | 'long' | 'error' | 'chart-problem' | 'look-for' | 'look-for-reversal';
const TOUR: Step[] = ['watch', 'long', 'error', 'chart-problem'];

class DemoServer {
  private state: ServerState = { ...demoState };
  private seq = 0;
  private step: Step;
  private view: VerdictView | null = null;
  private socket: FakeSocket | null = null;
  private tickTimer: ReturnType<typeof setInterval> | null = null;
  private random = rng(99);
  private connects = 0;

  private real: Promise<SnapshotFrame> | null = null;
  /** The scenario's own moment: the latest bar. Earlier moments (a step back, bar replay) trim the candles to them. */
  private readonly latestWhen: string;

  constructor(private readonly scenario: DemoScenario) {
    if (scenario === 'real' || scenario === 'real-triggered' || scenario === 'real-planned') {
      this.state = { ...realStates[scenario as RealScenario] };
      this.real = loadRealSnapshot(scenario as RealScenario);
    }
    const named: readonly Step[] = ['long', 'error', 'chart-problem', 'look-for', 'look-for-reversal'];
    this.step = (named as readonly string[]).includes(scenario) ? (scenario as Step) : 'watch';
    if (scenario === 'look-for') this.state = { ...this.state, when: LOOK_WHEN };
    if (scenario === 'look-for-reversal') this.state = { ...this.state, when: LOOK_REVERSAL_WHEN, stack: LOOK_REVERSAL_STACK };
    this.latestWhen = this.state.when;
  }

  attach(socket: FakeSocket): void {
    this.socket = socket;
    this.connects += 1;
    // A restarted core begins its seq again; the client must accept that after hello.
    this.seq = 0;
    if (this.scenario === 'connecting') return; // stay in the skeleton forever
    setTimeout(() => this.greet(), this.connects === 1 ? 450 : 250);
    if (this.scenario === 'drop' && this.connects === 1) {
      setTimeout(() => socket.serverClose(), 6000);
    }
  }

  detach(socket: FakeSocket): void {
    if (this.socket === socket) this.socket = null;
    this.stopTicks();
  }

  receive(frame: ClientFrame): void {
    if (this.real) {
      // The saved real snapshot is fixed: Check (or any step) shows it again, cut to the
      // moment asked for (a step back, bar replay); its verdict and plan stay as saved.
      // A new side re-checks by itself, as the core does; the saved verdict cannot change.
      if (frame.type === 'set' && frame.side !== undefined) {
        this.setState({ side: frame.side });
        void this.publishReal();
      }
      if (frame.type === 'set' && frame.when) this.moveTo(frame.when);
      if (frame.type === 'step' && !this.stepBy(frame.direction)) return;
      if (frame.type === 'latest') this.setState({ when: this.latestWhen, follow: true });
      if (frame.type === 'check' || frame.type === 'step' || frame.type === 'latest') void this.publishReal();
      return;
    }
    switch (frame.type) {
      case 'check':
        this.setState({ busy: true });
        setTimeout(() => {
          // the tour moves on to its next state, except while looking back (bar replay reads the same one)
          if (this.scenario === 'tour' && this.state.follow) this.step = TOUR[(TOUR.indexOf(this.step) + 1) % TOUR.length]!;
          this.setState({ busy: false });
          this.publish();
        }, 700);
        return;
      case 'set': {
        const { type: _type, ...patch } = frame;
        const selectionChanged = patch.symbol !== undefined || patch.stack !== undefined || patch.style !== undefined;
        const { when, ...rest } = patch;
        this.setState(rest);
        if (when) this.moveTo(when);
        if (patch.side !== undefined && !selectionChanged) {
          // As in the core: a new side reads the same moment again at once, no Check needed.
          this.publish();
        } else if (selectionChanged) {
          // A new selection has no verdict until the trader presses Check.
          this.view = null;
          this.send(snapshot(++this.seq, null, { status: liveStatus }));
        } else if (when) {
          this.publish();
        }
        return;
      }
      case 'step':
        if (this.stepBy(frame.direction)) this.publish();
        return;
      case 'latest':
        this.setState({ when: this.latestWhen, follow: true });
        this.publish();
        return;
      case 'use_history':
        this.setState({ data: 'Saved history', live: false });
        this.step = 'watch';
        this.publish();
        return;
      case 'journal': {
        // As the core does: the call is kept and the view on screen is sent again with it.
        const trigger = this.view?.journal?.trigger;
        if (!this.view?.journal || !trigger || trigger.key !== frame.key) {
          this.send({ type: 'error', message: 'That trigger is not in the journal.' });
          return;
        }
        const mark = frame.mark;
        const marked = { ...trigger, mark, reason: mark ? (frame.reason ?? '') : '', note: mark ? (frame.note ?? '').trim() : '' };
        this.view = { ...this.view, journal: { ...this.view.journal, trigger: marked } };
        this.send(snapshot(++this.seq, this.view, { status: this.currentStatus() }));
        return;
      }
    }
  }

  private async publishReal(): Promise<void> {
    const frame = await this.real!;
    const view = frame.view && !this.state.follow ? cutView(frame.view, wallSeconds(this.state.when)) : frame.view;
    this.send({ ...frame, view, seq: ++this.seq });
  }

  /** `set when`, as the core reads it: New York wall time; at or past the latest bar follows it again. */
  private moveTo(text: string): void {
    const latest = wallSeconds(this.latestWhen);
    const t = Math.min(wallSeconds(text), latest);
    this.setState({ when: fromWallSeconds(t, this.latestWhen), follow: t >= latest });
  }

  /** One 5m bar either way; false (after an error reply, as the core sends) past either end of the sample. */
  private stepBy(direction: -1 | 1): boolean {
    const latest = wallSeconds(this.latestWhen);
    const now = wallSeconds(this.state.when);
    if (direction > 0 && now >= latest) {
      const message = this.state.live ? 'That is the last closed bar. The next one appears by itself when it closes.' : 'That is the end of the sample data.';
      this.send({ type: 'error', message });
      return false;
    }
    const t = Math.min(now + direction * 300, latest);
    if (t < latest - SAMPLE_REACH) {
      this.send({ type: 'error', message: 'That is the start of the sample data.' });
      return false;
    }
    this.setState({ when: fromWallSeconds(t, this.latestWhen), follow: t >= latest });
    return true;
  }

  private greet(): void {
    this.send({ type: 'hello', version: 1, options: demoOptions, state: this.state });
    if (this.real) {
      void this.publishReal();
      return;
    }
    if (this.scenario === 'no-verdict') {
      this.send(snapshot(++this.seq, null));
      return;
    }
    if (this.scenario === 'history') {
      this.send(
        snapshot(++this.seq, null, {
          error: 'TradingView Desktop is not running, so there are no live bars to read.',
          offer_history: true,
          status: { state: 'offline', text: 'TradingView not found · retrying every 10 s', stale: false },
          timing: null,
        }),
      );
      return;
    }
    if (this.step === 'error') {
      // Show a good verdict first, then the failure, so the stale case has something to keep.
      this.step = 'watch';
      this.publish();
      this.step = 'error';
      setTimeout(() => this.publish(), 900);
      return;
    }
    this.publish();
  }

  private publish(): void {
    if (this.step === 'error') {
      this.send(snapshot(++this.seq, null, errorStaleExtra));
      this.stopTicks();
      return;
    }
    const base =
      this.step === 'long'
        ? longView()
        : this.step === 'chart-problem'
          ? chartProblemView()
          : this.step === 'look-for'
            ? lookForView()
            : this.step === 'look-for-reversal'
              ? lookForReversalView()
              : watchView();
    this.view = sideView(base, this.state.side);
    if (!this.state.follow) this.view = cutView(this.view, wallSeconds(this.state.when));
    if (this.state.data === 'Saved history') {
      this.view = { ...this.view, source_note: 'Sample data, demo mode. Pretending to read saved history.' };
    }
    this.send(snapshot(++this.seq, this.view, { status: this.currentStatus() }));
    this.startTicks();
  }

  private currentStatus(): Status {
    if (this.state.data === 'Saved history') return { state: 'history', text: 'Saved history · sample data', stale: false };
    if (!this.state.follow) return { state: 'past', text: `Replaying ${this.state.when.slice(11, 16)} · later bars hidden`, stale: false };
    return liveStatus;
  }

  /** Nudge the forming candle of every chart each second; each timeframe gets its own tick. */
  private startTicks(): void {
    this.stopTicks();
    if (!this.state.follow) return;
    this.tickTimer = setInterval(() => {
      const view = this.view;
      if (!view || view.charts.length === 0) return;
      const entry = view.charts.find((c) => c.role === 'entry');
      const lastEntry = entry?.candles[entry.candles.length - 1];
      if (!lastEntry) return;
      const price = roundTick(lastEntry.close + (this.random() - 0.5) * 4);
      const charts = view.charts.map((chart) => {
        const last = chart.candles[chart.candles.length - 1];
        if (!last || !last.forming) return chart;
        const candle: Candle = { ...last, close: price, high: Math.max(last.high, price), low: Math.min(last.low, price) };
        this.send({ type: 'tick', timeframe: chart.timeframe, candle, last: price });
        return { ...chart, candles: [...chart.candles.slice(0, -1), candle] };
      });
      this.view = { ...view, charts };
    }, 1000);
  }

  private stopTicks(): void {
    if (this.tickTimer) clearInterval(this.tickTimer);
    this.tickTimer = null;
  }

  private setState(patch: Partial<ServerState>): void {
    this.state = { ...this.state, ...patch };
    this.send({ type: 'state', state: this.state });
  }

  private send(frame: ServerFrame): void {
    this.socket?.deliver(JSON.stringify(frame));
  }
}

/** How far back the sample lets you step or replay from its latest bar: six hours of 5m bars. */
const SAMPLE_REACH = 6 * 3600;

/** New York wall time ("YYYY-MM-DD HH:MM", any offset ignored) as epoch seconds read as UTC, as a candle's `t`. */
export function wallSeconds(when: string): number {
  return Date.parse(`${when.slice(0, 10)}T${when.slice(11, 16)}:00Z`) / 1000;
}

/** Back to the sample's ISO form, with the offset of `like` (every sample stays inside one offset). */
function fromWallSeconds(t: number, like: string): string {
  return `${new Date(t * 1000).toISOString().slice(0, 16)}:00${like.slice(19) || '-05:00'}`;
}

/**
 * The view as of wall time `t`: only candles that opened before it, the last of a higher
 * timeframe left forming (sample data: its prices are the whole candle's). Marks and the
 * plan that begin later are dropped; ones that ran on past it run to the right edge.
 */
export function cutView(view: VerdictView, t: number): VerdictView {
  return { ...view, charts: view.charts.map((chart) => cutChart(chart, t)) };
}

function cutChart(chart: ChartView, t: number): ChartView {
  const n = chart.candles.filter((c) => c.t < t).length;
  if (n === chart.candles.length) return chart;
  const candles = chart.candles.slice(0, n).map((c, i) => (i === n - 1 && c.t + chart.minutes * 60 > t ? { ...c, forming: true } : c));
  const marks = chart.marks
    .filter((m) => m.start === null || m.start < n)
    .map((m) => (m.end !== null && m.end >= n ? { ...m, end: null } : m));
  const tool = chart.tool && chart.tool.start < n ? chart.tool : null;
  return { ...chart, candles, marks, tool };
}

class FakeSocket implements SocketLike {
  onopen: SocketLike['onopen'] = null;
  onmessage: SocketLike['onmessage'] = null;
  onclose: SocketLike['onclose'] = null;
  onerror: SocketLike['onerror'] = null;
  readyState = 0;

  constructor(private readonly server: DemoServer) {
    setTimeout(() => {
      if (this.readyState === 3) return; // closed before it opened (React StrictMode remount)
      this.readyState = 1;
      this.onopen?.({});
      server.attach(this);
    }, 120);
  }

  send(data: string): void {
    if (this.readyState !== 1) return;
    this.server.receive(JSON.parse(data) as ClientFrame);
  }

  close(): void {
    if (this.readyState === 3) return;
    this.readyState = 3;
    this.server.detach(this);
  }

  deliver(data: string): void {
    if (this.readyState === 1) this.onmessage?.({ data });
  }

  /** Simulate the core dropping the connection. */
  serverClose(): void {
    this.close();
    this.onclose?.({});
  }
}

export function demoScenario(search: string, envFlag: string | undefined): DemoScenario | null {
  const params = new URLSearchParams(search);
  if (!params.has('demo') && envFlag !== '1' && envFlag !== 'true') return null;
  const value = params.get('demo') ?? '';
  return (DEMO_SCENARIOS as readonly string[]).includes(value) ? (value as DemoScenario) : 'tour';
}

export function demoSocketFactory(scenario: DemoScenario): () => SocketLike {
  const server = new DemoServer(scenario);
  return () => new FakeSocket(server);
}
