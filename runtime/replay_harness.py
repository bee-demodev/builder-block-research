from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from runtime.harness import Bar, DEFAULT_TIMEZONE, bar_session_bucket, normalize_session_mode


@dataclass(frozen=True)
class ReplayFrame:
    index: int
    timestamp: str
    session_bucket: str
    visible_start_index: int
    visible_end_index: int
    visible_bar_count: int
    open: float
    high: float
    low: float
    close: float


def build_replay_frames(
    bars: Sequence[Bar],
    *,
    warmup_bars: int = 20,
    session_mode: str = "all",
    timezone_name: str = DEFAULT_TIMEZONE,
) -> list[ReplayFrame]:
    allowed_sessions = normalize_session_mode(session_mode)
    frames: list[ReplayFrame] = []
    for index, bar in enumerate(bars):
        bucket = bar_session_bucket(bar, timezone_name=timezone_name)
        if bucket not in allowed_sessions:
            continue
        start_index = max(0, index - warmup_bars)
        frames.append(
            ReplayFrame(
                index=index,
                timestamp=bar.timestamp.isoformat(),
                session_bucket=bucket,
                visible_start_index=start_index,
                visible_end_index=index,
                visible_bar_count=(index - start_index) + 1,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
            )
        )
    return frames

