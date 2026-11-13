// The plan's risk / reward tool, as the entry chart draws it. Pure decisions only
// (words, styles, what fits); MarksPrimitive does the drawing.
import { plainText, titleText } from '../format';
import type { Tool, ToolLine, ToolRole } from '../wire';

/** Zone fill opacity. contrast.test.ts holds captions and candles over it to AA. */
export const ZONE_ALPHA = 0.12;

/** Server words for a canvas label: no " · " separators, single spaces, "HIT" in lower case. */
export function toolText(s: string): string {
  return plainText(s)
    .replace(/\s{2,}/g, ' ')
    .replace(/\bHIT\b/g, 'hit')
    .trim();
}

/** "PLANNED  REWARD  2.00R" -> "Planned reward 2.00R". */
export function captionText(s: string): string {
  return titleText(plainText(s));
}

export interface ToolLabelOptions {
  /** The "level names" display option. Off: the bare role word only. */
  named: boolean;
  /** Whether this line's zone shows its caption. When it does not, stop and target use their worded names. */
  captionShown: boolean;
}

/**
 * The label texts a tool line may take, fullest first. The chart takes the first that
 * fits; the last is always the bare role word ("Entry", "Stop", "Target").
 * With `entry_note` the entry's labels carry the next step's words, because the core
 * sends no separate "next" line when the level the next step waits on is this entry.
 */
export function toolLineLabels(tool: Pick<Tool, 'entry_note'>, line: ToolLine, opts: ToolLabelOptions): string[] {
  const zoneLine = line.role === 'stop' || line.role === 'target';
  const source = !opts.named ? line.names.slice(-1) : zoneLine && !opts.captionShown ? line.names_worded : line.names;
  const names = dedupe(source.map(toolText).filter(Boolean));
  const bare = toolText(line.names[line.names.length - 1] ?? line.role);
  if (line.role === 'entry' && tool.entry_note.trim()) {
    const note = toolText(tool.entry_note);
    return dedupe([...names.map((n) => `${n}, ${lowerFirst(note)}`), note, bare]);
  }
  return names.length ? names : [bare];
}

/** The fullest label that `fits`; the bare word when none does. */
export function chooseLabel(options: readonly string[], fits: (text: string) => boolean): string {
  for (const o of options) if (fits(o)) return o;
  return options[options.length - 1] ?? '';
}

/**
 * Whether a zone has room for its caption: tall enough for the caption to sit in its
 * middle clear of a line label on each edge, and wide enough for the words.
 */
export function captionFits(zone: { height: number; width: number }, text: { width: number; height: number }, pad = 6): boolean {
  return zone.height >= text.height * 3 + pad * 2 && zone.width >= text.width + pad * 2;
}

export interface ToolLineStyle {
  /** Planned (nothing has triggered) or stale: the tool is drawn dashed. */
  dashed: boolean;
  /** The entry is the level the next step waits on: drawn in the "next" style. */
  next: boolean;
}

export function toolLineStyle(tool: Pick<Tool, 'planned' | 'entry_note'>, role: ToolRole, stale: boolean): ToolLineStyle {
  return { dashed: tool.planned || stale, next: role === 'entry' && tool.entry_note.trim() !== '' };
}

/** The price the outcome diamond sits on, or null while the trade is open. */
export function outcomePrice(tool: Pick<Tool, 'outcome' | 'target' | 'stop'>): number | null {
  if (tool.outcome === 'target_reached') return tool.target;
  if (tool.outcome === 'stopped') return tool.stop;
  return null;
}

/** Prices the tool occupies, for the chart's price scale. */
export function toolPrices(tool: Tool): number[] {
  return [tool.entry, tool.stop, tool.target, tool.risk_zone.top, tool.risk_zone.bottom, tool.reward_zone.top, tool.reward_zone.bottom];
}

function lowerFirst(s: string): string {
  return s.charAt(0).toLowerCase() + s.slice(1);
}

function dedupe(list: string[]): string[] {
  return [...new Set(list)];
}
