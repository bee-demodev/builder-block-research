// REAL snapshots, saved from the Python core on saved history (NQ, 1D / 1h / 5m,
// ttrades). Copies of tests/companion/fixtures/snapshot_v1*.json:
//  - real:           2025-11-18, side Auto, a triggered short.
//  - real-triggered: 2025-11-18 08:30, side Short, plan triggered, every step done.
//  - real-planned:   2025-11-19 10:15, side Short, plan only planned; steps blocked, next, later.
// Unlike ./fixtures they are not invented: they carry the long sentences, the nine
// checklist groups and the ~160 candles per chart that the core really sends, so the
// layout is checked against them (`?demo=real`, `?demo=real-triggered`,
// `?demo=real-planned`, and the tests).
import { validateFrame, type ServerState, type SnapshotFrame } from '../wire';

export type RealScenario = 'real' | 'real-triggered' | 'real-planned';

export function parseRealSnapshot(raw: string): SnapshotFrame {
  const r = validateFrame(raw);
  if (!r.ok) throw new Error(`real snapshot fixture is not a valid frame: ${r.reason}`);
  if (r.frame.type !== 'snapshot') throw new Error('real snapshot fixture is not a snapshot frame');
  return r.frame;
}

/** Loaded on demand so the bundle only carries a snapshot when its scenario is opened. */
export async function loadRealSnapshot(which: RealScenario = 'real'): Promise<SnapshotFrame> {
  const raw =
    which === 'real-triggered'
      ? (await import('./real-triggered.json?raw')).default
      : which === 'real-planned'
        ? (await import('./real-planned.json?raw')).default
        : (await import('./real-snapshot.json?raw')).default;
  return parseRealSnapshot(raw);
}

const base: ServerState = {
  symbol: 'NQ',
  stack: '1D / 1h / 5m',
  style: 'ttrades',
  data: 'history',
  when: '2025-11-18T08:25:00-05:00',
  follow: true,
  auto_refresh: true,
  busy: false,
  live: false,
  side: '',
};

/** The selection each snapshot was made with, as the core's hello would report it. */
export const realStates: Record<RealScenario, ServerState> = {
  real: base,
  'real-triggered': { ...base, when: '2025-11-18T08:30:00-05:00', side: 'short' },
  'real-planned': { ...base, when: '2025-11-19T10:15:00-05:00', side: 'short' },
};

