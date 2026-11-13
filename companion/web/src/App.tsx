import { MonitorIcon, MoonIcon, SlidersHorizontalIcon, SunIcon, WarningCircleIcon, WifiSlashIcon, XIcon } from '@phosphor-icons/react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChartsArea, type ChartDisplay } from './components/Charts';
import { Checklist } from './components/Checklist';
import { DecisionPanel } from './components/DecisionPanel';
import { DisplayMenu, type MenuAnchor } from './components/DisplayMenu';
import { TopBar } from './components/TopBar';
import { setSide } from './decision';
import { formatMs, plainText } from './format';
import { useCompanion, useDisplay, useNow, useTheme, type ThemePref } from './hooks';
import { isPaused, type Model } from './store';
import type { ClientFrame, Side, Timing } from './wire';

export function App() {
  const { model, send, retryNow, dismissNotice, url, demo } = useCompanion();
  const theme = useTheme();
  const display = useDisplay();
  const [mode, setMode] = useState<'charts' | 'details'>('charts');
  const [menu, setMenu] = useState<MenuAnchor | null>(null);
  const showDetails = mode === 'details' && model.view !== null;
  const toggleMode = useCallback(() => setMode((m) => (m === 'details' ? 'charts' : 'details')), []);
  useKeyboard(model, send, toggleMode);

  const openMenu = useCallback((anchor: MenuAnchor) => setMenu(anchor), []);
  const closeMenu = useCallback(() => setMenu(null), []);
  const { overlays } = display.options;
  const chartDisplay = useMemo<ChartDisplay>(
    () => ({ overlays, scheme: display.options.scheme, scale: display.scale, openMenu }),
    [overlays, display.options.scheme, display.scale, openMenu],
  );
  const displayBtn = useRef<HTMLButtonElement>(null);

  return (
    <div className="app">
      <TopBar model={model} send={send} />
      <Banners model={model} url={url} retryNow={retryNow} dismissNotice={dismissNotice} />
      <main className="layout">
        <DecisionPanel model={model} mode={showDetails ? 'details' : 'charts'} onToggleMode={() => setMode(showDetails ? 'charts' : 'details')} send={send} />
        {showDetails ? <Checklist model={model} view={model.view!} /> : <ChartsArea model={model} theme={theme.resolved} display={chartDisplay} />}
      </main>
      <footer className="footer">
        <p className="footer-source">{model.view ? plainText(model.view.source_note) : demo ? 'Sample data, demo mode.' : ''}</p>
        <div className="footer-right">
          <p className="footer-hint">Arrows step a bar. Space pauses. A, L, S set the side. D details.</p>
          {model.timing && <TimingReadout timing={model.timing} />}
          <a className="footer-credit" href="https://www.tradingview.com/" target="_blank" rel="noreferrer">
            Charts by TradingView Lightweight Charts
          </a>
          <ThemeToggle pref={theme.pref} onClick={theme.cycle} />
          <button
            ref={displayBtn}
            type="button"
            className="btn btn-small btn-ghost footer-display"
            aria-haspopup="dialog"
            aria-expanded={menu !== null}
            onClick={() => {
              if (menu) return closeMenu();
              const r = displayBtn.current!.getBoundingClientRect();
              openMenu({ left: r.left, top: r.top, right: r.right, bottom: r.bottom, above: true });
            }}
          >
            <SlidersHorizontalIcon size={14} aria-hidden />
            Display
          </button>
        </div>
      </footer>
      {menu && <DisplayMenu anchor={menu} display={display} onClose={closeMenu} />}
    </div>
  );
}

/** The last check's timing, quietly: lag (live), compute and load in ms. Fetch and the moment seen are in the tooltip. */
function TimingReadout({ timing: t }: { timing: Timing }) {
  const parts: string[] = [];
  if (t.lag_ms !== null) parts.push(`lag ${formatMs(t.lag_ms)}`);
  parts.push(`compute ${formatMs(t.compute_ms)}`);
  if (t.load_ms !== null) parts.push(`load ${formatMs(t.load_ms)}`);
  const full = [`Last check: fetch ${formatMs(t.fetch_ms)}`, ...parts.map((p) => p)].join(', ');
  return (
    <p className="footer-timing mono" title={`${full}.`} aria-label={`${full}.`}>
      {parts.map((p) => (
        <span key={p}>{p}</span>
      ))}
    </p>
  );
}

function Banners({ model, url, retryNow, dismissNotice }: { model: Model; url: string; retryNow: () => void; dismissNotice: () => void }) {
  const down = model.link === 'down';
  const now = useNow(down);
  const seconds = model.retryAt ? Math.max(0, Math.ceil((model.retryAt - now) / 1000)) : 0;
  return (
    <div className="banners">
      {down && (
        <div className="banner" role="alert">
          <WifiSlashIcon size={16} aria-hidden className="tone-watch" />
          <p>
            {model.everConnected ? 'Lost the connection to the companion.' : `Cannot reach the companion at ${url}.`}{' '}
            <span className="banner-muted">{seconds > 0 ? `Trying again in ${seconds} s.` : 'Trying again now.'}</span>
          </p>
          <button type="button" className="btn btn-small" onClick={retryNow}>
            Retry now
          </button>
        </div>
      )}
      {model.notice && (
        <div className="banner banner-bear" role="alert">
          <WarningCircleIcon size={16} aria-hidden className="tone-bear" />
          <p>{plainText(model.notice)}</p>
          <button type="button" className="btn btn-icon btn-small" aria-label="Dismiss" onClick={dismissNotice}>
            <XIcon size={14} aria-hidden />
          </button>
        </div>
      )}
    </div>
  );
}

const THEME_LABEL: Record<ThemePref, string> = { system: 'Theme follows the system', dark: 'Dark theme', light: 'Light theme' };

function ThemeToggle({ pref, onClick }: { pref: ThemePref; onClick: () => void }) {
  const Icon = pref === 'dark' ? MoonIcon : pref === 'light' ? SunIcon : MonitorIcon;
  return (
    <button type="button" className="btn btn-icon btn-ghost" onClick={onClick} aria-label={`${THEME_LABEL[pref]}. Change theme`} title={THEME_LABEL[pref]}>
      <Icon size={14} aria-hidden />
    </button>
  );
}

const SIDE_KEYS: Record<string, Side> = { a: '', l: 'long', s: 'short' };

/**
 * Left/right arrows step one bar, space toggles pause, A / L / S choose the side
 * (Auto, Long, Short) and D opens or closes Details. Ignored while a control has focus.
 */
function useKeyboard(model: Model, send: (f: ClientFrame) => void, toggleDetails: () => void) {
  const ready = model.link === 'open' && model.server !== null;
  const paused = isPaused(model);
  const follow = model.server?.follow ?? true;
  const side = model.server?.side ?? '';
  useEffect(() => {
    if (!ready) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.ctrlKey || e.metaKey || e.defaultPrevented) return;
      const el = e.target as HTMLElement | null;
      if (el && el.closest('input, select, textarea, button, a, [contenteditable="true"], [role="dialog"]')) return;
      const key = e.key.toLowerCase();
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        send({ type: 'step', direction: -1 });
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        if (!follow) send({ type: 'step', direction: 1 });
      } else if (e.key === ' ') {
        e.preventDefault();
        send({ type: 'pause', paused: !paused });
      } else if (Object.hasOwn(SIDE_KEYS, key)) {
        e.preventDefault();
        if (SIDE_KEYS[key] !== side) send(setSide(SIDE_KEYS[key]!));
      } else if (key === 'd') {
        e.preventDefault();
        toggleDetails();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [ready, paused, follow, side, send, toggleDetails]);
}
