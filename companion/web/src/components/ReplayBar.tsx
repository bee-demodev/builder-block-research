import { PauseIcon, PlayIcon, ScissorsIcon, SkipForwardIcon, XIcon } from '@phosphor-icons/react';
import type { ReplayControl } from '../hooks';
import { SPEEDS, atLatest, replayClock, type SpeedKey } from '../replay';
import type { Model } from '../store';
import { Select } from './ui';

const SPEED_KEYS = SPEEDS.map((s) => s.key);

/**
 * Bar replay's controls, under the charts while replay is on: Select bar, Play / Pause,
 * one bar forward, the speed, and back to the latest bar (which ends replay).
 */
export function ReplayBar({ model, control }: { model: Model; control: ReplayControl }) {
  const { replay, dispatch, exit, stepForward } = control;
  const ready = model.link === 'open' && model.server !== null && model.view !== null;
  const selecting = replay.mode === 'select';
  const playing = replay.mode === 'playing';
  const latest = atLatest(model.server);
  const canPlay = ready && !selecting && !latest;
  const clock = replayClock(model.server?.when ?? '');

  const hint = selecting
    ? 'Click a candle on either chart to start the replay after it. Esc cancels.'
    : latest
      ? 'At the latest bar. Select a bar to replay from.'
      : playing
        ? replay.awaiting !== null
          ? 'Reading the next bar.'
          : 'Playing. Space pauses.'
        : 'Paused. Space plays; the right arrow steps one bar.';

  return (
    <div className="replaybar" role="toolbar" aria-label="Bar replay">
      <span className="replaybar-title">Replay</span>
      {clock && <span className="replaybar-clock mono">{clock}</span>}
      <div className="replaybar-controls">
        <button
          type="button"
          className={`btn btn-small${selecting ? ' is-on' : ''}`}
          aria-pressed={selecting}
          disabled={!ready}
          onClick={() => dispatch(selecting ? { type: 'cancelSelect' } : { type: 'select' })}
        >
          <ScissorsIcon size={14} aria-hidden />
          Select bar
        </button>
        <button
          type="button"
          className="btn btn-icon btn-small replaybar-play"
          aria-label={playing ? 'Pause' : 'Play'}
          aria-keyshortcuts="Space"
          title={playing ? 'Pause (Space)' : 'Play (Space)'}
          disabled={!canPlay}
          onClick={() => dispatch({ type: 'toggle' })}
        >
          {playing ? <PauseIcon size={14} weight="fill" aria-hidden /> : <PlayIcon size={14} weight="fill" aria-hidden />}
        </button>
        <button
          type="button"
          className="btn btn-icon btn-small"
          aria-label="Forward one bar"
          aria-keyshortcuts="ArrowRight"
          title="Forward one bar (right arrow)"
          disabled={!canPlay}
          onClick={stepForward}
        >
          <SkipForwardIcon size={14} aria-hidden />
        </button>
        <Select label="Speed" value={replay.speed} options={SPEED_KEYS} hint="1x is one bar a second; no faster than one check per bar" onChange={(v) => dispatch({ type: 'speed', speed: v as SpeedKey })} />
      </div>
      <p className="replaybar-hint" role="status">
        {hint}
      </p>
      <button type="button" className="btn btn-small btn-ghost replaybar-exit" onClick={exit} title="Jump back to the latest bar and end the replay">
        <XIcon size={14} aria-hidden />
        Back to latest
      </button>
    </div>
  );
}
