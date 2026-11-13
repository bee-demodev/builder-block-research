import { ChartLineIcon, GearSixIcon, WarningCircleIcon } from '@phosphor-icons/react';
import { memo, useEffect, useMemo, useRef, useState, type MouseEvent } from 'react';
import { CandleChart, type MarkHover } from '../chart/CandleChart';
import type { Overlays, Scheme } from '../display';
import { initialWindowStart, offScaleNotes, partitionMarks } from '../chart/marks';
import { readPalette } from '../chart/palette';
import { formatPrice, plainText, priceDecimals, sentenceCase } from '../format';
import type { ResolvedTheme } from '../hooks';
import { isStale, type Model } from '../store';
import { readTone } from '../tones';
import type { Candle, ChartView, Direction } from '../wire';
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
}

const ORDER = ['setup', 'bias', 'entry'] as const;
/** Candles each chart opens on: more on the large setup chart, fewer on the small ones. */
const OPEN_BARS = { setup: 60, bias: 40, entry: 40 } as const;

export function ChartsArea({ model, theme, display }: Props) {
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

  // Setup on top, bias and entry below. Unknown roles fill the remaining slots in order.
  const byRole = new Map(view.charts.map((c) => [c.role, c]));
  const rest = view.charts.filter((c) => !(ORDER as readonly string[]).includes(c.role));
  const slots = ORDER.map((role) => byRole.get(role) ?? rest.shift());
  const stale = isStale(model);

  return (
    <section className={`charts${stale ? ' is-stale' : ''}`} aria-label="Charts">
      {slots.map((chart, i) => (
        <div key={ORDER[i]} className={`slot slot-${ORDER[i]}`}>
          {chart ? (
            <ChartPane chart={chart} direction={view.direction} theme={theme} stale={stale} openBars={OPEN_BARS[ORDER[i]!]} {...display} />
          ) : (
            <div className="pane pane-missing">No chart</div>
          )}
        </div>
      ))}
    </section>
  );
}

interface PaneProps extends ChartDisplay {
  chart: ChartView;
  direction: Direction;
  theme: ResolvedTheme;
  stale: boolean;
  openBars: number;
}

const ChartPane = memo(function ChartPane({ chart, direction, theme, stale, openBars, overlays, scheme, scale, openMenu }: PaneProps) {
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

  useEffect(() => {
    chartRef.current?.setView(chart, direction);
  }, [chart, direction]);

  const decimals = useMemo(() => priceDecimals(chart.candles.slice(-200).flatMap((c) => [c.open, c.close])), [chart.candles]);
  const notes = useMemo(() => {
    const from = initialWindowStart(chart.candles.length, chart.marks, openBars);
    return offScaleNotes(partitionMarks(chart.candles.slice(from), chart.marks), decimals);
  }, [chart.candles, chart.marks, decimals, openBars]);
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
        <span className="pane-role">{sentenceCase(chart.role)}</span>
        <span className={`pane-headline ${toneClass(tone)}`} title={plainText(chart.headline)}>
          <StatusIcon status={chart.status} size={13} />
          <span className="pane-headline-text">{plainText(chart.headline)}</span>
        </span>
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
      {ORDER.map((role) => (
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
