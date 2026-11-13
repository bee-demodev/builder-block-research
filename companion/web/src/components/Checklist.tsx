import { CaretDownIcon, CaretRightIcon, CheckIcon, PlusIcon } from '@phosphor-icons/react';
import { useState } from 'react';
import { formatMs, plainText, titleText, wallClock } from '../format';
import { isStale, type Model } from '../store';
import { advisoryInPlay, checkTotals, groupTally, orderGroups, rowFilter, rowTone, splitColumns, type RowFilter as Filter } from '../tones';
import type { CheckGroup, CheckRow, VerdictView } from '../wire';
import { StatusIcon, toneClass } from './ui';

const ROW_WORD: Record<CheckRow['status'], string> = { pass: 'Passed', fail: 'Failed', na: 'Not yet' };

export function Checklist({ model, view }: { model: Model; view: VerdictView }) {
  const [filters, setFilters] = useState<Record<Filter, boolean>>({ core: true, quality: true, advisory: false });
  const totals = checkTotals(view.groups);
  const advisoryCount = advisoryInPlay(view.groups);

  const visible = view.groups
    .map((g) => ({ ...g, rows: g.rows.filter((r) => filters[rowFilter(r)]) }))
    .filter((g) => g.rows.length > 0);
  // The path in play comes first, in two columns; groups of a path that is not in
  // play follow under one divider, collapsed.
  const { inPlay, notInPlay } = orderGroups(visible);
  const [left, right] = splitColumns(inPlay);

  const toggle = (f: Filter) => setFilters((s) => ({ ...s, [f]: !s[f] }));
  const stale = isStale(model);

  return (
    <section className={`details${stale ? ' is-stale' : ''}`} aria-label="Checklist">
      <header className="details-head">
        <div>
          <h2 className="details-title">Every rule the style checked</h2>
          <p className="details-sub">
            {view.groups.some((g) => !g.active) && 'Path in play: '}
            {totals.passed} passed, {totals.failed} failed
            {totals.notEvaluated > 0 && `, ${totals.notEvaluated} not evaluated`}.{view.notes.length > 0 && ` ${view.notes.map(plainText).join(' ')}`}
          </p>
        </div>
        <div className="filters" role="group" aria-label="Show rules">
          <FilterToggle on={filters.core} label="Gates and steps" onClick={() => toggle('core')} />
          <FilterToggle on={filters.quality} label="Quality" onClick={() => toggle('quality')} />
          <FilterToggle on={filters.advisory} label={advisoryCount || view.hidden_advisory ? `Advisory ${advisoryCount || view.hidden_advisory}` : 'Advisory'} onClick={() => toggle('advisory')} />
        </div>
      </header>

      <div className="details-cols">
        {[left, right].map((col, i) => (
          <div key={i} className="details-col">
            {col.map((g) => (
              <Group key={`${g.name}:in`} group={g} />
            ))}
          </div>
        ))}
        {visible.length === 0 && <p className="details-none">No rules match the filters.</p>}
      </div>

      {notInPlay.length > 0 && (
        <section className="details-other" aria-labelledby="details-other-title">
          <h3 id="details-other-title" className="details-divider">
            Not in play
          </h3>
          <div className="details-other-groups">
            {notInPlay.map((g) => (
              <Group key={`${g.name}:out`} group={g} />
            ))}
          </div>
        </section>
      )}

      <footer className="details-foot">
        {view.invalidation && (
          <div className="note-row">
            <p className="note-label">Invalidation</p>
            <p className="note-text">{plainText(view.invalidation)}</p>
          </div>
        )}
        {view.summary && (
          <div className="note-row">
            <p className="note-label">Summary</p>
            <p className="note-text">{plainText(view.summary)}</p>
          </div>
        )}
        {model.timing && <Timing model={model} />}
      </footer>
    </section>
  );
}

function FilterToggle({ on, label, onClick }: { on: boolean; label: string; onClick: () => void }) {
  return (
    <button type="button" className={`btn chip${on ? ' is-on' : ''}`} aria-pressed={on} onClick={onClick}>
      {on ? <CheckIcon size={13} aria-hidden /> : <PlusIcon size={13} aria-hidden />}
      {label}
    </button>
  );
}

function Group({ group }: { group: CheckGroup }) {
  // A group of a path not in play always starts collapsed.
  const [open, setOpen] = useState(group.active && !group.collapsed);
  const id = `group-${group.name.replace(/\s+/g, '-')}`;
  const title = titleText(group.title);
  // "Continuation C2" already says "continuation"; only show the path when it adds something.
  const showPath = group.path !== '' && !title.toLowerCase().includes(group.path.toLowerCase());
  const tally = groupTally(group);
  return (
    <section className={`group${group.active ? '' : ' is-inactive'}`} aria-labelledby={`${id}-title`}>
      <h3 className="group-head">
        <button type="button" className="group-toggle" aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)}>
          <span id={`${id}-title`} className="group-title">
            {title}
          </span>
          {showPath && <span className="group-path mono">{group.path}</span>}
          <span className="group-tally mono" title={tally.full}>
            <span className="tally-full">{tally.full}</span>
            <span className="tally-short" aria-hidden>
              {tally.short}
            </span>
          </span>
          {open ? <CaretDownIcon size={12} aria-hidden className="group-caret" /> : <CaretRightIcon size={12} aria-hidden className="group-caret" />}
        </button>
      </h3>
      {open && (
        <ul id={id} className="rows">
          {group.rows.map((r) => (
            <li key={r.key} className="row">
              <span className={`row-icon ${toneClass(rowTone(r.status))}`} role="img" aria-label={ROW_WORD[r.status]}>
                <StatusIcon status={r.status} size={16} />
              </span>
              <div className="row-body">
                <p className="row-label">{plainText(r.label)}</p>
                {r.detail && <p className="row-detail">{plainText(r.detail)}</p>}
              </div>
              <p className="row-tags">
                {r.advisory && <span>advisory</span>}
                {r.tags
                  .filter((t) => !(r.advisory && t.toLowerCase() === 'advisory'))
                  .map((t) => (
                    <span key={t}>{t}</span>
                  ))}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Timing({ model }: { model: Model }) {
  const t = model.timing!;
  const closed = t.bar_closed_at ? wallClock(t.bar_closed_at) : null;
  const seen = wallClock(t.detected_at);
  const seconds = /T\d{2}:\d{2}:(\d{2})/.exec(t.detected_at)?.[1];
  return (
    <p className="timing mono">
      {closed && <span>Bar closed {closed.time}</span>}
      {seen && (
        <span>
          Seen {seen.time}
          {seconds ? `:${seconds}` : ''}
        </span>
      )}
      <span>Fetch {formatMs(t.fetch_ms)}</span>
      <span>Compute {formatMs(t.compute_ms)}</span>
      {t.load_ms !== null && <span>Load {formatMs(t.load_ms)}</span>}
      {t.lag_ms !== null && <span>Lag {formatMs(t.lag_ms)}</span>}
    </p>
  );
}
