import { useState } from 'react';
import { endedLine, journalReasons, journalRows, lateNote, markFrame, noteFrame, openNote, reasonFrame, sampleNote } from '../journal';
import type { ClientFrame, Journal, JournalTrigger } from '../wire';

interface Props {
  journal: Journal;
  send: (frame: ClientFrame) => void;
  disabled?: boolean;
}

/**
 * The decision journal for the stack on screen, quiet and small: the trader's call on the
 * trigger shown (when the journal logged one), the running average R of taken, skipped and
 * every logged trigger, and the stack's backtest note. Display only; nothing here changes
 * the decision.
 */
export function JournalBlock({ journal, send, disabled = false }: Props) {
  const rows = journalRows(journal.stats);
  const few = sampleNote(journal.stats);
  const open = openNote(journal.stats);
  const late = lateNote(journal.stats);
  return (
    <section className="journal" aria-label="Decision journal">
      {journal.trigger && <JournalCall key={journal.trigger.key} trigger={journal.trigger} reasons={journalReasons(journal)} send={send} disabled={disabled} />}
      <h2 className="journal-label">Journal, {journal.stack}</h2>
      <table className="journal-stats">
        <caption className="sr-only">Closed trades on this stack and their average R before costs</caption>
        <thead className="sr-only">
          <tr>
            <th scope="col">Trades</th>
            <th scope="col">Closed</th>
            <th scope="col">Average R</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className={r.few ? 'is-few' : undefined}>
              <th scope="row">{r.label}</th>
              <td className="mono">{r.n}</td>
              <td className="mono">{r.avg || 'none closed'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="journal-hint">
        Average R per closed trade, before costs{open ? `; ${open}` : ''}.{few ? ` ${few}` : ''}{late ? ` ${late}` : ''}
      </p>
      {journal.note && <p className="journal-evidence">{journal.note}</p>}
    </section>
  );
}

function JournalCall({
  trigger,
  reasons,
  send,
  disabled,
}: {
  trigger: JournalTrigger;
  reasons: { key: string; label: string }[];
  send: Props['send'];
  disabled: boolean;
}) {
  const [note, setNote] = useState(trigger.note);
  const saveNote = () => {
    const frame = noteFrame(trigger, note);
    if (frame) send(frame);
  };
  if (trigger.outcome !== 'open') {
    // the trade has ended: a call now would be hindsight, so there is nothing to press
    return (
      <div className="journal-call">
        <h2 className="journal-label">Your call on this trigger</h2>
        <p className="journal-ended">{endedLine(trigger)}</p>
        {(trigger.reason || trigger.note) && (
          <p className="journal-ended">
            {[reasons.find((r) => r.key === trigger.reason)?.label, trigger.note].filter(Boolean).join(': ')}
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="journal-call">
      <h2 className="journal-label" id="journal-call">
        Your call on this trigger
      </h2>
      <div className="side journal-marks" role="group" aria-labelledby="journal-call">
        {(['took', 'skipped'] as const).map((mark) => (
          <button
            key={mark}
            type="button"
            className={`side-btn${trigger.mark === mark ? ' is-on' : ''}`}
            aria-pressed={trigger.mark === mark}
            disabled={disabled}
            onClick={() => send(markFrame(trigger, mark, note.trim()))}
          >
            {mark === 'took' ? 'Took it' : 'Skipped'}
          </button>
        ))}
      </div>
      {trigger.mark === 'skipped' && (
        <div className="journal-reasons" role="group" aria-label="Why skipped">
          {reasons.map((r) => (
            <button
              key={r.key}
              type="button"
              className={`journal-chip${trigger.reason === r.key ? ' is-on' : ''}`}
              aria-pressed={trigger.reason === r.key}
              disabled={disabled}
              onClick={() => send(reasonFrame(trigger, r.key, note.trim()))}
            >
              {r.label}
            </button>
          ))}
        </div>
      )}
      {trigger.mark && (
        <input
          className="journal-note"
          type="text"
          value={note}
          maxLength={200}
          placeholder="Note (optional)"
          aria-label="Note on this call"
          disabled={disabled}
          onChange={(e) => setNote(e.target.value)}
          onBlur={saveNote}
          onKeyDown={(e) => {
            if (e.key === 'Enter') saveNote(); // the app's shortcuts ignore keys typed in a field
          }}
        />
      )}
    </div>
  );
}
