import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { demoState } from './demo/fixtures';
import { parseRealSnapshot } from './demo/real';
import { cutView, wallSeconds } from './demo/server';
import { atLatest, cutWhen, initialReplay, readyForNext, reduceReplay, type Replay, type ReplayAction } from './replay';

const run = (actions: ReplayAction[], from: Replay = initialReplay()) => actions.reduce(reduceReplay, from);

describe('bar replay playback', () => {
  it('waits for the snapshot of each cut and step before the next step may go out', () => {
    let r = run([{ type: 'open' }, { type: 'cut', seq: 7 }, { type: 'play' }]);
    expect(r.mode).toBe('playing');
    expect(readyForNext(r)).toBe(false); // the cut's own snapshot is not in yet
    r = reduceReplay(r, { type: 'snapshot', seq: 7 });
    expect(readyForNext(r)).toBe(false); // an older snapshot does not count
    r = reduceReplay(r, { type: 'snapshot', seq: 8 });
    expect(readyForNext(r)).toBe(true);
    r = run([{ type: 'stepped', seq: 8 }], r);
    expect(readyForNext(r)).toBe(false);
    r = run([{ type: 'snapshot', seq: 9 }], r);
    expect(readyForNext(r)).toBe(true);
  });

  it('pauses on an error and drops the wait of a cut the core refused', () => {
    const playing = run([{ type: 'open' }, { type: 'cut', seq: 1 }, { type: 'snapshot', seq: 2 }, { type: 'play' }, { type: 'stepped', seq: 2 }]);
    expect(run([{ type: 'stop' }], playing)).toMatchObject({ mode: 'paused', awaiting: null });
    const refused = run([{ type: 'open' }, { type: 'cut', seq: 4 }, { type: 'stop' }]);
    expect(refused).toMatchObject({ mode: 'paused', awaiting: null });
  });

  it('Esc in Select bar goes back to where it began', () => {
    expect(run([{ type: 'open' }, { type: 'cancelSelect' }]).mode).toBe('off');
    expect(run([{ type: 'open' }, { type: 'cut', seq: 1 }, { type: 'play' }, { type: 'select' }, { type: 'cancelSelect' }]).mode).toBe('paused');
  });

  it('cannot play before a start bar is picked, and keeps the speed when it ends', () => {
    expect(run([{ type: 'open' }, { type: 'play' }]).mode).toBe('select');
    expect(run([{ type: 'play' }]).mode).toBe('off');
    expect(run([{ type: 'speed', speed: '10x' }, { type: 'open' }, { type: 'close' }])).toEqual(initialReplay('10x'));
  });
});

describe('cutWhen', () => {
  it('cuts at the close of the clicked candle, in New York wall time', () => {
    const fiveMinute = { t: Date.UTC(2025, 10, 18, 8, 25) / 1000 };
    expect(cutWhen(fiveMinute, 5)).toBe('2025-11-18 08:30');
    const hour = { t: Date.UTC(2025, 10, 18, 23, 0) / 1000 };
    expect(cutWhen(hour, 60)).toBe('2025-11-19 00:00');
  });
});

describe('atLatest', () => {
  it('is only the live last closed bar: saved history keeps follow set and still steps forward', () => {
    expect(atLatest({ ...demoState, live: true, follow: true })).toBe(true);
    expect(atLatest({ ...demoState, live: true, follow: false })).toBe(false);
    expect(atLatest({ ...demoState, live: false, follow: true })).toBe(false);
    expect(atLatest(null)).toBe(false);
  });
});

describe('demo replay cut', () => {
  const view = parseRealSnapshot(readFileSync(new URL('./demo/real-triggered.json', import.meta.url), 'utf8')).view!;

  it('shows no candle that opened at or after the replay time, and no mark that begins later', () => {
    const t = wallSeconds('2025-11-18 06:00');
    const cut = cutView(view, t);
    for (const chart of cut.charts) {
      expect(chart.candles.length).toBeGreaterThan(0);
      expect(chart.candles.every((c) => c.t < t)).toBe(true);
      expect(chart.marks.every((m) => (m.start === null || m.start < chart.candles.length) && (m.end === null || m.end < chart.candles.length))).toBe(true);
      expect(chart.tool === null || chart.tool.start < chart.candles.length).toBe(true);
    }
    const hour = cut.charts.find((c) => c.minutes === 60)!;
    expect(hour.candles[hour.candles.length - 1]!.forming).toBe(false); // 05:00 closed at 06:00
    const day = cut.charts.find((c) => c.minutes === 1440)!;
    expect(day.candles[day.candles.length - 1]!.forming).toBe(true);
  });
});
