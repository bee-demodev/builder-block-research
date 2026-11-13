// Socket lifecycle: connect, validate frames at the boundary, reconnect with
// exponential backoff. The transport is injected so demo mode can stand in for
// the core without a second code path through the reducer.
import type { Action } from './store';
import { parseServerFrame, type ClientFrame } from './wire';

export interface SocketLike {
  onopen: ((ev: unknown) => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onclose: ((ev: unknown) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  readonly readyState: number;
  send(data: string): void;
  close(): void;
}

export type SocketFactory = () => SocketLike;

const OPEN = 1;

export interface BackoffOptions {
  baseMs: number;
  maxMs: number;
}

const DEFAULT_BACKOFF: BackoffOptions = { baseMs: 500, maxMs: 15_000 };

/** Delay before reconnect attempt `attempt` (0-based): doubling, capped, with +-20% jitter. */
export function backoffDelay(attempt: number, random: number, opts: BackoffOptions = DEFAULT_BACKOFF): number {
  const raw = Math.min(opts.maxMs, opts.baseMs * 2 ** Math.max(0, attempt));
  const jitter = 1 + (random * 2 - 1) * 0.2;
  return Math.round(Math.min(opts.maxMs, raw * jitter));
}

export class Connection {
  private socket: SocketLike | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private attempt = 0;
  private stopped = false;

  constructor(
    private readonly factory: SocketFactory,
    private readonly dispatch: (action: Action) => void,
    private readonly backoff: BackoffOptions = DEFAULT_BACKOFF,
  ) {}

  start(): void {
    this.stopped = false;
    this.open();
  }

  stop(): void {
    this.stopped = true;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    const s = this.socket;
    this.socket = null;
    if (s) {
      s.onclose = null;
      s.close();
    }
  }

  /** Skip the remaining backoff wait. */
  retryNow(): void {
    if (this.socket || this.stopped) return;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.open();
  }

  send(frame: ClientFrame): boolean {
    if (!this.socket || this.socket.readyState !== OPEN) return false;
    this.socket.send(JSON.stringify(frame));
    return true;
  }

  private open(): void {
    this.dispatch({ type: 'link', link: 'connecting' });
    let socket: SocketLike;
    try {
      socket = this.factory();
    } catch (err) {
      console.warn('[companion] could not open socket', err);
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;
    socket.onopen = () => {
      this.attempt = 0;
      this.dispatch({ type: 'link', link: 'open' });
    };
    socket.onmessage = (ev) => {
      if (typeof ev.data !== 'string') {
        console.warn('[companion] dropped non-text frame');
        return;
      }
      const frame = parseServerFrame(ev.data);
      if (frame) this.dispatch({ type: 'frame', frame });
    };
    socket.onerror = () => {
      // onclose follows; reconnect is handled there.
    };
    socket.onclose = () => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    if (this.stopped) return;
    const delay = backoffDelay(this.attempt, Math.random(), this.backoff);
    this.attempt += 1;
    this.dispatch({ type: 'down', retryAt: Date.now() + delay });
    this.timer = setTimeout(() => {
      this.timer = null;
      this.open();
    }, delay);
  }
}

/** ws://<page host>/ws when served by the core; ws://127.0.0.1:8765/ws (or VITE_COMPANION_WS) in dev. */
export function socketUrl(loc: Pick<Location, 'protocol' | 'host' | 'search'>, env: { DEV: boolean; VITE_COMPANION_WS?: string | undefined }): string {
  const override = new URLSearchParams(loc.search).get('ws');
  if (override) return override;
  if (env.DEV) return env.VITE_COMPANION_WS || 'ws://127.0.0.1:8765/ws';
  const scheme = loc.protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${loc.host}/ws`;
}
