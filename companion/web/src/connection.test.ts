import { afterEach, describe, expect, it, vi } from 'vitest';
import { Connection, backoffDelay, socketUrl, type SocketLike } from './connection';
import type { Action } from './store';

describe('backoffDelay', () => {
  it('doubles from 500 ms and caps at 15 s, jitter within 20%', () => {
    expect(backoffDelay(0, 0.5)).toBe(500);
    expect(backoffDelay(1, 0.5)).toBe(1000);
    expect(backoffDelay(3, 0.5)).toBe(4000);
    expect(backoffDelay(20, 0.5)).toBe(15000);
    expect(backoffDelay(20, 1)).toBe(15000);
    expect(backoffDelay(2, 0)).toBe(1600);
    expect(backoffDelay(2, 1)).toBe(2400);
  });
});

describe('socketUrl', () => {
  const loc = (host: string, search = '', protocol = 'http:') => ({ host, search, protocol });
  it('uses the page host when served by the core', () => {
    expect(socketUrl(loc('127.0.0.1:8765'), { DEV: false })).toBe('ws://127.0.0.1:8765/ws');
    expect(socketUrl(loc('box:443', '', 'https:'), { DEV: false })).toBe('wss://box:443/ws');
  });
  it('uses the configured or default core address in dev', () => {
    expect(socketUrl(loc('127.0.0.1:5173'), { DEV: true })).toBe('ws://127.0.0.1:8765/ws');
    expect(socketUrl(loc('127.0.0.1:5173'), { DEV: true, VITE_COMPANION_WS: 'ws://10.0.0.2:9000/ws' })).toBe('ws://10.0.0.2:9000/ws');
  });
  it('lets ?ws= override both', () => {
    expect(socketUrl(loc('x', '?ws=ws://a/ws'), { DEV: false })).toBe('ws://a/ws');
  });
});

class TestSocket implements SocketLike {
  static all: TestSocket[] = [];
  onopen: SocketLike['onopen'] = null;
  onmessage: SocketLike['onmessage'] = null;
  onclose: SocketLike['onclose'] = null;
  onerror: SocketLike['onerror'] = null;
  readyState = 0;
  sent: string[] = [];
  constructor() {
    TestSocket.all.push(this);
  }
  send(d: string) {
    this.sent.push(d);
  }
  close() {
    this.readyState = 3;
  }
  open() {
    this.readyState = 1;
    this.onopen?.({});
  }
  drop() {
    this.readyState = 3;
    this.onclose?.({});
  }
}

describe('Connection', () => {
  afterEach(() => {
    vi.useRealTimers();
    TestSocket.all = [];
  });

  it('dispatches valid frames, drops malformed ones, and reconnects with backoff after a drop', () => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const actions: Action[] = [];
    const conn = new Connection(() => new TestSocket(), (a) => actions.push(a));
    conn.start();
    const s1 = TestSocket.all[0]!;
    s1.open();

    s1.onmessage?.({ data: '{"type":"error","message":"hi"}' });
    s1.onmessage?.({ data: '{"type":"error"}' });
    s1.onmessage?.({ data: new ArrayBuffer(2) });
    const frames = actions.filter((a) => a.type === 'frame');
    expect(frames).toHaveLength(1);
    expect(warn).toHaveBeenCalledTimes(2);

    expect(conn.send({ type: 'check' })).toBe(true);
    expect(s1.sent).toEqual(['{"type":"check"}']);

    s1.drop();
    expect(actions.at(-1)).toMatchObject({ type: 'down' });
    expect(conn.send({ type: 'check' })).toBe(false);
    vi.advanceTimersByTime(499);
    expect(TestSocket.all).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(TestSocket.all).toHaveLength(2);

    // second failure waits twice as long
    TestSocket.all[1]!.drop();
    vi.advanceTimersByTime(999);
    expect(TestSocket.all).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(TestSocket.all).toHaveLength(3);

    // a successful open resets the backoff
    TestSocket.all[2]!.open();
    TestSocket.all[2]!.drop();
    vi.advanceTimersByTime(500);
    expect(TestSocket.all).toHaveLength(4);
    conn.stop();
    vi.restoreAllMocks();
  });

  it('retryNow skips the wait, and stop prevents any further reconnect', () => {
    vi.useFakeTimers();
    const conn = new Connection(() => new TestSocket(), () => {});
    conn.start();
    TestSocket.all[0]!.drop();
    conn.retryNow();
    expect(TestSocket.all).toHaveLength(2);
    conn.stop();
    vi.advanceTimersByTime(60_000);
    expect(TestSocket.all).toHaveLength(2);
  });
});
