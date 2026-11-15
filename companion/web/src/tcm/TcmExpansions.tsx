// The TCM Expansions section: an expansion's range (high, low, EQ, 50% of the last
// candle, CSD) and the video's decision points, read candle by candle.
//  - Live: the companion core's own charts (TradingView live, or saved history). The
//    symbol and stack controls drive the same core as the TTrades tab. With no candle
//    picked, the tab follows the newest range still in play; a click pins one.
//  - Practice: lessons redrawn from the video with invented prices.
// Shadow (off by default): the two ways the next candle can go at the decision pending
// now, A (on plan) or B (not), as a pale ghost candle in a "What if" column, captioned
// with the rules' own read of it.
import { ArrowCounterClockwiseIcon, CaretLeftIcon, CaretRightIcon, CursorClickIcon, MagnifyingGlassIcon, PushPinIcon, WifiSlashIcon } from '@phosphor-icons/react';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { readPalette } from '../chart/palette';
import { LiveStatus } from '../components/TopBar';
import { Select, StatusIcon, toneClass } from '../components/ui';
import type { Scheme } from '../display';
import { formatPrice, priceDecimals } from '../format';
import type { ResolvedTheme } from '../hooks';
import { chartFor, type Model } from '../store';
import type { Semantic } from '../tones';
import type { ClientFrame } from '../wire';
import { MIN_RUN, latestRange, pickRange, readRange, type Bar, type ExpansionDir, type Range, type RangePick, type Reading, type StepStatus } from './expansion';
import { EXTEND_BARS, RangeChart, type ExtendMode } from './RangeChart';
import { LESSONS, type Lesson, type LessonMark } from './lessons';
import { SHADOW_OFF_TEXT, SHADOW_SEMANTIC as TONE, consequence, explainShadow, shadowTitle, type Shadow, type ShadowBranch } from './shadow';

interface Props {
  model: Model;
  send: (frame: ClientFrame) => void;
  theme: ResolvedTheme;
  scheme: Scheme;
  /** Text size (Display menu): the chart's canvas labels follow it. */
  scale: number;
  /** The section tabs, shown in this section's top bar. */
  tabs: ReactNode;
  /** Shown at the right of the footer (the theme toggle). */
  footerEnd: ReactNode;
}

type Mode = 'live' | 'practice';
type ShadowMode = 'off' | 'A' | 'B';
type Role = 'entry' | 'setup' | 'bias';

const ROLES: readonly { role: Role; label: string }[] = [
  { role: 'entry', label: 'Entry' },
  { role: 'setup', label: 'Setup' },
  { role: 'bias', label: 'Bias' },
];
const DATA_LABELS: Record<string, string> = { live: 'Live', history: 'Saved history' };
const LESSON_LABELS = LESSONS.map((s, i) => `${i + 1}. ${s.title}`);
const NO_MARKS: readonly LessonMark[] = [];

/** The expansion a lesson reads at this candle: its first, or a later one it has moved on to. */
function lessonAnchor(lesson: Lesson, cursor: number): number {
  return [...(lesson.next ?? [])].filter((n) => n.at <= cursor).pop()?.anchor ?? lesson.anchor;
}

/** Where a lesson's drawing first appears. */
function markAt(m: LessonMark): number {
  return m.at ?? (m.kind === 'time' || m.kind === 'tag' ? m.index : m.from);
}

/** The candle the trader picked (by open time, so new candles do not move it), and a range set by hand. */
interface Pick {
  source: string;
  t: number;
  manual: { start: number; end: number; dir: ExpansionDir } | null;
}

/** What the video says, in the order it builds up. Shown under "Rules from the video". */
const RULES: readonly [string, string, string][] = [
  ['05:52', 'Expansion', 'Two or more candles of one colour, each closing beyond the one before. One big candle is not an expansion.'],
  ['06:23', 'Range', 'The first candle that does not close beyond ends it. Range high, range low and EQ (the 50% line) are now key levels.'],
  ['07:25', 'Size', 'Is the range big enough for the trade you want? A tight range demands a perfect entry and may never reach its other side.'],
  ['42:50', 'OLR', 'A run past the range low (high, for shorts) that closes back inside: the opposing liquidity run. It makes the turn stronger; it is not required.'],
  ['09:32', '50%', 'A candle the other way closing past 50% of the last expansion candle: enough to participate, not yet strength.'],
  ['55:51', 'CSD', 'A close past the open of the last expansion candle. When CSD takes several candles, he watches the open of the second one (59:44).'],
  ['10:41', 'Wick', 'A big wick on the CSD candle: the next candle usually trades back past its close, so get in there; the bigger the wick, the deeper. No wick: no deep pullback, do not wait for one.'],
  ['17:22', 'Plan versus reality', 'If price leaves without the pullback, do not chase it: the deep retracement is not done yet.'],
  ['13:48', 'EQ', 'Hold only after a close past EQ. Until then it is a scalp: take it, then cut, partial or break even at EQ.'],
  ['93:36', 'Inside the range', 'Do not buy above EQ or sell below it. If you insist, only in an FVG after the high (or low) is taken.'],
  ['49:53', 'Targets', 'EQ, then the range high. Failure swings with an FVG through them are the next targets.'],
  ['43:26', 'Time', 'Time raises the odds; it does not change how price delivers. At 9:55 the new hour often takes the previous hour first (92:18).'],
  ['103:29', 'The last seconds', 'Watch how a candle closes, not how it looks mid-candle: a push in its last 10 to 20 seconds can trap traders on the wrong side.'],
];

const STEP_TONE: Record<StepStatus, Semantic> = { pass: 'bull', fail: 'bear', waiting: 'watch', na: 'muted' };
const STEP_ICON = { pass: 'pass', fail: 'fail', waiting: 'waiting', na: 'not_applicable' } as const;
const STEP_WORD: Record<StepStatus, string> = { pass: 'Done', fail: 'Failed', waiting: 'Waiting', na: 'Not in play' };

// ---------- small persisted settings ----------

function useStored<T extends string | number>(key: string, fallback: T, valid: (v: string) => boolean): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const v = localStorage.getItem(key);
      if (v !== null && valid(v)) return (typeof fallback === 'number' ? Number(v) : v) as T;
    } catch {
      // private mode
    }
    return fallback;
  });
  const set = useCallback(
    (v: T) => {
      setValue(v);
      try {
        localStorage.setItem(key, String(v));
      } catch {
        // private mode: the choice lasts this session only
      }
    },
    [key],
  );
  return [value, set];
}

function barNamer(minutes: number) {
  return (bar: Bar): string => {
    const d = new Date(bar.t * 1000);
    if (minutes >= 1440) return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
    return `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
  };
}

/** The last bar opening at or before `t` (0 when none does). */
function indexAt(bars: readonly Bar[], t: number): number {
  let lo = 0;
  let hi = bars.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (bars[mid]!.t <= t) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

export function TcmExpansions({ model, send, theme, scheme, scale, tabs, footerEnd }: Props) {
  const [mode, setMode] = useStored<Mode>('companion.tcm.mode', 'live', (v) => v === 'live' || v === 'practice');
  const [role, setRole] = useStored<Role>('companion.tcm.role', 'entry', (v) => ROLES.some((r) => r.role === v));
  const [lessonKey, setLessonKey] = useStored<string>('companion.tcm.lesson', LESSONS[0]!.key, (v) => LESSONS.some((s) => s.key === v));
  const [minSizeSetting, setMinSize] = useStored<number>('companion.tcm.minSize', 30, (v) => Number(v) > 0);
  // Line labels name their level only ("EQ", "CSD"); the price axis and the panel carry the numbers.
  const [pricesOn, setPricesOn] = useStored<string>('companion.tcm.prices', 'off', (v) => v === 'on' || v === 'off');
  // How far boxes and lines reach right, as TradingView's "extend": a few candles past the last one by default.
  const [extend, setExtend] = useStored<ExtendMode>('companion.tcm.extend', 'bars', (v) => v === 'candle' || v === 'bars' || v === 'edge');
  const [shadowMode, setShadowMode] = useState<ShadowMode>('off');

  const practice = mode === 'practice';
  const lessonMin = practice ? LESSONS.find((x) => x.key === lessonKey)?.minSize : undefined;
  // a lesson drawn on a 1-minute or daily chart brings its own minimum; the setting applies everywhere else
  const minSize = lessonMin ?? minSizeSetting;
  const lesson = practice ? (LESSONS.find((s) => s.key === lessonKey) ?? LESSONS[0]!) : null;
  const server = model.server;
  const options = model.options;
  const connected = model.link === 'open' && server !== null && options !== null;
  const liveChart = practice ? undefined : chartFor(model.view, role);
  const liveCandles = liveChart?.candles;
  const liveBars = useMemo<Bar[]>(
    () => (liveCandles ?? []).filter((c) => !c.forming).map((c) => ({ t: c.t, open: c.open, high: c.high, low: c.low, close: c.close })),
    [liveCandles],
  );
  const bars = lesson ? lesson.bars : liveBars;
  const source = lesson ? `lesson:${lesson.key}` : `live:${server?.symbol ?? ''}:${server?.stack ?? ''}:${role}`;
  const minutes = lesson ? lesson.minutes : (liveChart?.minutes ?? 5);
  const timeframe = lesson ? lesson.timeframe : (liveChart?.timeframe ?? '');
  const decimals = useMemo(() => (lesson ? 0 : priceDecimals(bars.slice(-200).flatMap((b) => [b.open, b.close]))), [lesson, bars]);

  // Replay position, by candle time. None: a lesson opens on its start, live follows the latest closed candle.
  const [step, setStep] = useState<{ source: string; t: number } | null>(null);
  const last = bars.length - 1;
  const stepped = step?.source === source ? step.t : null;
  const cursor = last < 0 ? -1 : stepped !== null ? indexAt(bars, stepped) : lesson ? lesson.start : last;
  const following = !practice && stepped === null;

  const [pick, setPick] = useState<Pick | null>(null);
  const pinned = pick?.source === source ? pick : null;
  const auto = !practice && pinned === null;

  // How the range is picked (pickRange in expansion.ts): the same function reads the shadow's branches,
  // so a branch always describes the range this tab would show once that candle printed.
  const rangePick = useMemo<RangePick | null>(() => {
    if (lesson && !pinned) return { kind: 'anchor', at: lessonAnchor(lesson, cursor) };
    if (!pinned) return { kind: 'latest', minSize }; // live, nothing pinned: the newest range in play
    if (pinned.manual) {
      const start = bars.findIndex((b) => b.t === pinned.manual!.start);
      const end = bars.findIndex((b) => b.t === pinned.manual!.end);
      return start >= 0 && end >= 0 ? { kind: 'manual', start, end, dir: pinned.manual.dir } : null;
    }
    const at = bars.findIndex((b) => b.t === pinned.t);
    return at >= 0 ? { kind: 'anchor', at } : null;
  }, [bars, lesson, pinned, minSize, cursor]);
  const range = useMemo<Range | null>(() => (cursor >= 0 && rangePick ? pickRange(bars, cursor, rangePick) : null), [bars, cursor, rangePick]);

  const readOpts = useMemo(() => ({ minSize, decimals, barName: barNamer(minutes), manual: !!pinned?.manual }), [minSize, decimals, minutes, pinned]);
  const reading = useMemo<Reading | null>(() => (range ? readRange(bars, range, cursor, readOpts) : null), [range, bars, cursor, readOpts]);
  const explained = useMemo(
    () => (range && rangePick && cursor >= 0 ? explainShadow(bars, range, cursor, readOpts, rangePick) : null),
    [range, rangePick, bars, cursor, readOpts],
  );
  const shadow: Shadow | null = explained?.shadow ?? null;
  // Why the switch is off, when it is (tooltip and screen readers).
  const shadowOff = SHADOW_OFF_TEXT[explained?.off ?? 'nothing'];
  const branch: ShadowBranch | null = shadow && shadowMode !== 'off' ? (shadowMode === 'A' ? shadow.a : shadow.b) : null;
  const ghosts = useMemo<Bar[]>(() => (shadow && branch ? [shadow.a.candle, shadow.b.candle] : []), [shadow, branch]);

  const goTo = useCallback(
    (i: number) => {
      const target = Math.max(Math.min(MIN_RUN, last), Math.min(last, i));
      if (!practice && target >= last) setStep(null);
      else if (bars[target]) setStep({ source, t: bars[target]!.t });
    },
    [last, practice, bars, source],
  );
  const stepBy = useCallback((d: number) => goTo(cursor + d), [goTo, cursor]);
  // Nothing pending: the switch goes back to Off, so no hidden choice pops up later.
  useEffect(() => {
    if (!shadow) setShadowMode('off');
  }, [shadow]);
  // S does nothing while the switch is disabled.
  const cycleShadow = useCallback(() => {
    if (shadow) setShadowMode((m) => (m === 'off' ? 'A' : m === 'A' ? 'B' : 'off'));
  }, [shadow]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.ctrlKey || e.metaKey || e.defaultPrevented) return;
      const el = e.target as HTMLElement | null;
      if (el && el.closest('input, select, textarea, [contenteditable="true"], [role="dialog"]')) return;
      if (e.key === 'ArrowLeft') stepBy(-1);
      else if (e.key === 'ArrowRight') stepBy(1);
      else if (e.key === 'Home' && lesson) goTo(lesson.start);
      else if (e.key === 'End') goTo(last);
      else if (e.key.toLowerCase() === 's') cycleShadow();
      else return;
      e.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [stepBy, goTo, lesson, last, cycleShadow]);

  const onPick = useCallback((i: number) => bars[i] && setPick({ source, t: bars[i]!.t, manual: null }), [bars, source]);
  const findLatest = () => {
    const r = pickRange(bars, cursor, { kind: 'latest', minSize }) ?? latestRange(bars, cursor);
    if (r) setPick({ source, t: bars[r.end]!.t, manual: null });
  };
  const nudge = (edge: 'start' | 'end', d: number) => {
    if (!range) return;
    let { start, end } = range;
    if (edge === 'start') start = Math.max(0, Math.min(end - 1, start + d));
    else end = Math.max(start + 1, Math.min(cursor, end + d));
    setPick({ source, t: bars[end]!.t, manual: { start: bars[start]!.t, end: bars[end]!.t, dir: range.dir } });
  };

  const said = lesson ? [...lesson.notes].filter((n) => n.at <= cursor).pop() ?? null : null;
  const marks = useMemo(() => (lesson?.marks ? lesson.marks.filter((m) => markAt(m) <= cursor) : NO_MARKS), [lesson, cursor]);

  const [hover, setHover] = useState<number | null>(null);
  const shown = bars[hover ?? cursor] ?? null;

  return (
    <>
      <header className="topbar">
        <div className="wordmark">Companion</div>
        {tabs}
        <div className="topbar-group">
          <Segmented
            label="Mode"
            value={mode}
            options={[
              { value: 'live', label: 'Live' },
              { value: 'practice', label: 'Practice' },
            ]}
            onChange={(v) => setMode(v as Mode)}
          />
          {practice ? (
            <Select
              label="Lesson"
              value={LESSON_LABELS[LESSONS.indexOf(lesson!)] ?? ''}
              options={LESSON_LABELS}
              onChange={(label) => {
                const s = LESSONS[LESSON_LABELS.indexOf(label)];
                if (s) setLessonKey(s.key);
              }}
            />
          ) : (
            <>
              <Select label="Symbol" value={server?.symbol ?? ''} options={options?.symbols ?? []} disabled={!connected} onChange={(symbol) => send({ type: 'set', symbol })} />
              <Select
                label="Stack"
                value={server?.stack ?? ''}
                options={options?.stacks ?? []}
                disabled={!connected}
                hint={options?.stack_notes[server?.stack ?? '']}
                onChange={(stack) => send({ type: 'set', stack })}
              />
              <Select
                label="Chart"
                value={chartLabel(role, model)}
                options={ROLES.map((r) => chartLabel(r.role, model))}
                onChange={(label) => {
                  const r = ROLES.find((x) => chartLabel(x.role, model) === label);
                  if (r) setRole(r.role);
                }}
              />
            </>
          )}
        </div>
        <div className="topbar-right">
          {!practice && <LiveStatus model={model} />}
          <div className="timectl" role="group" aria-label="Replay">
            <button type="button" className="btn btn-icon" aria-label="Back one candle" aria-keyshortcuts="ArrowLeft" disabled={cursor <= MIN_RUN} onClick={() => stepBy(-1)}>
              <CaretLeftIcon size={14} aria-hidden />
            </button>
            <span className="tcm-cursor mono" aria-live="polite">
              {bars.length ? `${cursor + 1} / ${bars.length}` : '-'}
            </span>
            <button type="button" className="btn btn-icon" aria-label="Forward one candle" aria-keyshortcuts="ArrowRight" disabled={cursor >= last} onClick={() => stepBy(1)}>
              <CaretRightIcon size={14} aria-hidden />
            </button>
            <button type="button" className="btn" disabled={following || (practice && cursor >= last)} aria-pressed={following} onClick={() => goTo(last)} aria-keyshortcuts="End">
              {practice ? 'Show all' : 'Latest'}
            </button>
            {lesson && (
              <button type="button" className="btn btn-icon" aria-label="Restart the lesson" title="Restart" aria-keyshortcuts="Home" onClick={() => goTo(lesson.start)}>
                <ArrowCounterClockwiseIcon size={14} aria-hidden />
              </button>
            )}
          </div>
        </div>
      </header>
      <div className="banners" />
      <main className="layout">
        <aside className="panel tcm-panel" aria-label="Range read">
          <div className="panel-scroll">
            {lesson && (
              // Collapsed to its title: the narration below carries the lesson; the summary is a click away.
              <details key={lesson.key} className="tcm-note">
                <summary>
                  <CaretRightIcon size={12} aria-hidden className="tcm-caret" />
                  <span className="tcm-note-title">{lesson.title}</span>
                  <span className="tcm-note-ref mono">{lesson.ref}</span>
                </summary>
                <p>{lesson.note}</p>
                <p className="tcm-note-meta">Practice chart, invented prices.</p>
              </details>
            )}
            {lesson && (
              <div className="tcm-said" aria-live="polite">
                <p className="tcm-said-label">At this candle</p>
                <p>{said ? said.text : 'Step forward with the arrow keys: the lesson explains each candle as it prints.'}</p>
              </div>
            )}
            {!practice && range && (
              <p className="tcm-follow">
                {auto ? (
                  <>Following the newest range in play. Click a candle to pin one.</>
                ) : (
                  <>
                    <PushPinIcon size={13} aria-hidden /> Pinned.{' '}
                    <button type="button" className="tcm-link" onClick={() => setPick(null)}>
                      Follow the newest instead
                    </button>
                  </>
                )}
              </p>
            )}
            {reading ? (
              <ReadingView key={`${reading.range.start}-${reading.range.end}-${reading.range.dir}`} reading={reading} decimals={decimals} onJump={goTo} />
            ) : (
              <div className="tcm-empty">
                <CursorClickIcon size={18} aria-hidden />
                <p>
                  {pinned && range === null
                    ? 'That candle is not part of an expansion (two or more candles closing beyond each other). Pick another.'
                    : bars.length
                      ? 'No expansion in play here yet. Click a candle of one on the chart.'
                      : 'No chart yet.'}
                </p>
              </div>
            )}
            <div className="tcm-tools">
              <button type="button" className="btn btn-small" onClick={findLatest} disabled={bars.length < 3}>
                <MagnifyingGlassIcon size={14} aria-hidden />
                Find latest expansion
              </button>
              {range && (
                <div className="tcm-nudge" role="group" aria-label="Adjust the range">
                  <span className="tcm-nudge-label">Start</span>
                  <button type="button" className="btn btn-icon btn-small" aria-label="Range starts one candle earlier" onClick={() => nudge('start', -1)}>
                    <CaretLeftIcon size={12} aria-hidden />
                  </button>
                  <button type="button" className="btn btn-icon btn-small" aria-label="Range starts one candle later" onClick={() => nudge('start', 1)}>
                    <CaretRightIcon size={12} aria-hidden />
                  </button>
                  <span className="tcm-nudge-label">End</span>
                  <button type="button" className="btn btn-icon btn-small" aria-label="Range ends one candle earlier" onClick={() => nudge('end', -1)}>
                    <CaretLeftIcon size={12} aria-hidden />
                  </button>
                  <button type="button" className="btn btn-icon btn-small" aria-label="Range ends one candle later" onClick={() => nudge('end', 1)}>
                    <CaretRightIcon size={12} aria-hidden />
                  </button>
                  {pinned?.manual && (
                    <button type="button" className="btn btn-small btn-ghost" onClick={() => setPick({ ...pinned, manual: null })}>
                      Use the rule
                    </button>
                  )}
                </div>
              )}
            </div>
            <section className="tcm-settings" aria-label="Settings">
              <h2 className="tcm-settings-title">Settings</h2>
              <label className="tcm-setting">
                <span>Lines &amp; boxes</span>
                <select value={extend} onChange={(e) => setExtend(e.target.value as ExtendMode)}>
                  <option value="candle">To the last candle</option>
                  <option value="bars">{EXTEND_BARS} candles past</option>
                  <option value="edge">To the right edge</option>
                </select>
              </label>
              <label className="tcm-setting tcm-setting-check">
                <span>Prices on chart labels</span>
                <input type="checkbox" checked={pricesOn === 'on'} onChange={(e) => setPricesOn(e.target.checked ? 'on' : 'off')} />
              </label>
              <label className="tcm-setting">
                <span>Min range (points)</span>
                <input
                  className="mono"
                  type="number"
                  min={0}
                  step="any"
                  value={minSize}
                  disabled={lessonMin !== undefined}
                  title={lessonMin !== undefined ? 'This lesson sets its own minimum.' : undefined}
                  onChange={(e) => setMinSize(Math.max(0, Number(e.target.value) || 0))}
                />
              </label>
              {!practice && (
                <label className="tcm-setting">
                  <span>Data</span>
                  <select
                    value={server?.data ?? ''}
                    disabled={!connected}
                    onChange={(e) => {
                      send({ type: 'set', data: e.target.value });
                      setStep(null);
                    }}
                  >
                    {(options?.data ?? ['live', 'history']).map((d) => (
                      <option key={d} value={d}>
                        {DATA_LABELS[d] ?? d}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </section>
            <details className="tcm-rules">
              <summary>Rules from the video</summary>
              <ol>
                {RULES.map(([ref, name, text]) => (
                  <li key={name}>
                    <span className="tcm-ref mono">{ref}</span>
                    <p>
                      <strong>{name}.</strong> {text}
                    </p>
                  </li>
                ))}
              </ol>
            </details>
          </div>
        </aside>
        <section className="charts tcm-charts" aria-label="Range chart">
          <article className="pane" aria-label={`${timeframe} chart`}>
            <header className="pane-head">
              <span className="pane-tf mono">{timeframe || '-'}</span>
              <span className="pane-role">{lesson ? 'Practice' : liveChart ? `${server?.symbol ?? ''} ${ROLES.find((r) => r.role === role)!.label.toLowerCase()} chart` : 'No chart'}</span>
              {reading && (
                <span className={`pane-headline ${toneClass(reading.verdict.tone)}`}>
                  <span className="pane-headline-text">{reading.verdict.word}</span>
                </span>
              )}
              {shown && <Ohlc bar={shown} decimals={decimals} />}
              <ShadowSwitch shadow={shadow} value={shadowMode} onChange={setShadowMode} offReason={shadowOff} />
            </header>
            <ShadowCaption shadow={shadow} branch={branch} fallback={reading ? reading.verdict.detail : bars.length ? 'Click a candle of an expansion.' : ' '} />
            <div className="pane-body">
              {bars.length > 0 ? (
                <>
                  <TcmChart
                    bars={bars}
                    cursor={cursor}
                    decimals={decimals}
                    fitKey={source}
                    follow={following}
                    // while the expansion runs, "extends" is drawn against the range it would make
                    reading={branch && shadow?.decision === 'range' ? branch.after : reading}
                    shadow={branch}
                    ghosts={ghosts}
                    hypothetical={!!branch && shadow?.decision === 'range' && branch.key === 'B'}
                    marks={marks}
                    showPrices={pricesOn === 'on'}
                    extend={extend}
                    scale={scale}
                    theme={theme}
                    scheme={scheme}
                    onPick={onPick}
                    onHover={setHover}
                  />
                </>
              ) : (
                <LiveEmpty model={model} role={role} practice={practice} send={send} />
              )}
            </div>
          </article>
        </section>
      </main>
      <footer className="footer">
        <p className="footer-source">
          {practice ? 'Practice charts use invented prices. ' : ''}Rules from TCM Core, Revisiting Expansions.
        </p>
        <div className="footer-right">
          <p className="footer-hint">Click a candle to read its expansion. Arrows step a candle. S shows the shadow.</p>
          <a className="footer-credit" href="https://www.tradingview.com/" target="_blank" rel="noreferrer">
            Charts by TradingView Lightweight Charts
          </a>
          {footerEnd}
        </div>
      </footer>
    </>
  );
}

function chartLabel(role: Role, model: Model): string {
  const name = ROLES.find((r) => r.role === role)!.label;
  const tf = chartFor(model.view, role)?.timeframe;
  return tf ? `${name} ${tf}` : name;
}

/** A row of mutually exclusive buttons: the mode, the shadow. */
function Segmented({
  label,
  value,
  options,
  onChange,
  disabled,
  className = '',
  describedBy,
}: {
  describedBy?: string;
  label: string;
  value: string;
  options: { value: string; label: ReactNode; title?: string; tone?: Semantic }[];
  onChange: (v: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <div
      className={`seg ${className}`}
      role="radiogroup"
      aria-label={label}
      aria-describedby={describedBy}
      onKeyDown={(e) => {
        // Arrows move the choice inside the group (as radios do), not the replay.
        if (disabled || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight')) return;
        e.preventDefault();
        e.stopPropagation();
        const i = options.findIndex((o) => o.value === value);
        const next = options[(i + (e.key === 'ArrowRight' ? 1 : options.length - 1)) % options.length]!;
        onChange(next.value);
        (e.currentTarget.querySelectorAll('button')[options.indexOf(next)] as HTMLButtonElement | undefined)?.focus();
      }}
    >
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            tabIndex={on || (value === '' && o === options[0]) ? 0 : -1}
            title={o.title}
            disabled={disabled}
            className={`seg-btn${on ? ' is-on' : ''}${on && o.tone ? ` ${toneClass(o.tone)}` : ''}`}
            onClick={() => onChange(o.value)}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/** Off, A, B: which way the next candle goes on the chart. Off and disabled when nothing is pending. */
function ShadowSwitch({ shadow, value, onChange, offReason }: { shadow: Shadow | null; value: ShadowMode; onChange: (v: ShadowMode) => void; offReason: string }) {
  const label = (key: string, text: string) => (
    <>
      <span className="seg-key">{key}</span>
      <span className="seg-text">{text}</span>
    </>
  );
  const opt = (b: ShadowBranch) => ({ value: b.key, title: `${b.title}. S cycles the shadow.`, tone: TONE[b.tone], label: label(b.key, b.short) });
  return (
    <div className="tcm-shadow" title={shadow ? shadow.question : offReason}>
      <span className="tcm-shadow-label">Shadow</span>
      <span id="tcm-shadow-why" className="sr-only">
        {shadow ? shadow.question : offReason}
      </span>
      <Segmented
        describedBy="tcm-shadow-why"
        label="Shadow: what the next candle could do"
        className="seg-small"
        value={shadow ? value : 'off'}
        disabled={!shadow}
        options={[
          { value: 'off', label: 'Off' },
          ...(shadow
            ? [opt(shadow.a), opt(shadow.b)]
            : (['A', 'B'] as const).map((k) => ({ value: k, label: label(k, k === 'A' ? 'On plan' : 'Against') }))),
        ]}
        onChange={(v) => onChange(v as ShadowMode)}
      />
    </div>
  );
}

/**
 * Under the pane head, as the TTrades panes caption their read: the branch on show and
 * what it would mean. The question it answers is the tooltip.
 */
function ShadowCaption({ shadow, branch, fallback }: { shadow: Shadow | null; branch: ShadowBranch | null; fallback: string }) {
  // One element, always there: the chart never moves when the shadow turns on, and screen readers
  // hear the change (a live region inserted already filled is often not announced).
  if (!shadow || !branch) {
    return (
      <p className="pane-caption tcm-shadow-caption is-quiet" role="note" aria-live="polite">
        {fallback}
      </p>
    );
  }
  return (
    <p className="pane-caption tcm-shadow-caption" role="note" aria-live="polite" title={shadowTitle(shadow, branch)}>
      <span className="sr-only">Illustration, not a forecast. </span>
      <span className={`tcm-shadow-title ${toneClass(TONE[branch.tone])}`}>
        <span className="seg-key">{branch.key}</span>
        <span className="tcm-shadow-cond"> {branch.title}</span>
      </span>
      <span className="tcm-shadow-arrow" aria-hidden>
        {' → '}
      </span>
      <span className="sr-only">: </span>
      {consequence(shadow, branch)}
    </p>
  );
}

function LiveEmpty({ model, role, practice, send }: { model: Model; role: Role; practice: boolean; send: (f: ClientFrame) => void }) {
  if (practice) return <div className="empty"><p>No candles.</p></div>;
  if (model.link !== 'open') {
    return (
      <div className="empty">
        <WifiSlashIcon size={20} aria-hidden className="tone-watch" />
        <p className="empty-title">Not connected to the companion</p>
        <p>Start Trading Companion (or Start-Companion.cmd); this tab reads the same charts as TTrades.</p>
      </div>
    );
  }
  if (!model.view) {
    return (
      <div className="empty">
        <p className="empty-title">No chart yet</p>
        <p>{model.server?.live ? 'Waiting for the first closed candle from TradingView.' : 'Read the chart once to load it.'}</p>
        <button type="button" className="btn btn-small" disabled={model.server?.busy} onClick={() => send({ type: 'check' })}>
          {model.server?.busy ? 'Reading' : 'Read the chart'}
        </button>
      </div>
    );
  }
  return (
    <div className="empty">
      <p>No {role} chart in this read.</p>
    </div>
  );
}

function ReadingView({ reading, decimals, onJump }: { reading: Reading; decimals: number; onJump: (i: number) => void }) {
  const f = (p: number) => formatPrice(p, decimals);
  const level = (key: string) => reading.levels.find((l) => l.key === key)!;
  const rows: [string, number | null][] = [
    [level('high').label, level('high').price],
    ['EQ', level('eq').price],
    ['50% of last candle', level('half').price],
    ['CSD', level('csd').price],
    [level('low').label, level('low').price],
    ['Entry', reading.entry],
    ['Stop', reading.stop],
  ];
  // Top to bottom as on the chart.
  const priced = rows.filter((r): r is [string, number] => r[1] !== null).sort((a, b) => b[1] - a[1]);
  // One line per step; only the step that matters now (the first one waiting, or the void) shows its
  // explanation. A click opens or closes any of them.
  const focus = reading.steps.find((s) => s.key === 'void' || (s.status === 'waiting' && !s.optional))?.key ?? null;
  const [flipped, setFlipped] = useState<ReadonlySet<string>>(() => new Set());
  const toggle = (key: string) =>
    setFlipped((prev) => {
      const next = new Set(prev);
      if (!next.delete(key)) next.add(key);
      return next;
    });
  return (
    <div className="tcm-reading">
      <p className={`tcm-word ${toneClass(reading.verdict.tone)}`}>{reading.verdict.word}</p>
      <p className="tcm-word-detail">{reading.verdict.detail}</p>
      <ol className="tcm-steps">
        {reading.steps.map((s) => {
          const open = (s.key === focus) !== flipped.has(s.key);
          return (
          <li key={s.key} className={`tcm-step is-${s.status}${open ? ' is-open' : ''}`}>
            <span className={`tcm-step-icon ${toneClass(STEP_TONE[s.status])}`}>
              <StatusIcon status={STEP_ICON[s.status]} size={15} />
            </span>
            <div className="tcm-step-body">
              <button type="button" className="tcm-step-title" aria-expanded={open} onClick={() => toggle(s.key)}>
                <span className="sr-only">{STEP_WORD[s.status]}: </span>
                {s.title}
                {s.optional && <span className="tcm-optional">optional</span>}
              </button>
              {open && <p className="tcm-step-detail">{s.detail}</p>}
            </div>
            {s.at !== null ? (
              <button type="button" className="tcm-ref mono" title={`Replay to this candle. Video ${s.ref}`} onClick={() => onJump(s.at!)}>
                {s.ref}
              </button>
            ) : (
              <span className="tcm-ref mono" title={`Video ${s.ref}`}>
                {s.ref}
              </span>
            )}
          </li>
          );
        })}
      </ol>
      <dl className="tcm-levels mono">
        {priced.map(([name, price]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>{f(price)}</dd>
          </div>
        ))}
        <div>
          <dt>Range size</dt>
          <dd>{f(reading.size)}</dd>
        </div>
        {reading.risk !== null && (
          <div>
            <dt>Risk</dt>
            <dd>{f(reading.risk)}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}

function Ohlc({ bar, decimals }: { bar: Bar; decimals: number }) {
  const f = (n: number) => formatPrice(n, decimals);
  return (
    <dl className="ohlc mono">
      {(['open', 'high', 'low', 'close'] as const).map((k) => (
        <div key={k} className={k === 'close' ? undefined : 'ohlc-full'}>
          <dt>{k[0]!.toUpperCase()}</dt>
          <dd>{f(bar[k])}</dd>
        </div>
      ))}
    </dl>
  );
}

interface ChartProps {
  bars: readonly Bar[];
  cursor: number;
  decimals: number;
  fitKey: string;
  follow: boolean;
  reading: Reading | null;
  shadow: ShadowBranch | null;
  ghosts: readonly Bar[];
  hypothetical: boolean;
  marks: readonly LessonMark[];
  showPrices: boolean;
  extend: ExtendMode;
  scale: number;
  theme: ResolvedTheme;
  scheme: Scheme;
  onPick: (i: number) => void;
  onHover: (i: number | null) => void;
}

function TcmChart({ bars, cursor, decimals, fitKey, follow, reading, shadow, ghosts, hypothetical, marks, showPrices, extend, scale, theme, scheme, onPick, onHover }: ChartProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<RangeChart | null>(null);
  const pickRef = useRef(onPick);
  pickRef.current = onPick;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const c = new RangeChart(host, readPalette(host), (i) => pickRef.current(i), onHover);
    chartRef.current = c;
    void document.fonts?.ready.then(() => chartRef.current?.setPalette(readPalette(host)));
    return () => {
      c.destroy();
      chartRef.current = null;
    };
  }, [onHover]);

  useEffect(() => {
    if (hostRef.current) chartRef.current?.setPalette(readPalette(hostRef.current));
  }, [theme, scheme]);

  useEffect(() => {
    chartRef.current?.setBars(bars, cursor, decimals, fitKey, follow);
  }, [bars, cursor, decimals, fitKey, follow]);

  useEffect(() => {
    chartRef.current?.setReading(reading, shadow, ghosts, hypothetical);
  }, [reading, shadow, ghosts, hypothetical]);

  useEffect(() => {
    chartRef.current?.setScale(scale);
  }, [scale]);

  useEffect(() => {
    chartRef.current?.setMarks(marks);
  }, [marks]);

  useEffect(() => {
    chartRef.current?.setShowPrices(showPrices);
  }, [showPrices]);

  useEffect(() => {
    chartRef.current?.setExtend(extend);
  }, [extend]);

  return <div ref={hostRef} className="pane-chart tcm-chart" />;
}
