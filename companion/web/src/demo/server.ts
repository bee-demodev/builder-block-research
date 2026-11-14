// Demo mode: a stand-in for the Python core. It speaks wire contract v1 as JSON
// text through a socket-shaped object, so frames take the same path as live ones
// (validation, reducer, render). All content is SAMPLE DATA from ./fixtures.
import type { SocketLike } from '../connection';
import type { Candle, ClientFrame, ServerFrame, ServerState, SnapshotFrame, Status, VerdictView } from '../wire';
import {
  LATEST_WHEN,
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

  constructor(private readonly scenario: DemoScenario) {
    if (scenario === 'real' || scenario === 'real-triggered' || scenario === 'real-planned') {
      this.state = { ...realStates[scenario as RealScenario] };
      this.real = loadRealSnapshot(scenario as RealScenario);
    }
    const named: readonly Step[] = ['long', 'error', 'chart-problem', 'look-for', 'look-for-reversal'];
    this.step = (named as readonly string[]).includes(scenario) ? (scenario as Step) : 'watch';
    if (scenario === 'look-for') this.state = { ...this.state, when: LOOK_WHEN };
    if (scenario === 'look-for-reversal') this.state = { ...this.state, when: LOOK_REVERSAL_WHEN, stack: LOOK_REVERSAL_STACK };
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
      // The saved real snapshot is fixed: Check (or any step) shows it again.
      if (frame.type === 'pause') this.setState({ auto_refresh: !frame.paused });
      // A new side re-checks by itself, as the core does; the saved verdict cannot change.
      if (frame.type === 'set' && frame.side !== undefined) {
        this.setState({ side: frame.side });
        void this.publishReal();
      }
      if (frame.type === 'check' || frame.type === 'step' || frame.type === 'latest') void this.publishReal();
      return;
    }
    switch (frame.type) {
      case 'check':
        this.setState({ busy: true });
        setTimeout(() => {
          if (this.scenario === 'tour') this.step = TOUR[(TOUR.indexOf(this.step) + 1) % TOUR.length]!;
          this.setState({ busy: false });
          this.publish();
        }, 700);
        return;
      case 'set': {
        const { type: _type, ...patch } = frame;
        const selectionChanged = patch.symbol !== undefined || patch.stack !== undefined || patch.style !== undefined;
        this.setState(patch.when ? { ...patch, follow: patch.when.slice(0, 16) === LATEST_WHEN.slice(0, 16) } : patch);
        if (patch.side !== undefined && !selectionChanged) {
          // As in the core: a new side reads the same moment again at once, no Check needed.
          this.publish();
        } else if (selectionChanged) {
          // A new selection has no verdict until the trader presses Check.
          this.view = null;
          this.send(snapshot(++this.seq, null, { status: liveStatus }));
        } else if (patch.when) {
          this.publish();
        }
        return;
      }
      case 'step': {
        const minutes = toMinutes(this.state.when) + frame.direction * 5;
        const latest = toMinutes(LATEST_WHEN);
        const when = fromMinutes(Math.min(minutes, latest));
        this.setState({ when, follow: minutes >= latest });
        this.publish();
        return;
      }
      case 'latest':
        this.setState({ when: LATEST_WHEN, follow: true });
        this.publish();
        return;
      case 'pause':
        this.setState({ auto_refresh: !frame.paused });
        this.send({ type: 'status', status: this.currentStatus() });
        if (frame.paused) this.stopTicks();
        else this.startTicks();
        return;
      case 'use_history':
        this.setState({ data: 'Saved history', live: false });
        this.step = 'watch';
        this.publish();
        return;
    }
  }

  private async publishReal(): Promise<void> {
    const frame = await this.real!;
    this.send({ ...frame, seq: ++this.seq });
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
    if (this.state.data === 'Saved history') {
      this.view = { ...this.view, source_note: 'Sample data, demo mode. Pretending to read saved history.' };
    }
    this.send(snapshot(++this.seq, this.view, { status: this.currentStatus() }));
    if (this.state.auto_refresh) this.startTicks();
  }

  private currentStatus(): Status {
    if (!this.state.auto_refresh) return { state: 'paused', text: 'Paused · press Space to resume', stale: false };
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

function toMinutes(iso: string): number {
  return Date.parse(iso) / 60000;
}

function fromMinutes(minutes: number): string {
  // Sample timestamps stay on 12 Nov 2026, which is EST (-05:00).
  const d = new Date(minutes * 60000 - 5 * 3600 * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:00-05:00`;
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
