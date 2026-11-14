import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { JournalBlock } from './components/JournalBlock';
import { demoJournal, demoTrigger, longView, snapshot, watchView } from './demo/fixtures';
import { journalRows, markFrame, noteFrame, openNote, reasonFrame, sampleNote, signedR } from './journal';
import { parseServerFrame, validateFrame, type Journal, type JournalTrigger } from './wire';

const trigger = (changes: Partial<JournalTrigger> = {}): JournalTrigger => ({ ...demoTrigger('2026-11-12T10:30:00-05:00'), ...changes });

const render = (journal: Journal) => renderToStaticMarkup(createElement(JournalBlock, { journal, send: () => {} }));

describe('journal on the wire', () => {
  it('parses a full journal', () => {
    const view = longView();
    const r = validateFrame(JSON.stringify(snapshot(1, view)));
    expect(r.ok).toBe(true);
    if (r.ok && r.frame.type === 'snapshot') expect(r.frame.view?.journal).toEqual(view.journal);
  });

  it('reads null from a saved-history snapshot or a core that predates it', () => {
    const { journal: _gone, ...older } = watchView();
    const r = validateFrame(JSON.stringify(snapshot(1, older as never)));
    expect(r.ok && r.frame.type === 'snapshot' && r.frame.view?.journal).toBeNull();
  });

  it('a malformed journal is logged and dropped, the frame is kept', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const view = { ...longView(), journal: { ...demoJournal(trigger()), stats: { taken: { n: 'six' } } } };
    const frame = parseServerFrame(JSON.stringify(snapshot(2, view as never)), () => {});
    expect(frame?.type).toBe('snapshot');
    if (frame?.type === 'snapshot') {
      expect(frame.view?.journal).toBeNull();
      expect(frame.view?.plan?.state).toBe('triggered');
    }
    expect(warn).toHaveBeenCalledOnce();
    warn.mockRestore();
  });

  it('fills what an older journal leaves out', () => {
    const { reasons: _r, note: _n, ...bare } = demoJournal(null);
    const view = { ...watchView(), journal: { ...bare, stats: { ...bare.stats, min_n: undefined } } };
    const r = validateFrame(JSON.stringify(snapshot(3, view as never)));
    expect(r.ok && r.frame.type === 'snapshot' && r.frame.view?.journal).toMatchObject({ note: '', reasons: [], stats: { min_n: 20 } });
  });
});

describe('journal words', () => {
  it('signs R with a plain hyphen and two decimals', () => {
    expect([signedR(0.42), signedR(-1), signedR(0), signedR(-0.004)]).toEqual(['+0.42R', '-1.00R', '0.00R', '0.00R']);
  });

  it('rows: taken, skipped, all; an empty count shows no average; under min_n is few', () => {
    const stats = { ...demoJournal(null).stats, skipped: { n: 0, avg_r: null } };
    expect(journalRows(stats)).toEqual([
      { key: 'taken', label: 'Took', n: 6, avg: '+0.42R', few: true },
      { key: 'skipped', label: 'Skipped', n: 0, avg: '', few: true },
      { key: 'all', label: 'All triggers', n: 23, avg: '+0.04R', few: false },
    ]);
    expect(sampleNote(stats)).toBe('Under 20 closed trades is too few to mean anything yet.');
    const plenty = { n: 25, avg_r: 0.1 };
    expect(sampleNote({ ...stats, taken: plenty, skipped: plenty, all: plenty })).toBe('');
    expect(openNote(stats)).toBe('2 still open');
    expect(openNote({ ...stats, open: 0 })).toBe('');
  });
});

describe('journal frames', () => {
  it('took it, skipped, and a second press clears the call', () => {
    expect(markFrame(trigger(), 'took', '')).toEqual({ type: 'journal', key: trigger().key, mark: 'took', reason: '', note: '' });
    expect(markFrame(trigger({ mark: 'took', reason: 'late' }), 'skipped', 'n')).toEqual({ type: 'journal', key: trigger().key, mark: 'skipped', reason: 'late', note: 'n' });
    expect(markFrame(trigger({ mark: 'skipped' }), 'skipped', '')).toEqual({ type: 'journal', key: trigger().key, mark: '' });
  });

  it('a reason marks it skipped; the same reason again takes it off', () => {
    expect(reasonFrame(trigger({ mark: 'skipped' }), 'news', '')).toMatchObject({ mark: 'skipped', reason: 'news' });
    expect(reasonFrame(trigger({ mark: 'skipped', reason: 'news' }), 'news', '')).toMatchObject({ mark: 'skipped', reason: '' });
  });

  it('a note is saved with the call only when there is one and it changed', () => {
    expect(noteFrame(trigger(), 'x')).toBeNull();
    expect(noteFrame(trigger({ mark: 'took', note: 'x' }), ' x ')).toBeNull();
    expect(noteFrame(trigger({ mark: 'skipped', reason: 'late', note: '' }), ' chased ')).toEqual({
      type: 'journal', key: trigger().key, mark: 'skipped', reason: 'late', note: 'chased',
    });
  });
});

describe('the journal block', () => {
  it('shows the call, the stats, the sample warning and the stack note', () => {
    const html = render(demoJournal(trigger()));
    expect(html).toContain('Your call on this trigger');
    expect(html).toContain('aria-pressed="false"');
    expect(html).toContain('Took it');
    expect(html).toContain('Journal, 1D / 1h / 5m');
    expect(html).toMatch(/Took<\/th><td class="mono">6<\/td><td class="mono">\+0\.42R/);
    expect(html).toMatch(/All triggers<\/th><td class="mono">23<\/td><td class="mono">\+0\.04R/);
    expect(html).toContain('Under 20 closed trades is too few to mean anything yet.');
    expect(html).toContain('2 still open');
    expect(html).toContain('Backtest 2024-26: flat after costs.');
    expect(html).not.toContain('Why skipped'); // reasons only once skipped
    expect(html).not.toContain('—'); // no em dashes in the copy
  });

  it('skipped: the reason chips and the note; no trigger: stats only', () => {
    const skipped = render(demoJournal(trigger({ mark: 'skipped', reason: 'news', note: 'CPI' })));
    expect(skipped).toContain('aria-label="Why skipped"');
    expect(skipped).toMatch(/class="journal-chip is-on" aria-pressed="true">News/);
    expect(skipped).toContain('value="CPI"');
    const quiet = render(demoJournal(null));
    expect(quiet).not.toContain('Your call');
    expect(quiet).toContain('Journal, 1D / 1h / 5m');
  });

  it('an empty count says so and no stack note means no evidence line', () => {
    const j = demoJournal(null);
    const html = render({ ...j, note: '', stats: { ...j.stats, skipped: { n: 0, avg_r: null } } });
    expect(html).toMatch(/Skipped<\/th><td class="mono">0<\/td><td class="mono">none closed/);
    expect(html).not.toContain('journal-evidence');
  });
});
