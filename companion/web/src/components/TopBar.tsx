import { CaretLeftIcon, CaretRightIcon, PauseIcon, PlayIcon } from '@phosphor-icons/react';
import { useEffect, useRef, useState } from 'react';
import { statusParts, wallClock } from '../format';
import { isPaused, type Model } from '../store';
import { hasDot, statusTone } from '../tones';
import type { ClientFrame } from '../wire';
import { Select, toneClass } from './ui';

interface Props {
  model: Model;
  send: (frame: ClientFrame) => void;
}

export function TopBar({ model, send }: Props) {
  const { server, options, link } = model;
  const ready = link === 'open' && server !== null && options !== null;
  const paused = isPaused(model);
  const busy = server?.busy ?? false;

  return (
    <header className="topbar">
      <div className="wordmark">Companion</div>

      <div className="topbar-group">
        <Select label="Symbol" value={server?.symbol ?? ''} options={options?.symbols ?? []} disabled={!ready} onChange={(symbol) => send({ type: 'set', symbol })} />
        <Select
          label="Stack"
          value={server?.stack ?? ''}
          options={options?.stacks ?? []}
          disabled={!ready}
          hint={options?.stack_notes[server?.stack ?? '']}
          onChange={(stack) => send({ type: 'set', stack })}
        />
        <Select label="Style" value={server?.style ?? ''} options={options?.styles ?? []} disabled={!ready} onChange={(style) => send({ type: 'set', style })} />
      </div>

      <TimeControl when={server?.when ?? ''} follow={server?.follow ?? true} disabled={!ready} send={send} />

      <div className="topbar-right">
        <LiveStatus model={model} />
        <button type="button" className="btn" disabled={!ready} onClick={() => send({ type: 'pause', paused: !paused })} aria-keyshortcuts="Space">
          {paused ? <PlayIcon size={14} aria-hidden /> : <PauseIcon size={14} aria-hidden />}
          {paused ? 'Resume' : 'Pause'}
        </button>
        <button type="button" className="btn btn-primary btn-check" disabled={!ready || busy} onClick={() => send({ type: 'check' })}>
          {busy ? 'Checking' : 'Check'}
        </button>
      </div>
    </header>
  );
}

function TimeControl({ when, follow, disabled, send }: { when: string; follow: boolean; disabled: boolean; send: Props['send'] }) {
  const clock = wallClock(when);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const open = () => {
    setDraft(clock?.local ?? '');
    setEditing(true);
  };
  const submit = () => {
    // The input has no offset; the core reads `when` as New York wall time.
    if (draft) send({ type: 'set', when: draft });
    setEditing(false);
  };

  return (
    <div className="timectl" role="group" aria-label="Time">
      <button type="button" className="btn btn-icon" aria-label="Step back one bar" aria-keyshortcuts="ArrowLeft" disabled={disabled} onClick={() => send({ type: 'step', direction: -1 })}>
        <CaretLeftIcon size={14} aria-hidden />
      </button>
      {editing ? (
        <form
          className="when when-edit"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <input
            ref={inputRef}
            type="datetime-local"
            className="mono"
            aria-label="As of, New York time"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') setEditing(false);
            }}
            onBlur={(e) => {
              if (!e.currentTarget.form?.contains(e.relatedTarget as Node | null)) setEditing(false);
            }}
          />
          <button type="submit" className="btn btn-small">
            Go
          </button>
        </form>
      ) : (
        <button type="button" className="when" disabled={disabled || !clock} onClick={open} aria-label={clock ? `As of ${clock.date} ${clock.time} New York. Change` : 'As of'}>
          {clock ? (
            <>
              <span className="when-date">{clock.date}</span>
              <span className="when-time mono">{clock.time}</span>
              <span className="when-zone">New York</span>
            </>
          ) : (
            <span className="when-date">-</span>
          )}
        </button>
      )}
      <button type="button" className="btn btn-icon" aria-label="Step forward one bar" aria-keyshortcuts="ArrowRight" disabled={disabled || follow} onClick={() => send({ type: 'step', direction: 1 })}>
        <CaretRightIcon size={14} aria-hidden />
      </button>
      <button type="button" className="btn" disabled={disabled || follow} aria-pressed={follow} onClick={() => send({ type: 'latest' })}>
        Latest
      </button>
    </div>
  );
}

function LiveStatus({ model }: { model: Model }) {
  const { status, link, timing } = model;
  if (link !== 'open' || !status) {
    const word = link === 'down' ? 'Not connected' : 'Connecting';
    return (
      <div className="livestatus" role="status">
        <span className={`dot ${toneClass(link === 'down' ? 'bear' : 'watch')}`} aria-hidden />
        <span className="livestatus-part">{word}</span>
      </div>
    );
  }
  // The dot stands for a live feed (live, stale, connecting, offline). Saved history,
  // a paused feed and a replay show words only.
  const parts = statusParts(status);
  const timingText = timing
    ? `Fetch ${timing.fetch_ms} ms, compute ${timing.compute_ms} ms${timing.load_ms !== null ? `, load ${timing.load_ms} ms` : ''}${timing.lag_ms !== null ? `, lag ${timing.lag_ms} ms` : ''}.`
    : '';
  const title = [parts.join('. '), timingText].filter(Boolean).join('. ');
  return (
    <div className="livestatus" role="status" title={title}>
      {hasDot(status.state) && <span className={`dot ${toneClass(statusTone(status.state))}`} aria-hidden />}
      {parts.map((p, i) => (
        <span key={i} className={i === 0 ? 'livestatus-part' : 'livestatus-part is-secondary'}>
          {p}
        </span>
      ))}
    </div>
  );
}
