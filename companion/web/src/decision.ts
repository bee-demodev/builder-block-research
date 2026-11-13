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
  /** "What has to happen": the step list. */
  steps: boolean;
  /** The single "Waiting for" block, the fallback when the core sends no steps. */
  waiting: boolean;
  /** The plan block; it replaces the levels rows. */
  plan: boolean;
  levels: boolean;
}

export function sections(view: Pick<VerdictView, 'steps' | 'waiting_for' | 'plan' | 'has_levels' | 'levels'>): Sections {
  const steps = view.steps.length > 0;
  const plan = view.plan !== null;
  return {
    steps,
    waiting: !steps && view.waiting_for.trim() !== '',
    plan,
    levels: !plan && view.has_levels && view.levels.length > 0,
  };
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
}

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
  };
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
