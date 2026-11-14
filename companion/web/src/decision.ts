// What the decision panel shows, decided apart from the markup so it can be tested:
// the suggestion line, which step is the focus, what replaces what, the plan's words
// and the side selector's choices.
import { formatPrice, plainText, priceDecimals, sentenceCase, wallClock } from './format';
import { DEFAULT_SIDES, DEFAULT_SIDE_LABELS, type ClientFrame, type Options, type Plan, type ServerState, type Side, type Step, type VerdictView } from './wire';

/** "WATCH · SHORT" -> "Watch, short"; "SHORT · TARGET REACHED" -> "Short, target reached". */
export function suggestionText(view: Pick<VerdictView, 'suggestion' | 'decision_word'>): string {
  return sentenceCase(plainText(view.suggestion || view.decision_word));
}

/** The step the trader is waiting on: the one marked next (the core marks at most one). */
export function focusedStep(steps: readonly Step[]): Step | null {
  return steps.find((s) => s.status === 'next') ?? null;
}

export interface Sections {
  /** The single "Waiting for" block: what has to happen next. */
  waiting: boolean;
  /** The plan block; it replaces the levels rows. */
  plan: boolean;
  levels: boolean;
}

export function sections(view: Pick<VerdictView, 'steps' | 'waiting_for' | 'plan' | 'has_levels' | 'levels'>): Sections {
  const plan = view.plan !== null;
  return {
    waiting: waitingText(view) !== '',
    plan,
    levels: !plan && view.has_levels && view.levels.length > 0,
  };
}

/**
 * The one thing the trader is waiting for: the core's `waiting_for`, else the detail
 * (or label) of the step marked next, else "" when nothing is pending.
 */
export function waitingText(view: Pick<VerdictView, 'steps' | 'waiting_for'>): string {
  const told = plainText(view.waiting_for).trim();
  if (told) return told;
  const next = focusedStep(view.steps);
  return next ? plainText(next.detail || next.label).trim() : '';
}

/**
 * The New York session checkpoints TTrades works to (knowledge/ttrades_livestream_playbook.md,
 * "The session clock"): the open, the first 15m close, 10:00 when the 4H and 1H open, and
 * the end of his window.
 */
export const CHECKPOINTS: readonly { time: string; label: string }[] = [
  { time: '09:30', label: 'New York open' },
  { time: '09:45', label: 'first 15m close' },
  { time: '10:00', label: 'new 4H and 1H candles' },
  { time: '10:30', label: 'window closing' },
  { time: '11:00', label: 'window closed' },
];

export interface Checkpoint {
  time: string;
  label: string;
  /** Minutes from the clock to the checkpoint. */
  minutes: number;
}

/** The next checkpoint after `hour:minute` New York, or null once the 11:00 window has closed. */
export function nextCheckpoint(hour: number, minute: number): Checkpoint | null {
  const now = hour * 60 + minute;
  for (const c of CHECKPOINTS) {
    const [h, m] = c.time.split(':').map(Number) as [number, number];
    const at = h * 60 + m;
    if (at > now) return { time: c.time, label: c.label, minutes: at - now };
  }
  return null;
}

/** "Next 10:00, new 4H and 1H candles, in 10 min"; after 11:00 "His window closed at 11:00". */
export function checkpointText(hour: number, minute: number): string {
  const next = nextCheckpoint(hour, minute);
  if (!next) return 'His window closed at 11:00';
  const wait = next.minutes < 60 ? `${next.minutes} min` : `${Math.floor(next.minutes / 60)} h ${String(next.minutes % 60).padStart(2, '0')} min`;
  return `Next ${next.time}, ${next.label}, in ${wait}`;
}

/** A step's price as the trader reads it ("24,958.25"), or "" when the step has none. */
export function stepPrice(step: Pick<Step, 'price'>): string {
  return step.price === null ? '' : formatPrice(step.price, priceDecimals([step.price]));
}

/** "+0.19R", "−1.00R" (a true minus sign). */
export function formatR(r: number): string {
  const v = Math.abs(r) < 0.005 ? 0 : r;
  return `${v < 0 ? '−' : '+'}${Math.abs(v).toFixed(2)}R`;
}

export interface PlanWords {
  /** "Planned short", "Short". */
  title: string;
  /** "Planned" or "Triggered 08:20". */
  state: string;
  /** "Target reached 09:40", "Stopped 09:15", or "" while open. */
  outcome: string;
  /** Last close and where it stands, only once triggered: "24,713.25", "+0.19R". */
  last: { price: string; r: string } | null;
  /** Triggered: "Actionable", "Late · 5 bars", "Played out"; "" otherwise. */
  stage: string;
  /** Whether that stage says the entry is gone or stale (late, played out). */
  stageAlert: boolean;
  /** "Stop 6% of ADR · costs 0.05R mini, 0.11R micro", or "". */
  cost: string;
  /** "1 micro risks $96 · 1 mini $960", or "". */
  size: string;
  /** What the backtest measured for this setup, or null (not shown once the outcome is in). */
  evidence: { label: string; line: string; exits: string; source: string; tone: string } | null;
}

/** small_stop warns; best_measured is the one setup that passed a test (weak); the rest are plain. */
const EVIDENCE_TONES: Record<string, string> = { small_stop: 'watch', best_measured: 'reward', no_edge: 'muted', untested: 'muted' };

const STAGE_WORDS: Record<string, string> = { actionable: 'Actionable', late: 'Late', played_out: 'Played out' };

export function planWords(plan: Plan): PlanWords {
  const at = (iso: string | null) => (iso ? (wallClock(iso)?.time ?? '') : '');
  const triggered = plan.state === 'triggered';
  const outcome = plan.outcome === 'target_reached' ? 'Target reached' : plan.outcome === 'stopped' ? 'Stopped' : '';
  const decimals = priceDecimals([plan.entry, plan.stop, plan.target]);
  return {
    title: sentenceCase(plainText(plan.title)),
    state: triggered ? `Triggered ${at(plan.since)}`.trim() : 'Planned',
    outcome: outcome ? `${outcome} ${at(plan.outcome_at)}`.trim() : '',
    last: triggered && plan.last !== null ? { price: formatPrice(plan.last, decimals), r: plan.r_now === null ? '' : formatR(plan.r_now) } : null,
    stage: stageWords(plan),
    stageAlert: plan.stage_label === 'late' || plan.stage_label === 'played_out',
    cost: plan.cost_note,
    size: plan.size_note,
    evidence:
      plan.evidence && plan.outcome === 'open'
        ? {
            label: plan.evidence.label,
            line: plainText(plan.evidence.line),
            exits: plainText(plan.evidence.exits),
            source: plan.evidence.source,
            tone: EVIDENCE_TONES[plan.evidence.grade] ?? 'muted',
          }
        : null,
  };
}

function stageWords(plan: Plan): string {
  const word = STAGE_WORDS[plan.stage_label] ?? '';
  if (!word) return '';
  const age = plan.age_bars === null ? '' : ` · ${plan.age_bars} ${plan.age_bars === 1 ? 'bar' : 'bars'}`;
  return plan.stage_label === 'played_out' ? word : `${word}${age}`;
}

export interface SideChoice {
  value: Side;
  label: string;
  /** From the core's state, never from the click: the control is not optimistic. */
  pressed: boolean;
}

export function sideChoices(options: Pick<Options, 'sides' | 'side_labels'> | null, state: Pick<ServerState, 'side'> | null): SideChoice[] {
  const sides = options?.sides.length ? options.sides : DEFAULT_SIDES;
  return sides.map((value) => ({
    value,
    label: options?.side_labels[value] || DEFAULT_SIDE_LABELS[value],
    pressed: state !== null && state.side === value,
  }));
}

/** The core reads the same moment again by itself after a new side; no `check` follows. */
export function setSide(side: Side): ClientFrame {
  return { type: 'set', side };
}
