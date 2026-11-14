import { ChartLineIcon, GearSixIcon, WarningCircleIcon } from '@phosphor-icons/react';
import { memo, useEffect, useMemo, useRef, useState, type MouseEvent } from 'react';
import { CandleChart, type MarkHover } from '../chart/CandleChart';
import type { Overlays, Scheme } from '../display';
import { buildColumn, capBand, columnNote, numberedCandles } from '../chart/htf';
import { paneFocus } from '../chart/look';
import type { LookScene } from '../chart/LookLayer';
import { initialWindowStart, offScaleNotes, partitionMarks } from '../chart/marks';
import { readPalette } from '../chart/palette';
import { formatPrice, plainText, priceDecimals, sentenceCase } from '../format';
import type { ResolvedTheme } from '../hooks';
import { isStale, type Model } from '../store';
import { readTone } from '../tones';
import type { Candle, ChartView, Direction, LookFor } from '../wire';
import type { MenuAnchor } from './DisplayMenu';
import { Skeleton, StatusIcon, toneClass } from './ui';

/** What the charts take from the display options. */
export interface ChartDisplay {
  overlays: Overlays;
  scheme: Scheme;
  scale: number;
  /** Open the Display menu at this anchor. */
  openMenu: (anchor: MenuAnchor) => void;
}

interface Props {
  model: Model;
  theme: ResolvedTheme;
  display: ChartDisplay;
  /** The "look for" option the trader picked ("A" or "B"); client-only. */
  lookChoice?: string;
}

/**
 * Two panes side by side, TTFM style: the setup chart (1h) with the bias candles (1D) on its
 * right, then the entry chart (5m) with the setup candles (1h) on its right. Each pane
 * shares one price scale with the candles it carries, so the two agree on price.
 */
const PANES = [
  { role: 'setup', above: 'bias' },
  { role: 'entry', above: 'setup' },
] as const;
const ROLES = ['bias', 'setup', 'entry'] as const;
/** Candles each chart opens on: each pane is half the width, so fewer than a full-width chart keeps the bars readable. */
const OPEN_BARS = { setup: 44, entry: 44 } as const;

export function ChartsArea({ model, theme, display, lookChoice = 'A' }: Props) {
  const { view } = model;
  if (!view) {
    if (!model.snapshotReceived) return <ChartsSkeleton />;
    return (
      <section className="charts charts-empty" aria-label="Charts">
        <div className="empty">
          <ChartLineIcon size={20} aria-hidden />
          <p>{model.error ? 'No charts: the last check could not read the market.' : 'Charts appear here after a check.'}</p>
        </div>
      </section>
    );
  }
  if (view.chart_problem) {
    return (
      <section className="charts charts-empty" aria-label="Charts">
        <div className="empty empty-problem" role="alert">
          <WarningCircleIcon size={20} aria-hidden className="tone-bear" />
          <p className="empty-title">Charts are not available</p>
          <p>{plainText(view.chart_problem)}</p>
        </div>
      </section>
    );
  }

  // Bias, setup, entry by role. Unknown roles fill the missing ones in order.
  const byRole = new Map(view.charts.map((c) => [c.role, c]));
  const rest = view.charts.filter((c) => !(ROLES as readonly string[]).includes(c.role));
  for (const role of ROLES) if (!byRole.has(role) && rest.length) byRole.set(role, rest.shift()!);
  const reasons = new Map<string, string>(view.read.map((r) => [r.role, r.reason]));
  const stale = isStale(model);

  return (
    <section className={`charts${stale ? ' is-stale' : ''}`} aria-label="Charts">
      {PANES.map(({ role, above }) => {
        const chart = byRole.get(role);
        return (
          <div key={role} className={`slot slot-${role}`}>
            {chart ? (
              <ChartPane
                chart={chart}
                above={byRole.get(above) ?? null}
                look={view.look_for}
                lookChoice={lookChoice}
                pane={role}
                reason={reasons.get(chart.role) ?? ''}
                direction={view.direction}
                theme={theme}
                stale={stale}
                openBars={OPEN_BARS[role]}
                {...display}
              />
            ) : (
              <div className="pane pane-missing">No chart</div>
            )}
          </div>
        );
      })}
    </section>
  );
}

interface PaneProps extends ChartDisplay {
  chart: ChartView;
  /** The timeframe above, drawn as candles right of this chart's own; null for none. */
  above: ChartView | null;
  look: LookFor | null;
  lookChoice: string;
  pane: 'setup' | 'entry';
  /** The read's reason for this timeframe: the second line of the chain-of-thought caption. */
  reason: string;
  direction: Direction;
  theme: ResolvedTheme;
  stale: boolean;
  openBars: number;
}

const ChartPane = memo(function ChartPane({ chart, above, look, lookChoice, pane, reason, direction, theme, stale, openBars, overlays, scheme, scale, openMenu }: PaneProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<CandleChart | null>(null);
  const [hover, setHover] = useState<Candle | null>(null);
  const [tip, setTip] = useState<MarkHover | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const c = new CandleChart(host, readPalette(), setHover, openBars, setTip);
    chartRef.current = c;
    // Canvas labels draw with Geist once it has loaded.
    void document.fonts?.ready.then(() => chartRef.current?.setPalette(readPalette()));
    return () => {
      c.destroy();
      chartRef.current = null;
    };
    // openBars is fixed per slot.
  }, []);

  // The scheme and theme attributes are on <html> by now (set in layout effects).
  useEffect(() => {
    chartRef.current?.setPalette(readPalette());
  }, [theme, scheme]);

  useEffect(() => {
    chartRef.current?.setOptions({ overlays, stale, scale });
  }, [overlays, stale, scale]);

  const decimals = useMemo(() => priceDecimals(chart.candles.slice(-200).flatMap((c) => [c.open, c.close])), [chart.candles]);
  // The window the chart opens on: off-scale levels and the column's cap are judged against it.
  const from = useMemo(() => initialWindowStart(chart.candles.length, chart.marks, openBars), [chart.candles.length, chart.marks, openBars]);
  const column = useMemo(
    () => (above ? buildColumn(chart.candles, above.candles, above.timeframe, numberedCandles(above.marks)) : null),
    [chart.candles, above],
  );
  const band = useMemo(() => capBand(chart.candles.slice(from)), [chart.candles, from]);

  const lookScene = useMemo<LookScene | null>(() => (look && look.options.length ? { look, choice: lookChoice, pane } : null), [look, lookChoice, pane]);

  useEffect(() => {
    chartRef.current?.setView(chart, direction, column, band, lookScene);
  }, [chart, direction, column, band, lookScene]);

  const notes = useMemo(() => {
    const out = offScaleNotes(partitionMarks(chart.candles.slice(from), chart.marks), decimals);
    const cut = column ? columnNote(column, band, decimals) : '';
    return cut ? [...out, cut] : out;
  }, [chart.candles, chart.marks, decimals, from, column, band]);
  const shown = hover ?? chart.candles[chart.candles.length - 1] ?? null;
  const tone = readTone(chart.status);
  const onContextMenu = (e: MouseEvent) => {
    e.preventDefault();
    openMenu({ left: e.clientX, top: e.clientY, right: e.clientX, bottom: e.clientY });
  };

  return (
    <article className="pane" aria-label={`${chart.timeframe} ${chart.role} chart`}>
      <header className="pane-head">
        <span className="pane-tf mono">{chart.timeframe}</span>
        <span className="pane-role">{column?.bars.length ? `${column.timeframe} candles on the right` : sentenceCase(chart.role)}</span>
        {lookScene ? (
          // one word per pane while looking for the setup: amber only on the pane awaited now
          <LookTag look={lookScene.look} pane={pane} title={plainText(chart.headline)} />
        ) : (
          <span className={`pane-headline ${toneClass(tone)}`} title={plainText(chart.headline)}>
            <StatusIcon status={chart.status} size={13} />
            <span className="pane-headline-text">{plainText(chart.headline)}</span>
          </span>
        )}
        {stale && <span className="pane-stale">Stale</span>}
        {shown && <Ohlc candle={shown} decimals={decimals} hovered={hover !== null} />}
        <button
          type="button"
          className="btn btn-icon btn-small btn-ghost pane-gear"
          aria-label={`Display options (${chart.timeframe} ${chart.role} chart)`}
          title="Display options. Right-click a chart also opens them."
          onClick={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            openMenu({ left: r.left, top: r.top, right: r.right, bottom: r.bottom });
          }}
        >
          <GearSixIcon size={14} aria-hidden />
        </button>
      </header>
      {reason && <p className="pane-caption">{plainText(reason)}</p>}
      <div className="pane-body" onContextMenu={onContextMenu}>
        <div ref={hostRef} className="pane-chart" onMouseLeave={() => setTip(null)} />
        {tip && <MarkTip tip={tip} width={hostRef.current?.clientWidth ?? 0} />}
        {notes.length > 0 && (
          <div className="pane-notes">
            {notes.map((n) => (
              <p key={n}>{n}</p>
            ))}
          </div>
        )}
      </div>
    </article>
  );
});

/** "Look for" on the pane whose step is awaited now, "Later" on the other. */
function LookTag({ look, pane, title }: { look: LookFor; pane: 'setup' | 'entry'; title: string }) {
  const now = paneFocus(look)[pane];
  return (
    <span className={`pane-look${now ? ' tone-watch' : ''}`} title={title}>
      {now ? 'Look for' : 'Later'}
    </span>
  );
}

/** The full title of the level, zone or marker under the pointer. */
function MarkTip({ tip, width }: { tip: MarkHover; width: number }) {
  const flip = tip.x > width - 220;
  const style = { left: tip.x + 2 + (flip ? -12 : 12), top: tip.y + 14 };
  return (
    <p className={`pane-tip${flip ? ' is-flipped' : ''}`} style={style} role="tooltip">
      {plainText(tip.title)}
    </p>
  );
}

function Ohlc({ candle, decimals, hovered }: { candle: Candle; decimals: number; hovered: boolean }) {
  const f = (n: number) => formatPrice(n, decimals);
  return (
    <dl className="ohlc mono" aria-label={hovered ? 'Hovered candle' : 'Last candle'}>
      <div className="ohlc-full">
        <dt>O</dt>
        <dd>{f(candle.open)}</dd>
      </div>
      <div className="ohlc-full">
        <dt>H</dt>
        <dd>{f(candle.high)}</dd>
      </div>
      <div className="ohlc-full">
        <dt>L</dt>
        <dd>{f(candle.low)}</dd>
      </div>
      <div>
        <dt>C</dt>
        <dd>{f(candle.close)}</dd>
      </div>
    </dl>
  );
}

function ChartsSkeleton() {
  return (
    <section className="charts" aria-label="Charts" aria-busy="true">
      {PANES.map(({ role }) => (
        <div key={role} className={`slot slot-${role}`}>
          <div className="pane pane-skeleton">
            <div className="pane-head">
              <Skeleton w={22} h={14} />
              <Skeleton w={40} h={12} />
              <Skeleton w={160} h={12} />
            </div>
            <div className="pane-body sk-chart">
              <Skeleton h={1} />
              <Skeleton h={1} />
              <Skeleton h={1} />
              <Skeleton h={1} />
            </div>
          </div>
        </div>
      ))}
    </section>
  );
}
