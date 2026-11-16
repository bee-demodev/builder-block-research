import { describe, expect, it } from 'vitest';
import { demoOptions, demoState, errorStaleExtra, longView, snapshot, watchView } from './demo/fixtures';
import { foldIntoForming, initialModel, isStale, mergeCandle, reduce, type Model } from './store';
import type { Candle, ServerFrame } from './wire';

const frame = (m: Model, f: ServerFrame) => reduce(m, { type: 'frame', frame: f });
const hello = (m: Model = initialModel) => frame(m, { type: 'hello', version: 1, options: demoOptions, state: demoState });

describe('snapshots', () => {
  it('ignores a snapshot with a lower seq than the one shown, accepts equal and higher', () => {
    const long = longView();
    let m = frame(hello(), snapshot(5, watchView()));
    m = frame(m, snapshot(4, long));
    expect(m.view?.decision).toBe('watch');
    expect(m.seq).toBe(5);
    m = frame(m, snapshot(5, long));
    expect(m.view?.decision).toBe('long');
    m = frame(m, snapshot(6, watchView()));
    expect(m.view?.decision).toBe('watch');
  });

  it('keeps the last good verdict when a snapshot carries only an error, and marks it stale', () => {
    let m = frame(hello(), snapshot(1, watchView()));
    const shown = m.view;
    m = frame(m, snapshot(2, null, errorStaleExtra));
    expect(m.view).toBe(shown);
    expect(m.viewStale).toBe(true);
    expect(m.error).toMatch(/stopped answering/);
    expect(m.offerHistory).toBe(true);
    expect(isStale(m)).toBe(true);
  });

  it('clears staleness and the error when a fresh verdict arrives', () => {
    let m = frame(hello(), snapshot(1, watchView()));
    m = frame(m, snapshot(2, null, errorStaleExtra));
    m = frame(m, snapshot(3, longView()));
    expect(m.viewStale).toBe(false);
    expect(m.error).toBe('');
    expect(isStale(m)).toBe(false);
  });

  it('an error before any verdict is not "stale": there is nothing to keep', () => {
    const m = frame(hello(), snapshot(1, null, errorStaleExtra));
    expect(m.view).toBeNull();
    expect(m.viewStale).toBe(false);
    expect(isStale(m)).toBe(false);
  });

  it('a snapshot with neither verdict nor error means nothing checked yet and clears the old verdict', () => {
    let m = frame(hello(), snapshot(1, watchView()));
    m = frame(m, snapshot(2, null));
    expect(m.view).toBeNull();
    expect(m.snapshotReceived).toBe(true);
  });

  it('honours the server stale flag even on a fresh verdict', () => {
    const m = frame(hello(), snapshot(1, watchView(), { status: { state: 'stale', text: 'x', stale: true } }));
    expect(isStale(m)).toBe(true);
  });

  it('accepts a restarted core whose seq begins again after a new hello', () => {
    let m = frame(hello(), snapshot(40, watchView()));
    m = reduce(m, { type: 'down', retryAt: 0 });
    expect(isStale(m)).toBe(true);
    m = hello(m);
    expect(m.view?.decision).toBe('watch'); // kept until the new session reports
    m = frame(m, snapshot(1, longView()));
    expect(m.view?.decision).toBe('long');
  });
});

describe('server state', () => {
  it('reflects state frames rather than local guesses', () => {
    let m = hello();
    m = frame(m, { type: 'state', state: { ...demoState, busy: true, symbol: 'ES1!' } });
    expect(m.server?.busy).toBe(true);
    expect(m.server?.symbol).toBe('ES1!');
    m = frame(m, { type: 'state', state: { ...demoState, auto_refresh: false } });
    expect(m.server?.symbol).toBe('NQ1!');
  });

  it('keeps error frame messages until dismissed', () => {
    let m = frame(hello(), { type: 'error', message: 'Unknown symbol' });
    expect(m.notice).toBe('Unknown symbol');
    m = reduce(m, { type: 'dismissNotice' });
    expect(m.notice).toBeNull();
  });

  it('counts every error frame, a repeat of the same message too (bar replay pauses on each)', () => {
    let m = frame(hello(), { type: 'error', message: 'That is the end of the data.' });
    m = frame(m, { type: 'error', message: 'That is the end of the data.' });
    expect(m.errors).toBe(2);
  });
});

describe('ticks', () => {
  const lastOf = (m: Model, tf: string) => {
    const c = m.view!.charts.find((x) => x.timeframe === tf)!.candles;
    return c[c.length - 1]!;
  };

  it('updates the chart of the tick timeframe in place', () => {
    const m0 = frame(hello(), snapshot(1, watchView()));
    const entry = m0.view!.charts.find((c) => c.timeframe === '5m')!;
    const forming = entry.candles[entry.candles.length - 1]!;
    const candle: Candle = { ...forming, close: forming.close + 3, high: Math.max(forming.high, forming.close + 3) };
    const m1 = frame(m0, { type: 'tick', timeframe: '5m', candle, last: candle.close });

    expect(lastOf(m1, '5m').close).toBe(forming.close + 3);
    expect(m1.view!.charts.find((c) => c.timeframe === '5m')!.candles).toHaveLength(entry.candles.length);
    // earlier candles keep identity so the chart can update without a redraw
    expect(m1.view!.charts.find((c) => c.timeframe === '5m')!.candles[0]).toBe(entry.candles[0]);
    expect(m1.lastPrice['5m']).toBe(candle.close);
  });

  it('moves the forming candle of every higher timeframe the tick falls inside, so the panes keep agreeing', () => {
    const m0 = frame(hello(), snapshot(1, watchView()));
    const entry = m0.view!.charts.find((c) => c.timeframe === '5m')!;
    const forming = entry.candles[entry.candles.length - 1]!;
    const spike = lastOf(m0, '1D').high + 40; // above anything on screen
    const candle: Candle = { ...forming, close: spike - 10, high: spike };
    const m1 = frame(m0, { type: 'tick', timeframe: '5m', candle, last: candle.close });
    for (const tf of ['1h', '1D']) {
      const before = m0.view!.charts.find((c) => c.timeframe === tf)!.candles;
      const after = m1.view!.charts.find((c) => c.timeframe === tf)!.candles;
      expect(after).toHaveLength(before.length);
      expect(after.at(-1)).toMatchObject({ high: spike, close: spike - 10, low: before.at(-1)!.low, open: before.at(-1)!.open, forming: true });
      expect(after[0]).toBe(before[0]);
    }
  });

  it('leaves a higher timeframe alone when the tick is outside its forming candle, and never moves a lower one', () => {
    const m0 = frame(hello(), snapshot(1, watchView()));
    const setup = m0.view!.charts.find((c) => c.timeframe === '1h')!;
    const hourLast = setup.candles.at(-1)!;
    const late: Candle = { ...hourLast, t: hourLast.t + 3600, high: hourLast.high + 50 }; // past the forming 1h candle
    expect(foldIntoForming(setup.candles, 60, late)).toBe(setup.candles);
    const closed = [...setup.candles.slice(0, -1), { ...hourLast, forming: false }];
    expect(foldIntoForming(closed, 60, { ...hourLast, high: hourLast.high + 50 })).toBe(closed);
    // a 1h tick does not touch the 5m chart
    const m1 = frame(m0, { type: 'tick', timeframe: '1h', candle: { ...hourLast, close: hourLast.close + 1 }, last: 0 });
    expect(m1.view!.charts.find((c) => c.timeframe === '5m')).toBe(m0.view!.charts.find((c) => c.timeframe === '5m'));
  });

  it('ignores a tick for a timeframe that is not on screen, and a tick with no verdict', () => {
    const m0 = frame(hello(), snapshot(1, watchView()));
    const c = m0.view!.charts[0]!.candles[0]!;
    expect(frame(m0, { type: 'tick', timeframe: '15m', candle: c, last: 1 }).view).toBe(m0.view);
    expect(frame(hello(), { type: 'tick', timeframe: '5m', candle: c, last: 1 }).view).toBeNull();
  });
});

describe('mergeCandle', () => {
  const c = (t: number, close: number, forming = false): Candle => ({ time: '', t, open: close, high: close, low: close, close, forming, label: '' });

  it('replaces the last candle with the same open time', () => {
    const out = mergeCandle([c(1, 10), c(2, 11, true)], c(2, 12, true));
    expect(out.map((x) => x.close)).toEqual([10, 12]);
  });

  it('appends a later candle and closes the one before it', () => {
    const out = mergeCandle([c(1, 10), c(2, 11, true)], c(3, 12, true));
    expect(out).toHaveLength(3);
    expect(out[1]!.forming).toBe(false);
    expect(out[2]!.forming).toBe(true);
  });

  it('ignores a candle older than the last one', () => {
    const list = [c(1, 10), c(2, 11)];
    expect(mergeCandle(list, c(1, 99))).toBe(list);
  });
});
