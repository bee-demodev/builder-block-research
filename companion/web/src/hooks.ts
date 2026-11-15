import { useCallback, useEffect, useLayoutEffect, useReducer, useRef, useState } from 'react';
import { Connection, socketUrl, type SocketLike } from './connection';
import { demoScenario, demoSocketFactory } from './demo/server';
import { initialModel, reduce, type Model } from './store';
import { DEFAULT_DISPLAY, loadDisplay, saveDisplay, stepTextSize, textScale, type DisplayOptions, type Overlays } from './display';
import type { ClientFrame } from './wire';

export interface Companion {
  model: Model;
  send: (frame: ClientFrame) => void;
  retryNow: () => void;
  dismissNotice: () => void;
  url: string;
  demo: string | null;
}

export function useCompanion(): Companion {
  const [model, dispatch] = useReducer(reduce, initialModel);
  const conn = useRef<Connection | null>(null);
  const [{ url, demo }] = useState(() => {
    const scenario = demoScenario(location.search, import.meta.env.VITE_COMPANION_DEMO);
    return {
      demo: scenario,
      url: scenario ? `demo:${scenario}` : socketUrl(location, { DEV: import.meta.env.DEV, VITE_COMPANION_WS: import.meta.env.VITE_COMPANION_WS }),
    };
  });

  useEffect(() => {
    const factory = demo ? demoSocketFactory(demo) : () => new WebSocket(url) as unknown as SocketLike;
    const c = new Connection(factory, dispatch);
    conn.current = c;
    c.start();
    return () => {
      c.stop();
      conn.current = null;
    };
  }, [demo, url]);

  const send = useCallback((frame: ClientFrame) => {
    conn.current?.send(frame);
  }, []);
  const retryNow = useCallback(() => conn.current?.retryNow(), []);
  const dismissNotice = useCallback(() => dispatch({ type: 'dismissNotice' }), []);

  return { model, send, retryNow, dismissNotice, url, demo };
}

// ---------- theme ----------

export type ThemePref = 'system' | 'dark' | 'light';
export type ResolvedTheme = 'dark' | 'light';
const THEME_KEY = 'companion.theme';

function readPref(): ThemePref {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === 'dark' || v === 'light' ? v : 'system';
  } catch {
    return 'system';
  }
}

const darkQuery = () => window.matchMedia('(prefers-color-scheme: dark)');

export function useTheme(): { pref: ThemePref; resolved: ResolvedTheme; cycle: () => void } {
  const [pref, setPref] = useState<ThemePref>(readPref);
  const [systemDark, setSystemDark] = useState(() => darkQuery().matches);

  useEffect(() => {
    const q = darkQuery();
    const on = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    q.addEventListener('change', on);
    return () => q.removeEventListener('change', on);
  }, []);

  // Layout effect: the attribute must be in place before charts read the palette.
  useLayoutEffect(() => {
    const root = document.documentElement;
    if (pref === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', pref);
    try {
      if (pref === 'system') localStorage.removeItem(THEME_KEY);
      else localStorage.setItem(THEME_KEY, pref);
    } catch {
      /* storage unavailable: the choice lasts for this session only */
    }
  }, [pref]);

  const cycle = useCallback(() => setPref((p) => (p === 'system' ? 'dark' : p === 'dark' ? 'light' : 'system')), []);
  const resolved: ResolvedTheme = pref === 'system' ? (systemDark ? 'dark' : 'light') : pref;
  return { pref, resolved, cycle };
}

/** Current time, refreshed every `ms` while `active`. */
export function useNow(active: boolean, ms = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(id);
  }, [active, ms]);
  return now;
}

// ---------- display options ----------

const storage = (): Storage | null => {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
};

export interface Display {
  options: DisplayOptions;
  scale: number;
  set: (patch: Partial<Omit<DisplayOptions, 'overlays'>> & { overlays?: Partial<Overlays> }) => void;
  reset: () => void;
}

/**
 * Per-device display options. The scheme and text size go on <html> as data
 * attributes (tokens.css reads them) before paint, so charts read the right palette.
 * Ctrl+= and Ctrl+- step the text size, Ctrl+0 resets it; they replace the browser's
 * own zoom on this page.
 */
export function useDisplay(): Display {
  const [options, setOptions] = useState<DisplayOptions>(() => loadDisplay(storage()));

  useLayoutEffect(() => {
    const root = document.documentElement;
    // grey is tokens.css's base and has no attribute; every other scheme, the default included, sets one
    if (options.scheme === 'grey') root.removeAttribute('data-scheme');
    else root.setAttribute('data-scheme', options.scheme);
    if (options.textSize === DEFAULT_DISPLAY.textSize) root.removeAttribute('data-text');
    else root.setAttribute('data-text', options.textSize);
    saveDisplay(storage(), options);
  }, [options]);

  const set = useCallback<Display['set']>((patch) => {
    setOptions((o) => ({ ...o, ...patch, overlays: { ...o.overlays, ...patch.overlays } }));
  }, []);
  const reset = useCallback(() => setOptions({ ...DEFAULT_DISPLAY, overlays: { ...DEFAULT_DISPLAY.overlays } }), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
      if (e.key === '=' || e.key === '+') {
        e.preventDefault();
        setOptions((o) => ({ ...o, textSize: stepTextSize(o.textSize, 1) }));
      } else if (e.key === '-' || e.key === '_') {
        e.preventDefault();
        setOptions((o) => ({ ...o, textSize: stepTextSize(o.textSize, -1) }));
      } else if (e.key === '0') {
        e.preventDefault();
        setOptions((o) => ({ ...o, textSize: DEFAULT_DISPLAY.textSize }));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return { options, scale: textScale(options.textSize), set, reset };
}
