// The decision journal block, as words and frames: what the panel shows for a
// stack's journal and what a click sends. Display only; the core keeps the journal.
import type { ClientFrame, Journal, JournalMark, JournalStats, JournalTrigger } from './wire';

export interface JournalRow {
  key: 'taken' | 'skipped' | 'all';
  label: string;
  n: number;
  /** "+0.42R", "-1.00R"; "" when nothing has closed. */
  avg: string;
  /** Fewer closed trades than the journal needs before an average means anything. */
  few: boolean;
}

/** "+0.42R" / "-0.10R" / "0.00R". A plain hyphen for the minus, as the core writes R. */
export function signedR(value: number): string {
  const rounded = Math.round(value * 100) / 100;
  if (rounded === 0) return '0.00R';
  return `${rounded > 0 ? '+' : '-'}${Math.abs(rounded).toFixed(2)}R`;
}

/** Your taken trades, your skipped ones, and every logged trigger (the engine's baseline). */
export function journalRows(stats: JournalStats): JournalRow[] {
  const row = (key: JournalRow['key'], label: string): JournalRow => {
    const t = stats[key];
    return { key, label, n: t.n, avg: t.avg_r === null || t.n === 0 ? '' : signedR(t.avg_r), few: t.n < stats.min_n };
  };
  return [row('taken', 'Took'), row('skipped', 'Skipped'), row('all', 'All triggers')];
}

/** Said plainly when a count is too small to read anything into. "" when every count is big enough. */
export function sampleNote(stats: JournalStats): string {
  if (journalRows(stats).every((r) => !r.few)) return '';
  return `Under ${stats.min_n} closed trades is too few to mean anything yet.`;
}

/** "1 call made after its trade ended is left out of Took and Skipped." or "". */
export function lateNote(stats: JournalStats): string {
  if (!stats.late) return '';
  return stats.late === 1
    ? '1 call made after its trade ended is left out of Took and Skipped.'
    : `${stats.late} calls made after their trades ended are left out of Took and Skipped.`;
}

/** A trigger whose trade has ended: what happened, and the call if one was made in time. */
export function endedLine(trigger: JournalTrigger): string {
  const how = trigger.outcome === 'target_reached' ? 'reached its target' : 'was stopped';
  const r = trigger.result_r === null ? '' : ` (${signedR(trigger.result_r)})`;
  if (trigger.mark === 'took') return `You took it. It ${how}${r}.`;
  if (trigger.mark === 'skipped') return `You skipped it. It ${how}${r}.`;
  return `It ${how}${r} before a call was made, so there is nothing to mark.`;
}

/** "2 still open" or "". */
export function openNote(stats: JournalStats): string {
  return stats.open > 0 ? `${stats.open} still open` : '';
}

/** Took it / Skipped: a second press on the call already made clears it. */
export function markFrame(trigger: JournalTrigger, mark: Exclude<JournalMark, ''>, note: string): ClientFrame {
  if (trigger.mark === mark) return { type: 'journal', key: trigger.key, mark: '' };
  return { type: 'journal', key: trigger.key, mark, reason: mark === 'skipped' ? trigger.reason : '', note };
}

/** A skip reason: picking one marks the trigger skipped; picking the one chosen again takes it off. */
export function reasonFrame(trigger: JournalTrigger, reason: string, note: string): ClientFrame {
  return { type: 'journal', key: trigger.key, mark: 'skipped', reason: trigger.reason === reason ? '' : reason, note };
}

/** The note, saved with the call as it stands. Null when there is no call to attach it to or nothing changed. */
export function noteFrame(trigger: JournalTrigger, note: string): ClientFrame | null {
  const text = note.trim();
  if (!trigger.mark || text === trigger.note) return null;
  return { type: 'journal', key: trigger.key, mark: trigger.mark, reason: trigger.reason, note: text };
}

/** The reasons the core offers, or the fixed set when an older core sent none. */
export function journalReasons(journal: Journal): { key: string; label: string }[] {
  return journal.reasons.length > 0 ? journal.reasons : [...DEFAULT_REASONS];
}

export const DEFAULT_REASONS: readonly { key: string; label: string }[] = [
  { key: 'late', label: 'Late' },
  { key: 'no_confluence', label: 'No confluence' },
  { key: 'news', label: 'News' },
  { key: 'risk_too_big', label: 'Risk too big' },
  { key: 'other', label: 'Other' },
];
