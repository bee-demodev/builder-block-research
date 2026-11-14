import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  ClockCounterClockwiseIcon,
  ClockIcon,
  DatabaseIcon,
  TriangleIcon,
  WarningCircleIcon,
  WarningIcon,
  XCircleIcon,
} from '@phosphor-icons/react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { checkpointText, planWords, sections, setSide, sideChoices, suggestionText, waitingText } from '../decision';
import { pathLine, plainText, sentenceCase, wallClock } from '../format';
import { isStale, type Model } from '../store';
import { checkTotals, decisionTone, directionTone, isStopLevel, readTone } from '../tones';
import type { ClientFrame, Direction, Plan, VerdictView } from '../wire';
import { Skeleton, StatusIcon, toneClass } from './ui';

interface Props {
  model: Model;
  mode: 'charts' | 'details';
  onToggleMode: () => void;
  send: (frame: ClientFrame) => void;
}

export function DecisionPanel({ model, mode, onToggleMode, send }: Props) {
  const { view, server } = model;
  const firstLoad = !model.everConnected && !view;
  const waitingForSnapshot = model.everConnected && !model.snapshotReceived && !view;

  if (firstLoad || waitingForSnapshot) return <PanelSkeleton />;

  const stale = isStale(model);
  const clock = wallClock(server?.when ?? '');
  const symbol = server?.symbol ?? '';
  const show = view ? sections(view) : null;
  const ready = model.link === 'open' && server !== null;
  const { panelRef, headRef, tall } = useTallHead();

  // Three bands. The head always shows: the side, the decision, what it is waiting for
  // and the one-line chain 1D -> 1h -> 5m (the charts carry the reasons). The middle (the
  // plan or levels, the session clock) scrolls when it does not fit. The foot button
  // (the scorecard) always shows.
  return (
    <aside ref={panelRef} className={`panel${tall ? ' is-tall' : ''}`} aria-label="Decision">
      <div ref={headRef} className="panel-head">
        <div className="panel-top">
          <p className="panel-meta mono">
            <span>{symbol}</span>
            {clock && <span>as of {clock.time} New York</span>}
            {stale && (
              <span className="stale-badge">
                <ClockCounterClockwiseIcon size={12} aria-hidden />
                Stale
              </span>
            )}
          </p>
          <SideSelector model={model} disabled={!ready} send={send} />
        </div>

        {view ? <Verdict view={view} stale={stale} showWaiting={show!.waiting} /> : <NoVerdict symbol={symbol} hasError={Boolean(model.error)} />}
        {view && <Chain view={view} stale={stale} />}
      </div>

      <ScrollBand>
        {model.error && (
          <div className="alert alert-bear" role="alert">
            <WarningCircleIcon size={16} aria-hidden className="tone-bear" />
            <div>
              <p className="alert-title">{view ? 'Could not refresh, showing the last good read' : 'Could not read the market'}</p>
              <p className="alert-body">{plainText(model.error)}</p>
              {model.offerHistory && <UseHistoryButton send={send} />}
            </div>
          </div>
        )}
        {!model.error && model.offerHistory && (
          <div className="alert">
            <DatabaseIcon size={16} aria-hidden />
            <div>
              <p className="alert-body">Live bars are not available right now.</p>
              <UseHistoryButton send={send} />
            </div>
          </div>
        )}

        {view?.plan && <PlanBlock plan={view.plan} stale={stale} />}
        {view && show!.levels && <Levels view={view} />}
        {view && clock && <SessionClock hour={clock.hour} minute={clock.minute} />}
      </ScrollBand>

      {view && (
        <div className="panel-foot">
          <PanelFootButton view={view} mode={mode} onClick={onToggleMode} />
        </div>
      )}
    </aside>
  );
}

/**
 * Whether the head (side, decision, steps) is taller than its share of the panel, as
 * at the larger text sizes. Then the whole panel scrolls as one, so nothing is cut
 * off inside a scrolling head; the foot stays pinned.
 */
function useTallHead() {
  const panelRef = useRef<HTMLElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  const [tall, setTall] = useState(false);
  useEffect(() => {
    const panel = panelRef.current;
    const head = headRef.current;
    if (!panel || !head) return;
    const update = () => setTall(head.scrollHeight > panel.clientHeight * HEAD_SHARE + 1);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(panel);
    for (const child of Array.from(head.children)) ro.observe(child);
    return () => ro.disconnect();
  });
  return { panelRef, headRef, tall };
}

/** The head's share of the panel height (keep in step with .panel-head max-height). */
const HEAD_SHARE = 0.76;

/** Auto, Long, Short. Shows the core's side; a click only asks for one (the core re-checks by itself). */
function SideSelector({ model, disabled, send }: { model: Model; disabled: boolean; send: Props['send'] }) {
  const choices = sideChoices(model.options, model.server);
  return (
    <div className="side" role="group" aria-label="Side" title="A, L and S choose the side">
      {choices.map((c) => (
        <button
          key={c.value || 'auto'}
          type="button"
          className={`side-btn${c.pressed ? ' is-on' : ''}`}
          aria-pressed={c.pressed}
          aria-keyshortcuts={c.value === '' ? 'A' : c.value === 'long' ? 'L' : 'S'}
          disabled={disabled}
          onClick={() => {
            if (!c.pressed) send(setSide(c.value));
          }}
        >
          {c.value && <DirectionIcon side={c.value} size={9} />}
          {c.label}
        </button>
      ))}
    </div>
  );
}

/** ▲ long, ▼ short: the side by shape, so it never rests on colour. */
function DirectionIcon({ side, size }: { side: Direction; size: number }) {
  if (!side) return null;
  return <TriangleIcon size={size} weight="fill" aria-hidden className={`dir-icon${side === 'short' ? ' is-down' : ''}`} />;
}

/** The scrolling middle band. Fades its bottom edge while there is more below. */
function ScrollBand({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [more, setMore] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setMore(el.scrollHeight - el.scrollTop - el.clientHeight > 2);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    for (const child of Array.from(el.children)) ro.observe(child);
    el.addEventListener('scroll', update, { passive: true });
    return () => {
      ro.disconnect();
      el.removeEventListener('scroll', update);
    };
  });
  return (
    <div ref={ref} className={`panel-scroll${more ? ' has-more' : ''}`}>
      {children}
    </div>
  );
}

function Verdict({ view, stale, showWaiting }: { view: VerdictView; stale: boolean; showWaiting: boolean }) {
  const line = pathLine(view);
  const ideaSide = view.suggestion_tone === 'long' || view.suggestion_tone === 'short' || view.suggestion_tone === 'watch' ? view.idea : '';
  return (
    <div className={`verdict${stale ? ' is-stale' : ''}`} key={view.suggestion + view.path}>
      <h1 className={`decision ${toneClass(decisionTone(view.suggestion_tone))}`}>
        <DirectionIcon side={ideaSide} size={20} />
        <span>{suggestionText(view)}</span>
      </h1>
      {line && <p className="path">{line}</p>}
      {view.idea_state && view.idea_alert && (
        <p className="idea-state is-alert" role="note">
          <WarningIcon size={15} weight="bold" aria-hidden className="tone-watch" />
          <span>
            <span className="sr-only">Warning: </span>
            {plainText(view.idea_state)}
          </span>
        </p>
      )}
      {view.auto_note && (
        <p className="auto-note">
          <span className="auto-note-label">By itself</span> {plainText(view.auto_note)}
        </p>
      )}
      {showWaiting && (
        <div className="waiting">
          <p className="waiting-label">Waiting for</p>
          <p className="waiting-text">{waitingText(view)}</p>
        </div>
      )}
    </div>
  );
}

/** The chain at a glance, highest timeframe first: one line per read, its state by icon and colour. */
function Chain({ view, stale }: { view: VerdictView; stale: boolean }) {
  if (view.read.length === 0) return null;
  return (
    <ol className={`chain${stale ? ' is-stale' : ''}`} aria-label="Top-down read">
      {view.read.map((r) => {
        const tone = readTone(r.status);
        return (
          <li key={r.role} className="chain-row" title={plainText(r.reason) || undefined}>
            <span className="chain-tf mono">{r.timeframe}</span>
            <span className="chain-role">{sentenceCase(r.role)}</span>
            <span className={`chain-headline ${toneClass(tone)}`}>{plainText(r.headline)}</span>
            <span className={`chain-icon ${toneClass(tone)}`}>
              <StatusIcon status={r.status} />
              <span className="sr-only">{r.word}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** The next New York checkpoint he works to (9:30, 9:45, 10:00, 10:30, 11:00). */
function SessionClock({ hour, minute }: { hour: number; minute: number }) {
  return (
    <p className="session-clock">
      <ClockIcon size={14} aria-hidden />
      {checkpointText(hour, minute)}
    </p>
  );
}

/** The trade plan. It replaces the plain levels rows when the core sends one. */
function PlanBlock({ plan, stale }: { plan: Plan; stale: boolean }) {
  const w = planWords(plan);
  const planned = plan.state === 'planned';
  return (
    <section className={`plan${stale ? ' is-stale' : ''}`} aria-labelledby="plan-title">
      <header className="plan-head">
        <h2 id="plan-title" className={`plan-title ${toneClass(directionTone(plan.direction))}`}>
          <DirectionIcon side={plan.direction} size={11} />
          {w.title}
        </h2>
        <span className={`plan-state${planned ? ' is-planned' : ''}`}>{w.state}</span>
        {w.stage && plan.outcome === 'open' && (
          <span className={`plan-stage${w.stageAlert ? ' tone-watch' : ''}`} title="Actionable: few entry bars since the trigger and price still near the entry (actionable_entry_bars, actionable_max_r in the style settings)">
            {w.stage}
          </span>
        )}
        {w.outcome && (
          <span className={`plan-outcome ${plan.outcome === 'target_reached' ? 'tone-bull' : 'tone-bear'}`}>
            {plan.outcome === 'target_reached' ? <CheckCircleIcon size={14} aria-hidden /> : <XCircleIcon size={14} aria-hidden />}
            {w.outcome}
          </span>
        )}
      </header>
      <dl className="plan-levels">
        {plan.levels.map((l) => {
          const name = l.name.toLowerCase();
          const tone = name.startsWith('stop') ? 'tone-risk' : name.startsWith('target') ? 'tone-reward' : '';
          return (
            <div key={l.name} className="plan-level">
              <dt>{l.name}</dt>
              <dd className={`plan-price mono ${tone}`}>{l.price}</dd>
              <dd className="plan-note-cell">{plainText(l.note)}</dd>
            </div>
          );
        })}
        {w.last && (
          <div className="plan-level">
            <dt>Last close</dt>
            <dd className="plan-price mono">{w.last.price}</dd>
            <dd className="plan-note-cell mono" title={w.last.r ? `${w.last.r} from the entry` : undefined}>
              {w.last.r}
            </dd>
          </div>
        )}
      </dl>
      {w.cost && (
        <p className="plan-cost mono" title="Stop size against the average daily range; one contract's round-turn cost (a tick of slippage plus commission) as a share of the risk">
          {w.cost}
        </p>
      )}
      {plan.note && <p className="plan-note">{plainText(plan.note)}</p>}
    </section>
  );
}

function NoVerdict({ symbol, hasError }: { symbol: string; hasError: boolean }) {
  if (hasError) return <h1 className="decision decision-empty">No read</h1>;
  return (
    <div className="verdict">
      <h1 className="decision decision-empty">No verdict yet</h1>
      <p className="why">
        Press <span className="kbd">Check</span> to read {symbol || 'the market'} on this stack and style.
      </p>
    </div>
  );
}

function Levels({ view }: { view: VerdictView }) {
  return (
    <dl className="levels" aria-label="Levels">
      {view.levels.map((l) => (
        <div key={l.name} className="level">
          <dt className="level-name">{l.name}</dt>
          <dd className="level-note" title={l.note || undefined}>
            {plainText(l.note)}
          </dd>
          <dd className={`level-price mono${isStopLevel(l) ? ' tone-risk' : ''}`}>{l.price}</dd>
        </div>
      ))}
    </dl>
  );
}

function PanelFootButton({ view, mode, onClick }: { view: VerdictView; mode: Props['mode']; onClick: () => void }) {
  if (mode === 'details') {
    return (
      <button type="button" className="footbtn" onClick={onClick}>
        <span className="footbtn-main">
          <ArrowLeftIcon size={14} aria-hidden />
          Back to charts
        </span>
      </button>
    );
  }
  const t = checkTotals(view.groups);
  return (
    <button type="button" className="footbtn" onClick={onClick} title="Counts the rules of the path in play" aria-keyshortcuts="D">
      <span className="footbtn-main">
        {t.passed} of {t.total} checks passed
      </span>
      <span className="footbtn-aside">
        Details
        <ArrowRightIcon size={14} aria-hidden />
      </span>
    </button>
  );
}

function UseHistoryButton({ send }: { send: Props['send'] }) {
  return (
    <button type="button" className="btn btn-small alert-action" onClick={() => send({ type: 'use_history' })}>
      <DatabaseIcon size={14} aria-hidden />
      Use saved history instead
    </button>
  );
}

function PanelSkeleton() {
  return (
    <aside className="panel" aria-label="Decision" aria-busy="true">
      <div className="panel-scroll">
        <Skeleton w={150} h={12} />
        <Skeleton w={190} h={44} className="sk-gap-lg" />
        <Skeleton w={280} h={16} className="sk-gap" />
        <Skeleton h={14} className="sk-gap" />
        <Skeleton w={240} h={14} className="sk-gap-sm" />
        <Skeleton h={62} className="sk-gap" />
        {[0, 1, 2].map((i) => (
          <div key={i} className="sk-read">
            <Skeleton w={24} h={14} />
            <div className="sk-read-body">
              <Skeleton w={110} h={12} />
              <Skeleton w={200} h={14} />
              <Skeleton w={240} h={12} />
            </div>
          </div>
        ))}
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="sk-level">
            <Skeleton w={70} h={12} />
            <Skeleton w={90} h={14} />
          </div>
        ))}
      </div>
      <div className="panel-foot">
        <Skeleton h={42} />
      </div>
      <span className="sr-only" role="status">
        Connecting to the companion
      </span>
    </aside>
  );
}
