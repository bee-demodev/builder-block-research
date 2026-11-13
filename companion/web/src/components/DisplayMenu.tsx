import { ArrowCounterClockwiseIcon, XIcon } from '@phosphor-icons/react';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { OVERLAYS, SCHEMES, TEXT_SIZES, isDefault, type Scheme } from '../display';
import type { Display } from '../hooks';

/** Where the menu opens: next to a button (its rectangle), or at the pointer (a zero-size rectangle). */
export interface MenuAnchor {
  left: number;
  top: number;
  right: number;
  bottom: number;
  /** Open above the anchor (the footer button) rather than below it. */
  above?: boolean;
}

interface Props {
  anchor: MenuAnchor;
  display: Display;
  onClose: () => void;
}

const MARGIN = 8;

/**
 * Display options, per device. A non-modal dialog: Escape, a click outside or moving
 * focus out closes it, and focus goes back to whatever opened it.
 */
export function DisplayMenu({ anchor, display, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const { options } = display;

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    // Right edges line up with a button; at the pointer the menu opens to its right.
    const pointer = anchor.right === anchor.left;
    let left = pointer ? anchor.left : anchor.right - width;
    let top = anchor.above ? anchor.top - height - 6 : anchor.bottom + 6;
    if (top + height > vh - MARGIN) top = Math.max(MARGIN, anchor.top - height - 6);
    if (top < MARGIN) top = MARGIN;
    left = Math.min(Math.max(MARGIN, left), vw - width - MARGIN);
    setPos({ left, top: Math.min(top, Math.max(MARGIN, vh - height - MARGIN)) });
  }, [anchor, options.textSize]);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    // The chosen text size: in a radio group, the checked option is the one Tab lands on.
    ref.current?.querySelector<HTMLElement>('input[name="text-size"]:checked')?.focus();
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener('mousedown', onDown, true);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown, true);
      document.removeEventListener('keydown', onKey);
      if (opener && document.contains(opener)) opener.focus();
    };
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="menu"
      role="dialog"
      aria-label="Display options"
      style={pos ? { left: pos.left, top: pos.top } : { left: -9999, top: 0 }}
      onBlur={(e) => {
        const next = e.relatedTarget as Node | null;
        if (next && ref.current && !ref.current.contains(next)) onClose();
      }}
    >
      <header className="menu-head">
        <h2 className="menu-title">Display</h2>
        <p className="menu-sub">This device only</p>
        <button type="button" className="btn btn-icon btn-small btn-ghost" aria-label="Close" onClick={onClose}>
          <XIcon size={14} aria-hidden />
        </button>
      </header>

      <fieldset className="menu-group">
        <legend className="menu-legend">
          Text size <span className="menu-keys mono">Ctrl + / Ctrl -</span>
        </legend>
        <div className="seg">
          {TEXT_SIZES.map((s) => (
            <label key={s.value} className={`seg-opt${options.textSize === s.value ? ' is-on' : ''}`}>
              <input type="radio" name="text-size" value={s.value} checked={options.textSize === s.value} onChange={() => display.set({ textSize: s.value })} />
              {s.label}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="menu-group">
        <legend className="menu-legend">Direction colours</legend>
        <div className="menu-list">
          {SCHEMES.map((s) => (
            <label key={s.value} className="menu-opt">
              <input type="radio" name="scheme" value={s.value} checked={options.scheme === s.value} onChange={() => display.set({ scheme: s.value })} />
              <Swatch scheme={s.value} />
              <span className="menu-opt-text">
                <span>{s.label}</span>
                <span className="menu-opt-hint">{s.hint}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="menu-group">
        <legend className="menu-legend">On the charts</legend>
        <div className="menu-list">
          {OVERLAYS.map((o) => (
            <label key={o.key} className="menu-opt">
              <input type="checkbox" checked={options.overlays[o.key]} onChange={(e) => display.set({ overlays: { [o.key]: e.target.checked } })} />
              <span className="menu-opt-text">{o.label}</span>
            </label>
          ))}
        </div>
        <p className="menu-note">Entry, stop and target lines always show.</p>
      </fieldset>

      <footer className="menu-foot">
        <button type="button" className="btn btn-small" disabled={isDefault(options)} onClick={display.reset}>
          <ArrowCounterClockwiseIcon size={13} aria-hidden />
          Reset to defaults
        </button>
      </footer>
    </div>
  );
}

/** Two candles in the scheme's own colours: up and down, hollow up for monochrome. */
function Swatch({ scheme }: { scheme: Scheme }) {
  return (
    <span className="swatch" data-swatch={scheme} aria-hidden>
      <span className="swatch-up" />
      <span className="swatch-down" />
    </span>
  );
}
