// Display formatting. All time handling reads the wall clock straight out of the
// ISO string (which carries the New York offset), so the browser's own time zone
// never shifts what the trader sees.

/** "WATCH" -> "Watch", "TRADE LONG" -> "Trade long", "DON'T TRADE" -> "Don't trade". */
export function sentenceCase(text: string): string {
  const lower = text.trim().toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

/**
 * Server sentences join clauses with " · " or " — ". On screen those read as a comma.
 * Only a separator with spaces on both sides is replaced, so a price range such as
 * "24,784.75–24,838.00" or a time is never touched.
 */
export function plainText(text: string): string {
  return text.replace(/\s+[·—]\s+/g, ', ').trim();
}

/** Placeholder values the core sends for "nothing here". */
const EMPTY_VALUES = new Set(['', '—', '-', 'none', 'n/a']);
const isEmptyValue = (s: string) => EMPTY_VALUES.has(s.trim().toLowerCase());

/**
 * A heading in sentence case that keeps codes with digits as sent:
 * "CONTINUATION C2" -> "Continuation C2", "SHARED" -> "Shared".
 */
export function titleText(text: string): string {
  const words = text.trim().split(/\s+/).filter(Boolean);
  const out = words.map((w) => (/\d/.test(w) ? w : w.toLowerCase())).join(' ');
  return out.charAt(0).toUpperCase() + out.slice(1);
}

/**
 * The line under the decision word, from the fields the core sends separately:
 * path "CONTINUATION", bias "BEARISH", stage "C4" -> "Continuation, bearish bias, stage C4".
 * Empty and placeholder fields are left out. The bias is named as the bias: on a
 * reversal it can differ from the reversal's direction (a bearish reversal forming
 * against a bias that still reads bullish), and a bare "Reversal, bullish" would read
 * as the reversal's direction. The stage stays a code: the core's stage codes are not
 * candle numbers, so they are not rewritten as one.
 */
export function pathLine(view: { path: string; bias: string; stage: string }): string {
  const parts: string[] = [];
  if (!isEmptyValue(view.path)) parts.push(plainText(view.path).toLowerCase());
  if (!isEmptyValue(view.bias)) parts.push(`${plainText(view.bias).toLowerCase()} bias`);
  if (!isEmptyValue(view.stage)) parts.push(`stage ${view.stage.trim()}`);
  const line = parts.join(', ');
  return line.charAt(0).toUpperCase() + line.slice(1);
}

/** The server separates status parts with " · ". We lay them out with spacing instead. */
export function splitStatus(text: string): string[] {
  return text
    .split('·')
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

/** What the top bar says for a status. Saved history with no text still says so. */
export function statusParts(status: { state: string; text: string }): string[] {
  const parts = splitStatus(status.text);
  if (parts.length > 0) return parts;
  if (status.state === 'history') return ['Saved history'];
  return [];
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as const;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] as const;

export interface WallClock {
  year: number;
  month: number; // 1-12
  day: number;
  hour: number;
  minute: number;
  /** "Thu 12 Nov 2026" */
  date: string;
  /** "10:35" */
  time: string;
  /** "2026-11-12T10:35", the value for <input type="datetime-local"> */
  local: string;
}

const ISO_WALL = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/;

export function wallClock(iso: string): WallClock | null {
  const m = ISO_WALL.exec(iso.trim());
  if (!m) return null;
  const [year, month, day, hour, minute] = m.slice(1, 6).map(Number) as [number, number, number, number, number];
  if (month < 1 || month > 12 || day < 1 || day > 31 || hour > 23 || minute > 59) return null;
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  const pad = (n: number) => String(n).padStart(2, '0');
  return {
    year,
    month,
    day,
    hour,
    minute,
    date: `${DAYS[weekday]} ${day} ${MONTHS[month - 1]} ${year}`,
    time: `${pad(hour)}:${pad(minute)}`,
    local: `${year}-${pad(month)}-${pad(day)}T${pad(hour)}:${pad(minute)}`,
  };
}

const priceFormatters = new Map<number, Intl.NumberFormat>();

export function formatPrice(value: number, decimals = 2): string {
  let f = priceFormatters.get(decimals);
  if (!f) {
    f = new Intl.NumberFormat('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    priceFormatters.set(decimals, f);
  }
  return f.format(value);
}

/** Decimal places needed to show every price in the series exactly (capped at 5). */
export function priceDecimals(values: readonly number[], min = 2): number {
  let best = min;
  for (const v of values) {
    let d = 0;
    while (d < 5 && Math.abs(v * 10 ** d - Math.round(v * 10 ** d)) > 1e-6) d++;
    if (d > best) best = d;
  }
  return best;
}

export function formatMs(ms: number | null): string {
  if (ms === null) return 'n/a';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

/** Axis labels from a candle's `t` (New York wall clock expressed as UTC seconds). */
export function axisLabel(t: number, kind: 'year' | 'month' | 'day' | 'time', intraday: boolean): string {
  const d = new Date(t * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  switch (kind) {
    case 'year':
      return String(d.getUTCFullYear());
    case 'month':
      return MONTHS[d.getUTCMonth()] ?? '';
    case 'day':
      return intraday ? `${DAYS[d.getUTCDay()]} ${d.getUTCDate()}` : `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
    case 'time':
      return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  }
}

/** Crosshair label: "Thu 12 Nov 10:35" intraday, "Thu 12 Nov 2026" daily and up. */
export function crosshairLabel(t: number, intraday: boolean): string {
  const d = new Date(t * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  const date = `${DAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
  return intraday ? `${date} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}` : `${date} ${d.getUTCFullYear()}`;
}
