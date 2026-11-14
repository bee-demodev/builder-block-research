// Display options: per device, kept in localStorage, never sent to the core.
// The core's tool says `box` and `named` are display options a client applies itself;
// these are those, plus text size and the direction colours.

export type TextSize = 'normal' | 'large' | 'larger';
export type Scheme = 'grey' | 'green-red' | 'green-black' | 'blue-orange' | 'mono';

export interface Overlays {
  /** Names on level lines. Off: trade lines keep their bare role word. */
  levelNames: boolean;
  /** Zones the core marks (points of interest, runs). */
  zones: boolean;
  /** Words beside marker arrows. */
  markerLabels: boolean;
  /** The risk / reward box on the entry chart (its zones and captions; its lines always stay). */
  riskReward: boolean;
  /** Intraday reference levels (Asia and London high / low, midnight and 09:30 opens, PDH / PDL). Off by default. */
  sessionLevels: boolean;
}

export interface DisplayOptions {
  textSize: TextSize;
  scheme: Scheme;
  overlays: Overlays;
}

export const TEXT_SIZES: readonly { value: TextSize; label: string; scale: number }[] = [
  { value: 'normal', label: 'Normal', scale: 1 },
  { value: 'large', label: 'Large', scale: 1.25 },
  { value: 'larger', label: 'Larger', scale: 1.5 },
];

export const SCHEMES: readonly { value: Scheme; label: string; hint: string }[] = [
  { value: 'grey', label: 'Grey candles', hint: 'Colour only where it means something' },
  { value: 'green-red', label: 'Green / red', hint: 'Up and long green, down and short red' },
  { value: 'green-black', label: 'Green / black', hint: 'Up green, down black; the stop stays red' },
  { value: 'blue-orange', label: 'Blue / orange', hint: 'Colour-blind safe' },
  { value: 'mono', label: 'Monochrome', hint: 'Hollow up, filled down, sides in words' },
];

export const OVERLAYS: readonly { key: keyof Overlays; label: string }[] = [
  { key: 'levelNames', label: 'Level names' },
  { key: 'zones', label: 'Zones' },
  { key: 'markerLabels', label: 'Marker labels' },
  { key: 'riskReward', label: 'Risk / reward box' },
  { key: 'sessionLevels', label: 'Session levels' },
];

export const DEFAULT_DISPLAY: DisplayOptions = {
  textSize: 'normal',
  scheme: 'grey',
  overlays: { levelNames: true, zones: true, markerLabels: true, riskReward: true, sessionLevels: false },
};

export const DISPLAY_KEY = 'companion.display';

/** The marks a chart draws with these overlays: the session levels layer only when it is on. */
export function layerMarks<T extends { role: string }>(marks: readonly T[], overlays: Overlays): T[] {
  return overlays.sessionLevels ? [...marks] : marks.filter((m) => m.role !== 'session');
}

export function textScale(size: TextSize): number {
  return TEXT_SIZES.find((s) => s.value === size)?.scale ?? 1;
}

/** One step larger (+1) or smaller (-1), stopping at the ends. */
export function stepTextSize(size: TextSize, by: 1 | -1): TextSize {
  const i = TEXT_SIZES.findIndex((s) => s.value === size);
  const next = Math.min(TEXT_SIZES.length - 1, Math.max(0, (i < 0 ? 0 : i) + by));
  return TEXT_SIZES[next]!.value;
}

/** Whatever was stored, as valid options: unknown or broken values fall back to the defaults one by one. */
export function parseDisplay(raw: string | null): DisplayOptions {
  if (!raw) return cloneDefaults();
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return cloneDefaults();
  }
  if (typeof data !== 'object' || data === null) return cloneDefaults();
  const d = data as Record<string, unknown>;
  const overlays = (typeof d.overlays === 'object' && d.overlays !== null ? d.overlays : {}) as Record<string, unknown>;
  const flag = (k: keyof Overlays) => (typeof overlays[k] === 'boolean' ? (overlays[k] as boolean) : DEFAULT_DISPLAY.overlays[k]);
  return {
    textSize: TEXT_SIZES.some((s) => s.value === d.textSize) ? (d.textSize as TextSize) : DEFAULT_DISPLAY.textSize,
    scheme: SCHEMES.some((s) => s.value === d.scheme) ? (d.scheme as Scheme) : DEFAULT_DISPLAY.scheme,
    overlays: {
      levelNames: flag('levelNames'),
      zones: flag('zones'),
      markerLabels: flag('markerLabels'),
      riskReward: flag('riskReward'),
      sessionLevels: flag('sessionLevels'),
    },
  };
}

function cloneDefaults(): DisplayOptions {
  return { ...DEFAULT_DISPLAY, overlays: { ...DEFAULT_DISPLAY.overlays } };
}

type Storage = Pick<globalThis.Storage, 'getItem' | 'setItem' | 'removeItem'>;

export function loadDisplay(storage: Storage | null): DisplayOptions {
  try {
    return parseDisplay(storage?.getItem(DISPLAY_KEY) ?? null);
  } catch {
    return cloneDefaults();
  }
}

/** Defaults are stored as nothing, so a reset leaves no trace and later default changes reach this device. */
export function saveDisplay(storage: Storage | null, options: DisplayOptions): void {
  try {
    if (isDefault(options)) storage?.removeItem(DISPLAY_KEY);
    else storage?.setItem(DISPLAY_KEY, JSON.stringify(options));
  } catch {
    /* storage unavailable: the choice lasts for this session only */
  }
}

export function isDefault(o: DisplayOptions): boolean {
  const d = DEFAULT_DISPLAY;
  return o.textSize === d.textSize && o.scheme === d.scheme && OVERLAYS.every(({ key }) => o.overlays[key] === d.overlays[key]);
}
