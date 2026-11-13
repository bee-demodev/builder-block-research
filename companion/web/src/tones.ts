// Colour is reserved for meaning. Every place that colours something asks this
// module which semantic tone to use; CSS and the chart palette turn the tone into
// an actual colour per theme.
import type { CheckGroup, CheckRow, Direction, Level, ReadStatus, RowStatus, StatusState, StepStatus, Tone } from './wire';

/**
 * bull = confirmed / passed / done, bear = failed / blocked / error, watch = waiting / next,
 * long and short = the side of a trade, reward and risk = target and stop,
 * muted = no meaning. The direction colour scheme decides what each looks like.
 */
export type Semantic = 'bull' | 'bear' | 'watch' | 'muted' | 'long' | 'short' | 'reward' | 'risk';

const DIRECTIONAL_ROLES = new Set(['entry', 'poi', 'protected']);

export function directionTone(direction: Direction): Semantic {
  return direction === 'long' ? 'long' : direction === 'short' ? 'short' : 'muted';
}

/**
 * Chart mark role -> tone. Stops and targets are risk and reward on either side, as
 * the tool draws them; confirmations have their own colour; the entry, points of
 * interest and protected levels follow the view's direction.
 */
export function markTone(role: string, direction: Direction): Semantic {
  const r = role.trim().toLowerCase();
  if (r === 'waiting' || r === 'next') return 'watch';
  if (r === 'stop') return 'risk';
  if (r === 'target') return 'reward';
  if (r === 'confirm') return 'bull';
  if (DIRECTIONAL_ROLES.has(r)) return directionTone(direction);
  return 'muted';
}

export function stepTone(status: StepStatus): Semantic {
  switch (status) {
    case 'done':
      return 'bull';
    case 'next':
      return 'watch';
    case 'later':
      return 'muted';
    case 'blocked':
      return 'bear';
  }
}

export function readTone(status: ReadStatus): Semantic {
  switch (status) {
    case 'confirmed':
      return 'bull';
    case 'waiting':
      return 'watch';
    case 'failed':
      return 'bear';
    case 'not_applicable':
      return 'muted';
  }
}

export function rowTone(status: RowStatus): Semantic {
  switch (status) {
    case 'pass':
      return 'bull';
    case 'fail':
      return 'bear';
    case 'na':
      return 'watch';
  }
}

/** Decision word colour. "Don't trade" and neutral carry no colour: they are not a failure. */
export function decisionTone(tone: Tone): Semantic | 'text' {
  switch (tone) {
    case 'long':
      return 'long';
    case 'short':
      return 'short';
    case 'watch':
      return 'watch';
    case 'no_trade':
    case 'neutral':
      return 'text';
  }
}

export function statusTone(state: StatusState): Semantic {
  switch (state) {
    case 'live':
      return 'bull';
    case 'connecting':
    case 'stale':
      return 'watch';
    case 'offline':
      return 'bear';
    case 'history':
    case 'paused':
    case 'past':
      return 'muted';
  }
}

/** Only states of a live feed get the status dot. */
export function hasDot(state: StatusState): boolean {
  return state === 'live' || state === 'stale' || state === 'connecting' || state === 'offline';
}

/** Levels carry no role on the wire, so the stop row is recognised by its name. */
export function isStopLevel(level: Level): boolean {
  return /\bstop\b/i.test(level.name);
}

export interface CheckTotals {
  passed: number;
  failed: number;
  notEvaluated: number;
  total: number;
}

/**
 * Totals over the groups in play only (`active`). Rules from a path that is not in
 * play say nothing about this read, so counting them would mislead.
 */
export function checkTotals(groups: readonly CheckGroup[]): CheckTotals {
  let passed = 0;
  let failed = 0;
  let notEvaluated = 0;
  for (const g of groups) {
    if (!g.active) continue;
    passed += g.passed;
    failed += g.failed;
    notEvaluated += g.not_evaluated;
  }
  return { passed, failed, notEvaluated, total: passed + failed + notEvaluated };
}

/** A group's tally: full ("2 of 3 passed, 1 failed, 1 not evaluated") and short ("2 of 3, 1 failed"). */
export function groupTally(g: Pick<CheckGroup, 'passed' | 'failed' | 'not_evaluated'>): { full: string; short: string } {
  const total = g.passed + g.failed + g.not_evaluated;
  const failed = g.failed > 0 ? `, ${g.failed} failed` : '';
  const ne = g.not_evaluated > 0 ? `, ${g.not_evaluated} not evaluated` : '';
  return { full: `${g.passed} of ${total} passed${failed}${ne}`, short: `${g.passed} of ${total}${failed}` };
}

/** Groups in play first, the rest after, each keeping the server's order. */
export function orderGroups<T extends Pick<CheckGroup, 'active'>>(groups: readonly T[]): { inPlay: T[]; notInPlay: T[] } {
  return { inPlay: groups.filter((g) => g.active), notInPlay: groups.filter((g) => !g.active) };
}

/**
 * Split groups into two columns, keeping their order, at the point that best
 * balances the row counts (the left column takes the extra when uneven).
 */
export function splitColumns<T extends { rows: readonly unknown[] }>(groups: readonly T[]): [T[], T[]] {
  if (groups.length <= 1) return [groups.slice(), []];
  const weight = (g: T) => g.rows.length + 2; // header counts for about two rows
  const total = groups.reduce((s, g) => s + weight(g), 0);
  let best = 1;
  let bestDiff = Infinity;
  let left = 0;
  for (let k = 1; k < groups.length; k++) {
    left += weight(groups[k - 1]!);
    const diff = Math.abs(left - (total - left));
    if (diff < bestDiff) {
      bestDiff = diff;
      best = k;
    }
  }
  return [groups.slice(0, best), groups.slice(best)];
}

/** Advisory rules in the groups in play; a path not in play says nothing about this read. */
export function advisoryInPlay(groups: readonly CheckGroup[]): number {
  return groups.reduce((n, g) => (g.active ? n + g.rows.filter((r) => r.advisory).length : n), 0);
}

export type RowFilter = 'core' | 'quality' | 'advisory';

/** Which Details filter toggle a row belongs to: advisory rows, quality-tagged rows, or the gates and steps. */
export function rowFilter(row: CheckRow): RowFilter {
  if (row.advisory) return 'advisory';
  if (row.tags.some((t) => t.toLowerCase() === 'quality')) return 'quality';
  return 'core';
}
