import { useCallback, useState } from 'react';

/** The app's top-level sections: the TTrades companion, and the TCM Expansions range tool. */
export type Section = 'ttrades' | 'tcm';

const SECTIONS: { key: Section; label: string }[] = [
  { key: 'ttrades', label: 'TTrades' },
  { key: 'tcm', label: 'TCM Expansions' },
];
const KEY = 'companion.section';

/** The open section, kept per device. */
export function useSection(): [Section, (s: Section) => void] {
  const [section, setState] = useState<Section>(() => {
    try {
      return localStorage.getItem(KEY) === 'tcm' ? 'tcm' : 'ttrades';
    } catch {
      return 'ttrades';
    }
  });
  const set = useCallback((s: Section) => {
    setState(s);
    try {
      localStorage.setItem(KEY, s);
    } catch {
      // private mode: the choice lasts this session only
    }
  }, []);
  return [section, set];
}

export function SectionTabs({ value, onChange }: { value: Section; onChange: (s: Section) => void }) {
  return (
    <nav className="sections" aria-label="Sections">
      {SECTIONS.map((s) => (
        <button key={s.key} type="button" className={`section-tab${s.key === value ? ' is-on' : ''}`} aria-current={s.key === value ? 'page' : undefined} onClick={() => onChange(s.key)}>
          {s.label}
        </button>
      ))}
    </nav>
  );
}
