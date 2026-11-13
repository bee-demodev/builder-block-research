"""The companion's desktop window.

    .venv/Scripts/python.exe -m companion.app

Pick where the bars come from (TradingView, live, or the saved history), a symbol, a
timeframe stack and a style. On live data the window checks again by itself each time an
entry-timeframe bar closes; on saved history you pick a New York date and time and press Check.

Top to bottom the window holds four things. The bias selector: Auto (the style proposes
the idea), Long or Short (only that side). The suggestion with the state of its idea
(planned, triggered, open, finished) beside the steps: what has to happen, highest
timeframe first, the next one with its exact price. The trade plan on one line. And three
charts side by side, the entry chart carrying the plan as a risk / reward tool and the
chart of the next step's timeframe carrying that step's level. The top-down read in full
sentences and the whole checklist sit behind "Details". Advisory only: nothing here
places an order.

Display options (text size, direction colours, chart overlays, bars shown) are reached by
right-clicking a chart, from the gear that appears in a chart's header under the pointer,
and from "Display" in the footer; Ctrl+= / Ctrl+- / Ctrl+0 change the text size wherever the
keyboard focus is, and the mouse wheel over a chart (or + / = / - on a focused one) zooms it.

This file is widgets only. Every decision (what the drop-downs offer, validation, time
stepping, running a check, verdict -> rows, which candles and marks go on which chart,
saved state) lives in ``companion.app_model``; colours, contrast and the geometry of a
chart live in ``companion.display``.
"""

from __future__ import annotations

import math
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Callable

from companion.app_model import (
    CUSTOM_CHOICE,
    DATA_HISTORY,
    DATA_LIVE,
    ChartMark,
    ChartView,
    RiskRewardTool,
    CheckOutcome,
    CheckRequest,
    CompanionController,
    UserError,
    VerdictView,
    chart_price_range,
    nice_ticks,
    parse_when,
    tool_captions,
    tool_lines,
)
from companion.display import (
    ACCENT,
    ACCENT_FILL,
    ACCENT_FILL_HOT,
    ACCENT_FILL_PRESSED,
    BG,
    BORDER,
    EDGE,
    ERROR,
    FAILED,
    FAINT,
    FIELD,
    GRID,
    HOVER,
    MARK_PRIORITY,
    MUTED,
    NEXT_BG,
    SURFACE,
    TEXT,
    WARN,
    WHITE,
    ZONE_FILL,
    Box,
    ChartMetrics,
    Flag,
    Theme,
    apply_overlays,
    available_text_sizes,
    backing,
    candle_body,
    chart_span,
    choose_box,
    display_menu,
    dpi_scale,
    fit_flags,
    fit_text_size,
    font_points,
    key_action,
    mark_style,
    menu_origin,
    merge_flags,
    min_window,
    more_note,
    name_gutter,
    needs_compact,
    overlaps,
    paint_order,
    pixels,
    room_message,
    stack_tags,
    status_colours,
    step_text_size,
    text_scale,
    theme_for,
    tones,
    zoom_bars,
)

# --- look -------------------------------------------------------------------------
# Colours are in ``companion.display``. Direction (up / long, down / short) comes from the
# scheme the trader chose and is used for the banner of a trade, the candles and the
# risk / reward zones, and nowhere else. Status: blue is confirmed, amber is waiting,
# grey is failed (the read, the chart headers, what confirmed on the charts, WATCH / DON'T TRADE);
# a scheme whose candles are blue or orange carries its own confirmed and waiting colours.

# a shape beside the word, so nothing rests on colour alone
TONE_GLYPH = {"long": "▲", "short": "▼", "watch": "●", "no_trade": "■", "neutral": ""}
READ_GLYPH = {"confirmed": "✓", "waiting": "●", "failed": "✗", "not_applicable": "–"}
# the steps: done / next / later / blocked, each with its own shape
STEP_GLYPH = {"done": "✓", "next": "▶", "later": "○", "blocked": "✗"}
MAX_STEPS = 7
SIDE_AUTO_VALUE = "auto"  # the radio buttons' value for Auto (the controller's is "")
SIDE_GLYPH = {"": "", "long": "▲ ", "short": "▼ "}
SIDE_HELP = {
    "": "Auto: the rules read all three timeframes and propose the idea.",
    "long": "Long only: what has to happen for a long.",
    "short": "Short only: what has to happen for a short.",
}
STATUS_GLYPH = {"pass": "✓", "fail": "✗", "na": "–"}
ROLE_NAMES = {"bias": "BIAS", "setup": "SETUP", "entry": "ENTRY"}
PANE_ROLES = ("bias", "setup", "entry")  # the three charts, left to right

UI = "Segoe UI"
MONO = "Consolas"
GEAR = "⚙"
POLL_MS = 40
LIVE_TICK_MS = 500
CONTROL = 0x0004  # the Ctrl bit of a key event's state
# the live line beside the status: (mark, colour) by state; "" is the scheme's up colour, "waiting" its waiting colour
LIVE_LOOK = {
    "live": ("●", ""),
    "stale": ("▲", WARN),
    "paused": ("❚❚", MUTED),
    "past": ("◂", "waiting"),
    "offline": ("○", ERROR),
    "connecting": ("…", MUTED),
}
_GEOMETRY = re.compile(r"^(\d+)x(\d+)")
HINT = "Enter check  ·  ← → step one entry bar  ·  A / L / S bias  ·  D details  ·  right-click a chart for display options  ·  advisory only, places no orders"
HINT_SHORT = "Enter check  ·  ← → step  ·  A / L / S bias  ·  D details  ·  advisory only, no orders"


class Look:
    """The one place sizes and direction colours come from.

    Every font is a named Tk font kept here, so a new text size reaches every widget
    without rebuilding any. ``dpi`` is Windows scaling (Tk already draws fonts in
    points, so they follow it); ``text`` is the trader's text size. Pixel sizes written
    for 100 % go through ``px`` (both factors) or ``dpx`` (Windows scaling only).
    """

    def __init__(self) -> None:
        self.dpi = 1.0
        self.text = 1.0
        self.theme: Theme = theme_for("")
        self.generation = 0  # goes up whenever a measured size may have changed
        self._fonts: dict[tuple[str, int, str], tkfont.Font] = {}
        self._root: tk.Misc | None = None

    def start(self, root: tk.Misc, size: str, scheme: str) -> None:
        self._root = root
        self._fonts = {}
        self.dpi = dpi_scale(float(root.tk.call("tk", "scaling")))
        self.text = text_scale(size)
        self.theme = theme_for(scheme)
        self.generation += 1

    @property
    def scale(self) -> float:
        return self.dpi * self.text

    def font(self, family: str, size: int, weight: str = "normal") -> tkfont.Font:
        key = (family, size, weight)
        if key not in self._fonts:
            self._fonts[key] = tkfont.Font(root=self._root, family=family, size=font_points(size, self.text), weight=weight)
        return self._fonts[key]

    def set_text(self, size: str) -> None:
        self.text = text_scale(size)
        for (_family, base, _weight), font in self._fonts.items():
            font.configure(size=font_points(base, self.text))
        self.generation += 1

    def set_scheme(self, scheme: str) -> None:
        self.theme = theme_for(scheme)

    def px(self, value: float) -> int:
        return pixels(value, self.scale)

    def dpx(self, value: float) -> int:
        return pixels(value, self.dpi)


LOOK = Look()


def _step_colours() -> dict[str, str]:
    """The steps' colours in the current scheme: done / next / later / blocked."""
    return {"done": LOOK.theme.confirmed, "next": LOOK.theme.waiting, "later": FAINT, "blocked": FAILED}


def _row_colours() -> dict[str, str]:
    """The checklist marks' colours in the current scheme."""
    return {"pass": LOOK.theme.confirmed, "fail": FAILED, "na": FAINT}


def F(family: str, size: int, weight: str = "normal") -> tkfont.Font:
    """The shared font of this family, base size (points at Normal text) and weight."""
    return LOOK.font(family, size, weight)


def S(value: float) -> int:
    """A pixel size written for 100 % scaling and Normal text, at the current scale."""
    return LOOK.px(value)


def _apply_theme(root: tk.Tk) -> None:
    """Style every ttk widget. Called again after a new text size, for the paddings."""
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(bg=BG)
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_FILL)
    root.option_add("*TCombobox*Listbox.selectForeground", WHITE)
    root.option_add("*TCombobox*Listbox.font", F(UI, 11))
    root.option_add("*TCombobox*Listbox.borderWidth", 0)

    style.configure(".", background=BG, foreground=TEXT, font=F(UI, 10), bordercolor=BORDER, focuscolor=ACCENT)
    style.configure("Panel.TFrame", background=SURFACE)
    style.configure("Caption.TLabel", background=SURFACE, foreground=MUTED, font=F(UI, 8, "bold"))
    style.configure("Problem.TLabel", background=SURFACE, foreground=WARN, font=F(UI, 10))

    field = dict(fieldbackground=FIELD, background=FIELD, foreground=TEXT, bordercolor=EDGE, lightcolor=FIELD, darkcolor=FIELD)
    style.configure("TCombobox", arrowcolor=TEXT, arrowsize=S(14), padding=(S(8), S(6)), selectbackground=FIELD, selectforeground=TEXT, **field)
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", FIELD)],
        foreground=[("readonly", TEXT)],
        selectbackground=[("readonly", FIELD)],
        selectforeground=[("readonly", TEXT)],
        bordercolor=[("focus", ACCENT)],
        arrowcolor=[("active", WHITE)],
    )
    style.configure("TEntry", insertcolor=TEXT, padding=(S(8), S(6)), selectbackground=ACCENT_FILL, selectforeground=WHITE, **field)
    # read-only (live mode: the time is TradingView's): flat on the panel, muted, no input border
    style.map(
        "TEntry",
        bordercolor=[("readonly", BORDER), ("focus", ACCENT)],
        fieldbackground=[("readonly", SURFACE)],
        foreground=[("readonly", MUTED)],
        lightcolor=[("readonly", SURFACE)],
        darkcolor=[("readonly", SURFACE)],
        selectbackground=[("readonly", SURFACE)],
        selectforeground=[("readonly", MUTED)],
    )

    style.configure("TButton", background=FIELD, foreground=TEXT, bordercolor=EDGE, lightcolor=FIELD, darkcolor=FIELD, padding=(S(10), S(6)), font=F(UI, 10))
    style.map("TButton", background=[("pressed", BORDER), ("active", HOVER)], bordercolor=[("focus", ACCENT)])
    style.configure("Step.TButton", padding=(S(10), S(4)), font=F(UI, 12))
    style.configure("Quiet.TButton", background=BG, foreground=MUTED, bordercolor=EDGE, lightcolor=BG, darkcolor=BG, padding=(S(12), S(3)), font=F(UI, 10))
    style.map("Quiet.TButton", background=[("pressed", BORDER), ("active", FIELD)], foreground=[("active", TEXT)], bordercolor=[("focus", ACCENT)])
    style.configure("Gear.TButton", background=BG, foreground=MUTED, bordercolor=EDGE, lightcolor=BG, darkcolor=BG, padding=(S(8), S(1)), font=F(UI, 9))
    style.map("Gear.TButton", background=[("pressed", BORDER), ("active", FIELD)], foreground=[("active", TEXT)], bordercolor=[("focus", ACCENT)])
    # the bias selector: three buttons, one pressed
    style.configure("Side.Toolbutton", background=FIELD, foreground=MUTED, bordercolor=EDGE, lightcolor=FIELD, darkcolor=FIELD, padding=(S(16), S(6)), font=F(UI, 11, "bold"), relief="flat")
    style.map(
        "Side.Toolbutton",
        background=[("selected", ACCENT_FILL), ("active", HOVER)],
        foreground=[("selected", WHITE), ("active", TEXT)],
        bordercolor=[("focus", WHITE), ("selected", ACCENT_FILL)],
        lightcolor=[("selected", ACCENT_FILL)],
        darkcolor=[("selected", ACCENT_FILL)],
    )
    style.configure("Check.TButton", background=ACCENT_FILL, foreground=WHITE, bordercolor=ACCENT_FILL, lightcolor=ACCENT_FILL, darkcolor=ACCENT_FILL, padding=(S(26), S(9)), font=F(UI, 12, "bold"))
    style.map(
        "Check.TButton",
        background=[("pressed", ACCENT_FILL_PRESSED), ("active", ACCENT_FILL_HOT)],
        lightcolor=[("pressed", ACCENT_FILL_PRESSED), ("active", ACCENT_FILL_HOT)],
        darkcolor=[("pressed", ACCENT_FILL_PRESSED), ("active", ACCENT_FILL_HOT)],
        bordercolor=[("focus", WHITE)],
    )

    style.configure(
        "TCheckbutton", background=BG, foreground=MUTED, font=F(UI, 10), padding=(S(4), S(2)), indicatorsize=S(15), indicatormargin=(S(2), S(2), S(7), S(2)),
        indicatorbackground=FIELD, indicatorforeground=FIELD, upperbordercolor=FAINT, lowerbordercolor=FAINT,
    )  # fmt: skip
    style.map(
        "TCheckbutton",
        background=[("active", BG)],
        foreground=[("active", TEXT), ("selected", TEXT)],
        indicatorbackground=[("selected", ACCENT_FILL)],
        indicatorforeground=[("selected", WHITE)],
        upperbordercolor=[("selected", ACCENT_FILL)],
        lowerbordercolor=[("selected", ACCENT_FILL)],
    )
    style.configure(
        "Vertical.TScrollbar", background=EDGE, troughcolor=SURFACE, bordercolor=SURFACE, lightcolor=EDGE, darkcolor=EDGE, arrowcolor=TEXT, gripcount=0,
        width=S(14), arrowsize=S(14),
    )  # fmt: skip
    style.map("Vertical.TScrollbar", background=[("active", FAINT)], lightcolor=[("active", FAINT)], darkcolor=[("active", FAINT)])
    style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=SURFACE, bordercolor=SURFACE, lightcolor=ACCENT, darkcolor=ACCENT, thickness=S(4))


def _money(value: float) -> str:
    return f"{value:,.2f}"


def _cut(text: str, font: tkfont.Font, width: float) -> str:
    """``text``, ended with an ellipsis when it is wider than ``width`` pixels."""
    if not text or font.measure(text) <= width:
        return text
    low, high = 1, len(text)
    while low < high:  # the longest prefix that still fits
        middle = (low + high + 1) // 2
        if font.measure(text[:middle] + "…") <= width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip(" ·,;") + "…"


class Flow:
    """Children of one frame laid out left to right, wrapping onto further rows when the width runs out."""

    def __init__(self, host: tk.Widget, background: str, gap: int = 12, row_gap: int = 6) -> None:
        self.host = host
        self.background = background
        self.gap, self.row_gap = gap, row_gap
        self._rows: list[tk.Frame] = []
        self._shown: tuple[object, ...] = ()

    def arrange(self, widgets: list[tk.Widget], widths: list[int], room: int) -> int:
        """Lay ``widgets`` (children of the host, ``widths`` wide) out in ``room`` pixels; returns the rows used."""
        gap, rows = S(self.gap), [[]]  # type: ignore[var-annotated]
        used = 0
        for widget, width in zip(widgets, widths):
            if rows[-1] and used + gap + width > room:
                rows.append([])
                used = 0
            used += width + (gap if rows[-1] else 0)
            rows[-1].append(widget)
        layout = tuple(tuple(str(widget) for widget in row) for row in rows)
        if layout == self._shown:
            return len(rows)
        self._shown = layout
        for child in self.host.winfo_children():
            if child not in self._rows:
                child.pack_forget()
        while len(self._rows) < len(rows):
            self._rows.append(tk.Frame(self.host, bg=self.background))
        for index, frame in enumerate(self._rows):
            frame.pack_forget()
            if index < len(rows) and rows[index]:
                frame.pack(side="top", anchor="w", pady=(0 if index == 0 else S(self.row_gap), 0))
                for position, widget in enumerate(rows[index]):
                    widget.pack(in_=frame, side="left", anchor="s", padx=(0 if position == 0 else gap, 0))
                    widget.lift()
        return len(rows)

    def forget(self) -> None:
        self._shown = ()


# --- one chart --------------------------------------------------------------------


class ChartPane:
    """Candles of one timeframe with what the read relied on drawn over them.

    It draws a ``ChartView`` and nothing else: which candles exist, where each mark sits
    and how far to zoom are decided in ``companion.app_model``; every size comes from
    ``companion.display.ChartMetrics``, which is built from the measured fonts.

    Back to front (``display.LAYERS``): grid, the zones' fills, the risk / reward fills,
    the zones' edges and every level line, the tool's outline and its entry / stop /
    target lines, the candles, and last everything that is text (captions, marker
    labels, names, price flags), each on its own backing. So no fill covers a line, and
    a zone inside the risk / reward tool keeps its edge and name without repainting it.
    """

    def __init__(
        self,
        parent: tk.Widget,
        role: str = "",
        on_menu: Callable[["ChartPane", int, int], None] | None = None,
        on_zoom: Callable[[str, int], None] | None = None,
    ) -> None:
        self.canvas = tk.Canvas(
            parent, bg=SURFACE, highlightthickness=max(2, LOOK.dpx(2)), highlightbackground=BORDER, highlightcolor=ACCENT, bd=0, cursor="crosshair",
            takefocus=True,
        )  # fmt: skip
        self.role = role
        self.chart: ChartView | None = None
        self.message = ""
        self.stale = False  # the verdict is not current: the tool is drawn like a planned one
        self.overlays: dict[str, bool] = {}
        self.bars = 0  # candles the trader zoomed to; 0 fits them
        self._on_menu, self._on_zoom = on_menu, on_zoom
        self._pending: str | None = None
        self._font_small = F(UI, 10)  # names, marker labels, time labels
        self._font_caption = F(UI, 10, "bold")  # RISK / REWARD
        self._font_role = F(UI, 9, "bold")
        self._font_title = F(UI, 13, "bold")
        self._font_head = F(UI, 10)
        self._font_mono = F(MONO, 10)  # the OHLC readout and the axis prices
        self._font_flag = F(MONO, 10, "bold")  # prices on the flags
        self._font_gear = F(UI, 13)
        self._widths: dict[tuple[str, str], int] = {}  # measured text widths; measuring is slow and texts repeat
        self._lines: dict[str, tuple[int, int]] = {}  # (line height, descent) per font
        self._generation = -1
        self._geometry: dict[str, float] = {}
        self._metrics: ChartMetrics | None = None
        self._span: tuple[int, int, float] | None = None  # candles shown, candles held, plot width
        self._first = 0
        self._readout: int | None = None
        self._cross: tuple[int, int, int, int] | None = None
        self._tip: tuple[int, int] | None = None
        self._gear: int | None = None
        self._hints: list[tuple[Box, str]] = []  # shortened labels: where they are, and their full text
        self._areas: list[tuple[Box, str]] = []  # the risk / reward fills: where they are, and their colour
        self._hatched = False  # those fills are hatched (a planned or stale tool)
        self._dropped: list[Flag] = []  # level labels the plot had no room for
        self._inside = False
        self._focused = False
        canvas = self.canvas
        canvas.bind("<Configure>", self._on_resize)
        canvas.bind("<Motion>", self._on_motion)
        canvas.bind("<Enter>", self._on_enter)
        canvas.bind("<Leave>", self._on_leave)
        canvas.bind("<Button-3>", self._on_right_click)
        canvas.bind("<MouseWheel>", self._on_wheel)
        canvas.bind("<FocusIn>", lambda _event: self._on_focus(True))
        canvas.bind("<FocusOut>", lambda _event: self._on_focus(False))
        for key in ("<space>", "<App>", "<Shift-F10>"):
            canvas.bind(key, self._on_menu_key)
        canvas.bind("<Key>", self._on_key)

    def show(self, chart: ChartView | None, message: str = "", stale: bool = False) -> None:
        self.chart = chart
        self.message = message
        self.stale = stale
        self.draw()

    def _on_resize(self, _event: object) -> None:
        if self._pending is None:
            self._pending = self.canvas.after_idle(self._redraw)

    def _redraw(self) -> None:
        self._pending = None
        self.draw()

    # --- measuring ---

    def _w(self, font: tkfont.Font, text: str) -> int:
        key = (font.name, text)
        if key not in self._widths:
            if len(self._widths) > 20_000:
                self._widths.clear()
            self._widths[key] = font.measure(text)
        return self._widths[key]

    def _line(self, font: tkfont.Font) -> tuple[int, int]:
        if font.name not in self._lines:
            self._lines[font.name] = (int(font.metrics("linespace")), int(font.metrics("descent")))
        return self._lines[font.name]

    def _fit(self, text: str, font: tkfont.Font, width: float) -> str:
        """``text``, cut with an ellipsis when it is wider than ``width`` pixels."""
        if self._w(font, text) <= width:
            return text
        low, high = 1, len(text)
        while low < high:  # the longest prefix that still fits
            middle = (low + high + 1) // 2
            if self._w(font, text[:middle] + "…") <= width:
                low = middle
            else:
                high = middle - 1
        return text[:low].rstrip(" ·") + "…"

    def _measure(self, chart: ChartView | None) -> ChartMetrics:
        """The chart's sizes from its fonts, and the widest price its axis can be asked to show."""
        if self._generation != LOOK.generation:  # another text size: everything measured is out of date
            self._generation = LOOK.generation
            self._widths.clear()
            self._lines.clear()
        prices = [0.0]
        if chart is not None:
            prices += [value for candle in chart.candles for value in (candle.high, candle.low)]
            prices += [value for mark in chart.marks for value in (mark.price, mark.top, mark.bottom) if value is not None]
            if chart.tool is not None:
                prices += [chart.tool.entry, chart.tool.stop, chart.tool.target]
        widest = max((_money(value) for value in (min(prices), max(prices))), key=len)
        widest = re.sub(r"\d", "8", widest if len(widest) >= 8 else "8,888.88")
        return ChartMetrics(
            scale=LOOK.scale,
            dpi=LOOK.dpi,
            line=self._line(self._font_small)[0],
            flag_line=self._line(self._font_flag)[0],
            title_line=self._line(self._font_title)[0],
            readout_line=self._line(self._font_mono)[0],
            price_width=self._w(self._font_flag, widest),
        )

    def min_height(self) -> int:
        """The least height at which this chart is drawn, at the current text size."""
        return self._measure(None).min_height + 2 * int(self.canvas.cget("highlightthickness"))

    # --- drawing ---

    def _back(self, box: Box) -> None:
        """A label's backing: the chart surface, and over the risk / reward tool the fill the label sits on."""
        canvas = self.canvas
        canvas.create_rectangle(*box, fill=SURFACE, outline="")
        for part, fill in backing(box, self._areas):
            canvas.create_rectangle(*part, fill=fill, outline="", stipple="gray50" if self._hatched else "")

    def draw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        self._readout = self._cross = self._tip = self._gear = None
        self._geometry = {}
        self._span = None
        self._hints = []
        self._areas = []
        self._hatched = False
        self._dropped = []
        source = self.chart
        m = self._metrics = self._measure(source)
        px = m.px
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < px(60) or height < px(24):
            return  # not laid out yet
        if source is not None and source.candles and (width < m.min_width or height < m.min_height + 2 * int(canvas.cget("highlightthickness"))):
            # no room for a chart whose labels stay inside it: say so, and how to get the room
            canvas.create_text(
                width / 2, height / 2, text=room_message(LOOK.text > 1.0), fill=TEXT, font=self._font_small, width=max(px(60), width - px(20)),
                justify="center",
            )  # fmt: skip
            return
        theme = LOOK.theme
        gear_room = self._w(self._font_gear, GEAR) + px(14)
        title_line, title_descent = self._line(self._font_title)
        baseline = px(7) + title_line - title_descent
        self._gear = canvas.create_text(
            width - px(8), px(7) + title_line / 2, text=GEAR, font=self._font_gear, fill=MUTED, anchor="e", tags=("gear",),
            state="normal" if self._inside or self._focused else "hidden",
        )  # fmt: skip
        canvas.tag_bind("gear", "<Button-1>", self._on_gear)
        canvas.tag_bind("gear", "<Enter>", lambda _event: (canvas.itemconfigure("gear", fill=WHITE), canvas.configure(cursor="hand2")))
        canvas.tag_bind("gear", "<Leave>", lambda _event: (canvas.itemconfigure("gear", fill=MUTED), canvas.configure(cursor="crosshair")))
        if source is None:
            canvas.create_text(
                width / 2, height / 2, text=self.message or "The chart appears here after a check.", fill=FAINT, font=self._font_head, width=width - px(40),
            )  # fmt: skip
            return
        chart = apply_overlays(source, self.overlays)

        # header: timeframe, role, and the read's line for this timeframe, all on one baseline
        def on_baseline(x: float, text: str, font: tkfont.Font, fill: str) -> None:
            canvas.create_text(x, baseline + self._line(font)[1], text=text, font=font, fill=fill, anchor="sw")

        x = px(12)
        on_baseline(x, chart.timeframe, self._font_title, TEXT)
        x += self._w(self._font_title, chart.timeframe) + px(8)
        role = ROLE_NAMES.get(chart.role, chart.role.upper())
        on_baseline(x, role, self._font_role, MUTED)
        x += self._w(self._font_role, role) + px(14)
        if chart.headline:
            head = f"{READ_GLYPH.get(chart.status, '')}  {chart.headline}"
            shown = self._fit(head, self._font_head, width - x - gear_room)
            on_baseline(x, shown, self._font_head, status_colours(theme).get(chart.status, MUTED))
            if shown != head:
                self._hints.append(((x, 0, width - gear_room, m.readout_y), head))
        self._readout = canvas.create_text(px(12), m.readout_y, text="", font=self._font_mono, fill=MUTED, anchor="nw")

        top, bottom = m.header + px(2), height - m.foot
        left, right = px(8), width - m.axis
        if not chart.candles:
            canvas.create_text(width / 2, height / 2, text=f"No {chart.timeframe} bars at this time.", fill=FAINT, font=self._font_head)
            return

        # the gutter at the right of the plot holds the level names: sized from the names
        # as they will be shown (names at one price share a tag), capped so the candles keep the chart
        levels = [mark for mark in chart.marks if mark.kind in ("level", "zone")]
        tool = chart.tool
        shared: dict[object, list[str]] = {}
        for mark in levels:
            if mark.label:
                shared.setdefault(round(mark.price, 6) if mark.kind == "level" and mark.price is not None else id(mark), []).append(mark.label)
        if tool is not None:
            for _role, price, forms in self._tool_lines(tool):
                shared.setdefault(round(price, 6), []).insert(0, forms[0])
        widths = [self._w(self._font_small, " = ".join(dict.fromkeys(names))) for names in shared.values()]
        gutter = name_gutter(widths, right - left, m.scale)
        name_room = gutter - px(12)
        room = max(float(px(40)), right - gutter - left)
        first, count, pitch = chart_span(chart, room, m.dpi, self.bars)
        candles = chart.candles[first:]
        x0 = right - gutter - count * pitch
        low, high = chart_price_range(chart, first)
        span = (high - low) or 1.0
        y_top, y_bottom = top + m.inset, bottom - m.inset
        if y_bottom - y_top < px(30):
            y_top, y_bottom = top + px(4), bottom - px(4)

        def y_of(price: float) -> float:
            return y_top + (high - price) / span * (y_bottom - y_top)

        def x_of(position: int) -> float:  # centre of the candle at chart position
            return x0 + (position - first + 0.5) * pitch

        self._first = first
        self._span = (count, len(chart.candles), room)
        self._geometry = dict(x0=x0, pitch=pitch, count=count, top=top, bottom=bottom, left=left, right=right, low=low, high=high, y_top=y_top, y_bottom=y_bottom)

        # where each candle is: needed before anything is drawn, to keep the captions off them
        body = candle_body(pitch, m.dpi)
        shapes: list[tuple[float, float, float, float, float]] = []  # body left, body right, wick x, y high, y low
        for index, candle in enumerate(candles):
            body_left = round(x0 + (index + 0.5) * pitch - body / 2)
            shapes.append((body_left, body_left + body, body_left + body // 2, y_of(candle.high), y_of(candle.low)))

        # Everything under the candles is queued with its layer and painted in the order of ``display.LAYERS``,
        # whatever order it is found in: grid, zone fills, risk / reward fills, zone edges and level lines,
        # then the tool's outline and its lines.
        steps: list[tuple[str, Callable[[], object]]] = []

        def queue_line(layer: str, *points: float, **options: object) -> None:
            steps.append((layer, lambda: canvas.create_line(*points, **options)))

        def queue_box(layer: str, *points: float, **options: object) -> None:
            steps.append((layer, lambda: canvas.create_rectangle(*points, **options)))

        # 1. price grid and axis
        queue_line("grid", right, top, right, bottom, fill=BORDER)
        queue_line("grid", left, bottom, right, bottom, fill=BORDER)
        visible_low = high - (bottom - y_top) / (y_bottom - y_top) * span
        visible_high = high + (y_top - top) / (y_bottom - y_top) * span
        ticks = [tick for tick in nice_ticks(visible_low, visible_high, max(3, int((bottom - top) // px(56)))) if top + px(6) < y_of(tick) < bottom - px(6)]
        for tick in ticks:
            queue_line("grid", left, y_of(tick), right, y_of(tick), fill=GRID)

        # 2. the risk / reward fills: over the zones' fills (a zone inside the tool keeps its edge and its
        # name, the risk and the reward keep their colour), under every line
        tool_x = 0.0
        zones: list[tuple[float, float, str, str, str, bool]] = []  # y1, y2, fill, edge, caption, caption at the top
        dashed = bool(tool is not None and (tool.planned or self.stale))
        if tool is not None:
            # never left of the trigger: from its candle (or the first one shown, which is later) to the right edge
            tool_x = left if tool.start < first else x_of(tool.start) - pitch / 2
            long = tool.direction == "long"
            reward_caption, risk_caption = tool_captions(tool)
            for (zone_top, zone_bottom), fill, edge, name, at_top in (
                (tool.reward_zone, theme.reward_fill, theme.up, reward_caption, long),
                (tool.risk_zone, theme.risk_fill, theme.down, risk_caption, not long),
            ):
                zones.append((min(max(y_of(zone_top), top), bottom), min(max(y_of(zone_bottom), top), bottom), fill, edge, name, at_top))
            if tool.box:
                self._hatched = dashed
                for y1, y2, fill, _edge, _name, _at_top in zones:
                    if dashed:  # hatched: on the plain surface, whatever zone lies under it
                        queue_box("tool_fill", tool_x, y1, right, y2, fill=SURFACE, outline="")
                    queue_box("tool_fill", tool_x, y1, right, y2, fill=fill, outline="", stipple="gray50" if dashed else "")
                    self._areas.append(((tool_x, y1, right, y2), fill))

        def span_x(mark: ChartMark) -> tuple[float, float]:
            start = left if mark.start is None or mark.start < first else x_of(mark.start) - pitch / 2
            end = right if mark.end is None else x_of(max(mark.end, first)) + pitch / 2
            return start, end

        # 3. zones (fill, then edges) and level lines
        flags: list[Flag] = []  # labels at the right edge: name in the plot, price on the axis
        off_scale: list[tuple[bool, str]] = []
        for mark in sorted(levels, key=lambda item: -MARK_PRIORITY.index(item.role)):
            colour, dash, line_width = mark_style(theme, mark.role)
            if mark.end is not None and mark.end < first:
                continue
            start, end = span_x(mark)
            named = (mark.label,) if mark.label else ()
            title = mark.label or mark.title
            if mark.kind == "zone" and mark.top is not None and mark.bottom is not None:
                if mark.bottom > visible_high or mark.top < visible_low:
                    off_scale.append((mark.bottom > visible_high, f"{title} {_money(mark.bottom)}–{_money(mark.top)}"))
                    continue
                y1, y2 = max(top, y_of(mark.top)), min(bottom, y_of(mark.bottom))
                queue_box("zone_fill", start, y1, end, y2, fill=ZONE_FILL.get(mark.role, ZONE_FILL["reference"]), outline="")
                if mark.top > visible_high:
                    off_scale.append((True, f"{title}, far edge {_money(mark.top)}"))
                if mark.bottom < visible_low:
                    off_scale.append((False, f"{title}, far edge {_money(mark.bottom)}"))
                for edge_y, price in ((y1, mark.top), (y2, mark.bottom)):
                    if top < edge_y < bottom:
                        queue_line("zone_edge", start, edge_y, end, edge_y, fill=colour, dash=(2, 3))
                        flags.append(Flag(edge_y, price, (), colour, mark.role))
                if named:
                    flags.append(Flag((y1 + y2) / 2, None, named, colour, mark.role))
            elif mark.price is not None:
                if not visible_low <= mark.price <= visible_high:
                    off_scale.append((mark.price > visible_high, f"{title} {_money(mark.price)}"))
                    continue
                y = y_of(mark.price)
                queue_line("level_line", start, y, end, y, fill=colour, dash=dash, width=line_width)
                flags.append(Flag(y, mark.price, named, colour, mark.role))

        # 4. the tool's outline and its entry, stop and target lines: over the zones and levels, under the candles
        if tool is not None:
            if tool.box:
                for y1, y2, _fill, edge, _name, _at_top in zones:
                    queue_box("tool_outline", tool_x, y1, right, y2, fill="", outline=edge, dash=(4, 3) if dashed else None)
            for role, price, _forms in self._tool_lines(tool):
                _role, colour, dash, line_width = self._tool_style(tool, role, dashed)
                queue_line("tool_line", tool_x, y_of(price), right, y_of(price), fill=colour, dash=dash, width=line_width)
        for _layer, paint in paint_order(steps):
            paint()

        def tool_flags(risk_word: bool = False, reward_word: bool = False) -> list[Flag]:
            if tool is None:
                return []
            made = []
            for role, price, forms in self._tool_lines(tool, risk_word, reward_word):
                shown_role, colour, _dash, _line_width = self._tool_style(tool, role, dashed)
                made.append(Flag(y_of(price), price, forms, colour, shown_role, keep=True))
            return made

        # time axis: a label roughly every 90 px, on round clock times where the timeframe has them
        every = max(1, math.ceil(px(90) / pitch))
        last_closed = count - 1 - (1 if candles[-1].forming else 0)
        as_of_x = x0 + count * pitch + px(3)
        labelled = list(range(last_closed, -1, -every))
        if 0 < chart.minutes < 1440:
            wanted = every * chart.minutes
            step = next((size for size in (5, 10, 15, 30, 60, 120, 240, 360, 720, 1440) if size >= wanted and size % chart.minutes == 0), 0)
            if step:  # counted from the 18:00 session open, where every bar grid starts
                labelled = [
                    index for index in range(last_closed + 1)
                    if (candles[index].time.hour * 60 + candles[index].time.minute - 1080) % step == 0
                ]
        label_y = bottom + px(4)
        as_of = f"as of {chart.as_of}"
        as_of_half = self._w(self._font_small, as_of) / 2
        as_of_centre = min(as_of_x, width - as_of_half - px(3))
        taken_x = as_of_centre - as_of_half
        for index in sorted(labelled, reverse=True):
            x = x0 + (index + 0.5) * pitch
            label = candles[index].label
            half = self._w(self._font_small, label) / 2
            if x - half < left or x + half > taken_x - px(10):
                continue
            taken_x = x - half
            canvas.create_line(x, bottom, x, bottom + px(3), fill=EDGE)
            canvas.create_text(x, label_y, text=label, font=self._font_small, fill=FAINT, anchor="n")
        # nothing is drawn to the right of this line: it is the analysis time
        canvas.create_line(as_of_x, top, as_of_x, bottom, fill=FAINT, dash=(2, 4))
        canvas.create_text(as_of_centre, label_y, text=as_of, font=self._font_small, fill=MUTED, anchor="n")

        # 5. candles: up is hollow, down is filled, at every zoom
        for candle, (body_left, body_right, wick, y_high, y_low) in zip(candles, shapes):
            up = candle.close >= candle.open
            colour = theme.up if up else theme.down
            y_open, y_close = y_of(candle.open), y_of(candle.close)
            y1, y2 = min(y_open, y_close), max(y_open, y_close)
            if y2 - y1 < 1:
                y2 = y1 + 1
            canvas.create_line(wick, y_high, wick, y_low, fill=colour)
            if candle.forming:
                canvas.create_rectangle(body_left, y1, body_right, y2, outline=colour, fill=SURFACE, dash=(2, 2))
                if not up:
                    canvas.create_rectangle(body_left, y1, body_right, y2, outline="", fill=colour, stipple="gray50")
            else:
                canvas.create_rectangle(body_left, y1, body_right, y2, outline=colour, fill=SURFACE if up else colour)

        # 6. everything that is text, over the candles, sharing one list of places already taken
        placed: list[Box] = []
        requests = self._draw_marker_shapes(chart, first, x_of, y_of, body)
        if tool is not None and tool.outcome != "open" and tool.outcome_at is not None and tool.outcome_at >= first:
            # the candle that reached the target or the stop: a diamond on that price
            hit_x, hit_y, size = x_of(tool.outcome_at), y_of(tool.target if tool.outcome == "target_reached" else tool.stop), px(6)
            canvas.create_polygon(hit_x, hit_y - size, hit_x + size, hit_y, hit_x, hit_y + size, hit_x - size, hit_y, fill=WHITE, outline=BG)
        # One pass, in the order of how little each label can move. The names first (their places are
        # fixed by their prices), then the notes about what is off the scale, then the words beside
        # marked candles (they step away from the candle), and last the captions, which go where no
        # label and no candle is, anywhere in their zone. A zone with no room for its caption hands
        # the word to its line's name: "Stop · risk", "Target · reward".
        tags = self._place_flags(flags + tool_flags(), right, top, bottom, name_room, m)
        placed += [box for _flag, _name, box in tags if box is not None]
        # notes at the top left: (words, their full text, colour). First the level labels a short plot had no
        # room for (entry, stop, target and the next step's level always keep theirs), then what is off the scale.
        notes: list[tuple[str, str, str]] = []
        if self._dropped:
            left_out = "  ·  ".join(
                " ".join(part for part in (flag.forms[0] if flag.forms else "", _money(flag.price) if flag.price is not None else "") if part)
                for flag in self._dropped
            )
            notes.append((more_note(len(self._dropped)), f"{more_note(len(self._dropped))}, not labelled for want of room: {left_out}", TEXT))
        for above, text in off_scale[:3]:
            words = f"{'▲' if above else '▼'} off the scale: {text}"
            notes.append((words, words, MUTED))
        note_rows = max(0, int((bottom - top - px(3)) // m.tag_gap))
        for row, (words, full, colour) in enumerate(notes[:note_rows]):
            shown = self._fit(words, self._font_small, right - gutter - left - px(8))
            box = (left + px(2), top + px(3) + row * m.tag_gap, left + px(6) + self._w(self._font_small, shown), top + px(3) + row * m.tag_gap + m.tag_height)
            self._back(box)
            canvas.create_text(left + px(4), (box[1] + box[3]) / 2, text=shown, font=self._font_small, fill=colour, anchor="w")
            placed.append(box)
            if shown != full:
                self._hints.append((box, full))
        self._draw_marker_labels(requests, left, right, top, bottom, m, placed)
        if tool is not None and tool.box:
            since = max(0, tool.start - first)
            busy = [(shape[0], shape[3], shape[1], shape[4]) for shape in shapes[since:]]
            worded = [False, False]  # risk, reward
            for index, (y1, y2, fill, edge, name, at_top) in enumerate(zones):  # reward, then risk
                box = choose_box(self._caption_spots(name, tool_x, right, y1, y2, at_top, m), placed, busy)
                if box is None:
                    worded[1 - index] = True
                    continue
                placed.append(box)
                canvas.create_rectangle(*box, fill=fill, outline="")
                canvas.create_text(box[0] + px(5), (box[1] + box[3]) / 2, text=name, font=self._font_caption, fill=edge, anchor="w")
            if any(worded):
                tags = self._place_flags(flags + tool_flags(*worded), right, top, bottom, name_room, m)
        flagged = self._draw_flags(tags, right, width, m, placed)
        for tick in ticks:
            y = y_of(tick)
            if all(abs(y - other) >= m.tag_gap for other in flagged):
                canvas.create_text(right + m.pointer + px(3), y, text=_money(tick), font=self._font_mono, fill=FAINT, anchor="w")

        cross = dict(fill=FAINT, dash=(3, 3), state="hidden")
        vertical = canvas.create_line(0, top, 0, bottom, **cross)
        horizontal = canvas.create_line(left, 0, right, 0, **cross)
        tag_box = canvas.create_rectangle(0, 0, 0, 0, fill=FIELD, outline=EDGE, state="hidden")
        tag_text = canvas.create_text(0, 0, text="", font=self._font_flag, fill=TEXT, anchor="w", state="hidden")
        self._cross = (vertical, horizontal, tag_box, tag_text)
        tip_box = canvas.create_rectangle(0, 0, 0, 0, fill=FIELD, outline=EDGE, state="hidden")
        tip_text = canvas.create_text(0, 0, text="", font=self._font_small, fill=TEXT, anchor="nw", state="hidden")
        self._tip = (tip_box, tip_text)
        canvas.tag_raise("gear")
        self._show_readout(None)

    def _caption_spots(self, text: str, x1: float, x2: float, y1: float, y2: float, at_top: bool, m: ChartMetrics) -> list[Box]:
        """Places a zone's caption may take, best first: its outer corner, then along that edge, then the middle, then the inner edge."""
        px = m.px
        wide, tall = self._w(self._font_caption, text) + px(10), m.tag_height
        if x2 - x1 < wide + px(8) or y2 - y1 < tall + px(6):
            return []
        outer = y1 + px(3) if at_top else y2 - tall - px(3)
        inner = y2 - tall - px(3) if at_top else y1 + px(3)
        rows = [outer]
        if y2 - y1 >= 3 * tall:
            rows += [(y1 + y2 - tall) / 2, inner]
        columns = [x1 + px(4)]
        while columns[-1] + wide / 2 + wide <= x2 - px(4):
            columns.append(columns[-1] + wide / 2)
        return [(x, y, x + wide, y + tall) for y in rows for x in columns]

    @staticmethod
    def _tool_style(tool: RiskRewardTool, role: str, dashed: bool) -> tuple[str, str, tuple[int, ...] | None, int]:
        """(role, colour, dash, width) of one of the tool's lines. An entry the next step waits on is drawn as that step."""
        colour, dash, line_width = mark_style(LOOK.theme, role)
        if role == "entry" and tool.entry_note:
            return ("next", *mark_style(LOOK.theme, "next"))
        if role == "entry" and dashed:
            dash, line_width = (6, 3), 1
        return role, colour, dash, line_width

    @staticmethod
    def _tool_lines(tool: RiskRewardTool, risk_word: bool = False, reward_word: bool = False) -> list[tuple[str, float, tuple[str, ...]]]:
        """(role, price, names) of the tool's three lines: ``companion.app_model.tool_lines``, shared with the wire."""
        return tool_lines(tool, risk_word, reward_word)

    def _draw_marker_shapes(self, chart: ChartView, first: int, x_of, y_of, body: float) -> list[tuple[str, str, float, float, bool, str]]:  # type: ignore[no-untyped-def]
        """Marked candles: a ring round the candle and a pointer. Returns the labels still to place:
        (text, full text, x, y of the pointer's far end, below the candle, colour)."""
        canvas = self.canvas
        px = LOOK.px
        groups: dict[tuple[int, bool], list[ChartMark]] = {}
        for mark in chart.marks:
            if mark.kind != "marker" or mark.start is None or mark.start < first or mark.price is None:
                continue
            candle = chart.candles[mark.start]
            below = mark.price <= (candle.high + candle.low) / 2
            groups.setdefault((mark.start, below), []).append(mark)
        requests = []
        for (position, below), marks in sorted(groups.items()):
            marks.sort(key=lambda item: MARK_PRIORITY.index(item.role))
            colour = mark_style(LOOK.theme, marks[0].role)[0]
            candle = chart.candles[position]
            x = x_of(position)
            half = max(body / 2 + px(3), px(4))
            canvas.create_rectangle(x - half, y_of(candle.high) - px(3), x + half, y_of(candle.low) + px(3), outline=colour)
            tip = y_of(candle.low) + px(5) if below else y_of(candle.high) - px(5)
            away = 1 if below else -1
            canvas.create_polygon(x, tip, x - px(4), tip + px(7) * away, x + px(4), tip + px(7) * away, fill=colour, outline="")
            names = list(dict.fromkeys(mark.label for mark in marks if mark.label))
            if names:
                requests.append((" · ".join(names), " · ".join(names), x, tip + px(9) * away, below, colour))
        return requests

    def _draw_marker_labels(
        self, requests: list[tuple[str, str, float, float, bool, str]], left: float, right: float, top: float, bottom: float, m: ChartMetrics, placed: list[Box]
    ) -> None:  # fmt: skip
        """The words beside each marked candle, stepped away from it until clear of every label already placed."""
        canvas = self.canvas
        tall, pad = m.tag_height, m.px(3)
        for words, full, x, y, below, colour in requests:
            text = self._fit(words, self._font_small, right - left - 2 * pad - m.px(4))
            wide = self._w(self._font_small, text) + 2 * pad
            centre = min(max(x, left + wide / 2 + 1), right - wide / 2 - 1)
            away = 1 if below else -1
            spots = []
            for step in range(8):  # away from the candle first, then the other way
                edge = y + step * m.tag_gap * away
                spots.append((centre - wide / 2, edge if below else edge - tall, centre + wide / 2, edge + tall if below else edge))
            spots = [spot for spot in spots if spot[1] >= top and spot[3] <= bottom] or spots[:1]
            box = next((spot for spot in spots if not any(overlaps(spot, other) for other in placed)), None)
            if box is None:
                # a plot too short for one more label: the ring and the pointer stay, the words wait under the pointer
                # rather than be drawn half under another label
                self._hints.append(((x - m.px(10), min(y, y + away * m.tag_gap), x + m.px(10), max(y, y + away * m.tag_gap)), full))
                continue
            if box[1] < top:
                box = (box[0], top, box[2], top + tall)
            if box[3] > bottom:
                box = (box[0], bottom - tall, box[2], bottom)
            placed.append(box)
            self._back(box)
            canvas.create_text((box[0] + box[2]) / 2, (box[1] + box[3]) / 2, text=text, font=self._font_small, fill=colour)
            if text != full:
                self._hints.append((box, full))

    def _name(self, flag: Flag, room: float) -> str:
        """The fullest of the flag's names that fits ``room``; a role word is shown whole, anything else is cut."""
        for form in flag.forms:
            if self._w(self._font_small, form) <= room:
                return form
        return flag.forms[-1] if flag.keep else self._fit(flag.forms[0], self._font_small, room)

    def _place_flags(self, flags: list[Flag], right: float, top: float, bottom: float, room: float, m: ChartMetrics) -> list[tuple[Flag, str, Box | None]]:
        """Where the level labels go: (flag, the name as shown, the name's box).

        Levels at exactly one price share a flag. Flags that would overlap are moved
        apart and stay inside the plot: when the plot is too short to stack them all,
        the least important are left out (``self._dropped``) and the chart says so.
        """
        merged, self._dropped = fit_flags(merge_flags(flags), m.tag_gap, top, bottom)
        half = m.tag_height / 2
        tags: list[tuple[Flag, str, Box | None]] = []
        for flag, at in zip(merged, stack_tags([flag.y for flag in merged], m.tag_gap, top, bottom)):
            flag.at = at
            name = self._name(flag, room) if flag.forms else ""
            tags.append((flag, name, (right - self._w(self._font_small, name) - m.px(10), at - half, right - m.px(2), at + half) if name else None))
        return tags

    def _draw_flags(self, tags: list[tuple[Flag, str, Box | None]], right: float, width: float, m: ChartMetrics, placed: list[Box]) -> list[float]:
        """Level labels: the name inside the plot at the right, the price as a flag on the axis.

        Each flag's point stays on its true price even when its box was moved. The whole
        price always fits: the axis is as wide as the widest price. Returns where the
        price flags sit.
        """
        canvas = self.canvas
        px = m.px
        half = m.tag_height / 2
        g = self._geometry
        for flag, name, box in tags:
            y, at = min(max(flag.y, g["top"]), g["bottom"]), flag.at
            if box is not None:
                self._back(box)
                canvas.create_text(right - px(5), at, text=name, font=self._font_small, fill=flag.colour, anchor="e")
                placed.append(box)
                if name != flag.forms[0]:
                    self._hints.append((box, flag.forms[0]))
            if flag.price is not None:
                edge = width - px(2)
                canvas.create_polygon(right, y, right + m.pointer, at - half, edge, at - half, edge, at + half, right + m.pointer, at + half, fill=flag.colour, outline="")
                canvas.create_text(right + m.pointer + px(3), at, text=_money(flag.price), font=self._font_flag, fill=BG, anchor="w")
        return [flag.at for flag, _name, _box in tags if flag.price is not None]

    # --- hover readout ---

    def _show_readout(self, position: int | None) -> None:
        chart = self.chart
        if chart is None or self._readout is None or not chart.candles:
            return
        hovering = position is not None
        position = len(chart.candles) - 1 if position is None else position
        candle = chart.candles[position]
        names = [mark.label for mark in chart.marks if mark.kind == "marker" and mark.start == position and mark.label]
        when = f"{candle.label}{' forming' if candle.forming else ''}"
        prices = [("O", candle.open), ("H", candle.high), ("L", candle.low), ("C", candle.close)]
        lead = "" if hovering else "last  "
        up = candle.close >= candle.open  # said in a word and a shape, not by the candle's colour alone
        way, arrow = ("▲ Up", "▲") if up else ("▼ Down", "▼")
        room = self.canvas.winfo_width() - LOOK.px(24)
        marks = " · ".join(dict.fromkeys(names))
        options: list[str] = []  # the fullest wording that fits the chart's width is shown
        for form in ("{0} {1:,.2f}", "{0} {1:.2f}", "{0}{1:.2f}"):
            body = "  ".join(form.format(*pair) for pair in prices)
            if marks:
                options.append(f"{lead}{when}  {way}   {body}   {marks}")
            options.append(f"{lead}{when}  {way}   {body}")
        tight = " ".join(f"{name}{value:.2f}" for name, value in prices)
        options += [
            f"{when} {way}  {tight}", f"{candle.label} {way} {tight}", f"{candle.label} {arrow} {tight}",
            f"{candle.label} {arrow} {tight.split(' ', 1)[1]}", f"{candle.label} {arrow} C{candle.close:.2f}", f"{arrow} C{candle.close:.2f}",
        ]  # fmt: skip
        text = next((option for option in options if self._w(self._font_mono, option) <= room), options[-1])
        self.canvas.itemconfigure(self._readout, text=text, fill=TEXT if hovering else MUTED)

    def _show_tip(self, x: float, y: float) -> bool:
        """The full text of a shortened label under the pointer, beside it. True when one is shown."""
        if self._tip is None:
            return False
        canvas = self.canvas
        tip_box, tip_text = self._tip
        words = next((full for box, full in self._hints if box[0] <= x <= box[2] and box[1] <= y <= box[3]), "")
        if not words:
            canvas.itemconfigure(tip_box, state="hidden")
            canvas.itemconfigure(tip_text, state="hidden")
            return False
        px = LOOK.px
        width, height = canvas.winfo_width(), canvas.winfo_height()
        canvas.itemconfigure(tip_text, text=words, width=max(px(120), width - px(24)), state="normal")
        canvas.coords(tip_text, 0, 0)
        x1, y1, x2, y2 = canvas.bbox(tip_text)
        wide, tall = x2 - x1, y2 - y1
        at_x = min(max(px(6), x - wide / 2), width - wide - px(8))
        at_y = y + px(18) if y + px(18) + tall + px(6) < height else y - tall - px(12)
        canvas.coords(tip_text, at_x, at_y)
        canvas.coords(tip_box, at_x - px(5), at_y - px(3), at_x + wide + px(5), at_y + tall + px(3))
        canvas.itemconfigure(tip_box, state="normal")
        canvas.tag_raise(tip_box)
        canvas.tag_raise(tip_text)
        return True

    def _on_motion(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._show_gear(True)
        tipped = self._show_tip(event.x, event.y)
        g = self._geometry
        if not g or self._cross is None or self.chart is None:
            return
        vertical, horizontal, tag_box, tag_text = self._cross
        canvas = self.canvas
        index = int((event.x - g["x0"]) // g["pitch"])
        inside = 0 <= index < g["count"] and g["top"] <= event.y <= g["bottom"]
        if not inside or tipped:
            self._hide_cross()
            return
        m = self._metrics
        assert m is not None
        half = m.tag_height / 2
        x = g["x0"] + (index + 0.5) * g["pitch"]
        price = g["high"] - (event.y - g["y_top"]) / (g["y_bottom"] - g["y_top"]) * ((g["high"] - g["low"]) or 1.0)
        at = min(max(event.y, g["top"] + half), g["bottom"] - half)
        canvas.coords(vertical, x, g["top"], x, g["bottom"])
        canvas.coords(horizontal, g["left"], event.y, g["right"], event.y)
        canvas.coords(tag_box, g["right"] + 1, at - half, canvas.winfo_width() - m.px(2), at + half)
        canvas.coords(tag_text, g["right"] + m.pointer + m.px(3), at)
        canvas.itemconfigure(tag_text, text=_money(price))
        for item in self._cross:
            canvas.itemconfigure(item, state="normal")
            canvas.tag_raise(item)
        self._show_readout(self._first + index)

    def _hide_cross(self) -> None:
        if self._cross is not None:
            for item in self._cross:
                self.canvas.itemconfigure(item, state="hidden")
        self._show_readout(None)

    def _show_gear(self, inside: bool | None = None) -> None:
        if inside is not None:
            self._inside = inside
        if self._gear is not None:
            self.canvas.itemconfigure(self._gear, state="normal" if self._inside or self._focused else "hidden")

    def _on_enter(self, _event: object) -> None:
        self._show_gear(True)

    def _on_leave(self, _event: object) -> None:
        self._show_gear(False)
        self._show_tip(-1, -1)
        self._hide_cross()

    def _on_focus(self, focused: bool) -> None:
        self._focused = focused
        self._show_gear()

    # --- display options: the menu and the zoom ---

    def _open_menu(self, x: int, y: int) -> None:
        if self._on_menu is not None:
            self._on_menu(self, x, y)

    def _on_right_click(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._open_menu(event.x_root, event.y_root)

    def _gear_corner(self) -> tuple[int, int]:
        """Screen position just under the gear, where its menu opens."""
        canvas = self.canvas
        box = canvas.bbox("gear") if self._gear is not None else None
        x, y = (box[0], box[3]) if box else (canvas.winfo_width() - LOOK.px(30), LOOK.px(30))
        return canvas.winfo_rootx() + int(x), canvas.winfo_rooty() + int(y)

    def _on_gear(self, _event: object) -> str:
        self._open_menu(*self._gear_corner())
        return "break"

    def _on_menu_key(self, _event: object) -> str:
        self._open_menu(*self._gear_corner())
        return "break"

    def _on_wheel(self, event: tk.Event) -> str:  # type: ignore[type-arg]
        self.zoom(1 if event.delta > 0 else -1)
        return "break"

    def _on_key(self, event: tk.Event) -> str | None:  # type: ignore[type-arg]
        """+ / = / - zoom this chart. With Ctrl they are the window's text size, here as anywhere: not handled here."""
        action = key_action(str(event.keysym), bool(int(event.state) & CONTROL), True)
        if action in ("zoom_in", "zoom_out"):
            return self.zoom(1 if action == "zoom_in" else -1)
        return None

    def zoom(self, notches: int) -> str:
        """Fewer, wider candles (positive) or more, narrower ones, never past the limits; remembered through ``on_zoom``."""
        if self._span is None or self._metrics is None:
            return "break"
        count, total, room = self._span
        bars = zoom_bars(count, notches, total, room, self._metrics.min_pitch)
        if bars != count:
            self.bars = bars
            if self._on_zoom is not None:
                self._on_zoom(self.role, bars)
            self.draw()
        return "break"


# --- the window -------------------------------------------------------------------


class CompanionApp:
    """The window. Reads and writes ``controller.state``; draws ``VerdictView`` objects."""

    def __init__(self, root: tk.Tk, controller: CompanionController | None = None) -> None:
        self.root = root
        self.controller = controller if controller is not None else CompanionController()
        self._results: queue.Queue[tuple[int, CheckOutcome]] = queue.Queue()
        self._sequence = 0
        self._busy = False
        self._pending: tuple[int, CheckRequest] | None = None
        self._outcome: CheckOutcome | None = None
        self._view: VerdictView | None = None
        self._collapsed: dict[str, bool] = {}
        self._details_open = False  # the full checklist starts hidden, every time
        self._details_stale = False  # the checklist is only repainted while it is on screen
        self._closed = False
        self._good: CheckOutcome | None = None  # the last live verdict, kept on screen (marked stale) when a refresh fails
        self._shown: CheckOutcome | None = None  # the outcome whose verdict is drawn
        self._stale_drawn = False
        self._screen: tuple[object, ...] = ("idle",)  # what is painted: idle, a problem, or an outcome
        self._menu: tk.Menu | None = None
        self._compact = False  # the steps and the reason are folded, to keep the charts drawable on a short screen
        self._why_lines = 2  # lines the reason keeps while compact: two, or one when two still leave the charts too little
        self._fit_job: str | None = None
        self._why = self._note = ""
        self._steps_shown: tuple[VerdictView | None, str, bool] = (None, "", False)
        self._folded: list[tk.Widget] = []  # step rows the compact layout has folded away

        state = self.controller.state
        fitting = fit_text_size(state.text_size, dpi_scale(float(root.tk.call("tk", "scaling"))), self._screen_size())
        if fitting != state.text_size:  # saved on a taller screen, or at a lower Windows scaling
            self.controller.set_text_size(fitting)
        LOOK.start(root, state.text_size, state.colours)
        _apply_theme(root)
        root.title("Trading Companion")
        _darken_title_bar(root)
        least_width, least_height = self._apply_minsize()
        match = _GEOMETRY.match(state.geometry)
        width, height = (int(match.group(1)), int(match.group(2))) if match else (LOOK.dpx(1500), LOOK.dpx(960))
        height = max(least_height, min(height, root.winfo_screenheight() - 90))
        width = max(least_width, min(width, root.winfo_screenwidth() - 40))
        root.geometry(f"{width}x{height}")
        self.var_text_size = tk.StringVar(value=state.text_size)
        self.var_scheme = tk.StringVar(value=state.colours)
        self.var_overlays = {name: tk.BooleanVar(value=shown) for name, shown in self.controller.overlays().items()}

        self._build_controls()
        self._build_summary()
        self._build_footer()
        self._build_body()
        self._load_selections()
        self._show_idle()

        root.bind_all("<Return>", self._on_enter)
        root.bind_all("<KP_Enter>", self._on_enter)
        root.bind_all("<Left>", lambda event: self._on_arrow(event, -1))
        root.bind_all("<Right>", lambda event: self._on_arrow(event, 1))
        root.bind_all("<KeyPress-d>", self._on_details_key)
        root.bind_all("<KeyPress-D>", self._on_details_key)
        for key, side in (("a", ""), ("l", "long"), ("s", "short")):
            for name in (key, key.upper()):
                root.bind_all(f"<KeyPress-{name}>", lambda event, side=side: self._on_side_key(event, side))
        root.bind_all("<Control-Key>", self._on_control_key)  # Ctrl with = / + / - / 0: the text size, whatever has the focus
        root.bind("<Configure>", self._on_window_resized, add="+")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(POLL_MS, self._poll)
        root.after(LIVE_TICK_MS, self._tick_live)
        if self.controller.is_live:
            root.after(150, lambda: self.check(auto=True))

    # --- construction ---

    def _build_controls(self) -> None:
        panel = ttk.Frame(self.root, style="Panel.TFrame", padding=(S(18), S(10), S(18), S(5)))
        panel.pack(fill="x")
        self.var_data = tk.StringVar()
        self.var_symbol = tk.StringVar()
        self.var_stack = tk.StringVar()
        self.var_style = tk.StringVar()
        self.var_date = tk.StringVar()
        self.var_time = tk.StringVar()
        self.var_bias = tk.StringVar()
        self.var_setup = tk.StringVar()
        self.var_entry = tk.StringVar()

        row = ttk.Frame(panel, style="Panel.TFrame")
        row.pack(fill="x")
        self.button_check = ttk.Button(row, text="Check", style="Check.TButton", command=self.check)
        self.button_check.pack(side="right", anchor="n", padx=(S(12), 0), pady=(F(UI, 8, "bold").metrics("linespace") - S(4), 0))
        # the selections flow left to right and wrap onto a second row when the window is narrow
        host = ttk.Frame(row, style="Panel.TFrame")
        host.pack(side="left", fill="x", expand=True)
        self._controls_host = host
        self._controls_flow = Flow(host, SURFACE, gap=12, row_gap=8)
        self._control_columns: list[ttk.Frame] = []

        def column(parent: ttk.Frame, caption: str, pad: int = 12) -> ttk.Frame:
            holder = ttk.Frame(parent, style="Panel.TFrame")
            if parent is host:
                self._control_columns.append(holder)  # placed by the flow
            else:
                holder.pack(side="left", padx=(0, S(pad)), anchor="s")
            holder.caption = ttk.Label(holder, text=caption, style="Caption.TLabel")  # type: ignore[attr-defined]
            holder.caption.pack(anchor="w", pady=(0, S(4)))  # type: ignore[attr-defined]
            return holder

        def combo(parent: ttk.Frame, variable: tk.StringVar, width: int) -> ttk.Combobox:
            box = ttk.Combobox(parent, textvariable=variable, state="readonly", width=width, font=F(UI, 11))
            box.pack(anchor="w")
            return box

        self.box_data = combo(column(host, "DATA"), self.var_data, 16)
        self.box_symbol = combo(column(host, "SYMBOL"), self.var_symbol, 6)
        self.box_stack = combo(column(host, "TIMEFRAME STACK"), self.var_stack, 14)
        self.box_style = combo(column(host, "STYLE"), self.var_style, 9)

        when = column(host, "DATE AND TIME  ·  NEW YORK", pad=8)
        self.caption_when = when.caption  # type: ignore[attr-defined]
        inner = ttk.Frame(when, style="Panel.TFrame")
        inner.pack(anchor="w")
        self.entry_date = ttk.Entry(inner, textvariable=self.var_date, width=11, font=F(MONO, 12))
        self.entry_date.pack(side="left")
        self.entry_time = ttk.Entry(inner, textvariable=self.var_time, width=6, font=F(MONO, 12))
        self.entry_time.pack(side="left", padx=(S(6), 0))

        steps = column(host, "STEP ONE ENTRY BAR", pad=8)
        inner = ttk.Frame(steps, style="Panel.TFrame")
        inner.pack(anchor="w")
        self.button_back = ttk.Button(inner, text="◀", width=3, style="Step.TButton", takefocus=False, command=lambda: self.step(-1))
        self.button_back.pack(side="left")
        self.button_forward = ttk.Button(inner, text="▶", width=3, style="Step.TButton", takefocus=False, command=lambda: self.step(1))
        self.button_forward.pack(side="left", padx=(S(6), 0))
        self.button_latest = ttk.Button(inner, text="Latest", takefocus=False, command=self.jump_to_latest)
        self.button_latest.pack(side="left", padx=(S(6), 0))
        # live mode only: stop / restart the automatic check at each bar close
        self.button_pause = ttk.Button(inner, text="Pause", takefocus=False, command=self.toggle_pause)

        # custom stack: three more drop-downs, shown only for the "Custom…" choice
        self.custom_row = ttk.Frame(panel, style="Panel.TFrame")
        self.box_bias = combo(column(self.custom_row, "BIAS TIMEFRAME"), self.var_bias, 6)
        self.box_setup = combo(column(self.custom_row, "SETUP TIMEFRAME"), self.var_setup, 6)
        self.box_entry = combo(column(self.custom_row, "ENTRY TIMEFRAME"), self.var_entry, 6)
        self.label_problem = ttk.Label(self.custom_row, text="", style="Problem.TLabel", wraplength=S(560), justify="left")
        self.label_problem.pack(side="left", anchor="s", padx=(S(6), 0), pady=(0, S(6)))

        self.status_row = ttk.Frame(panel, style="Panel.TFrame")
        self.status_row.pack(fill="x", pady=(S(6), 0))
        self.label_status = tk.Label(self.status_row, text="", bg=SURFACE, fg=MUTED, font=F(UI, 9), anchor="w", justify="left")
        self.label_live = tk.Label(self.status_row, text="", bg=SURFACE, fg=MUTED, font=F(UI, 10, "bold"), anchor="e")
        self.label_live.pack(side="right", padx=(S(12), 0))
        self.label_status.pack(side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(panel, mode="determinate", value=0, style="Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(S(3), 0))

        self.box_data.bind("<<ComboboxSelected>>", self._on_data_changed)
        self.box_style.bind("<<ComboboxSelected>>", self._on_stack_changed)
        self.box_symbol.bind("<<ComboboxSelected>>", self._on_symbol_changed)
        self.box_stack.bind("<<ComboboxSelected>>", self._on_stack_changed)
        for box in (self.box_bias, self.box_setup, self.box_entry):
            box.bind("<<ComboboxSelected>>", self._on_stack_changed)
        row.bind("<Configure>", lambda _event: self._reflow_controls())

    def _reflow_controls(self) -> None:
        """One row when it fits; otherwise the selections wrap, so nothing is cut off at the right."""
        row = self._controls_host.master
        room = row.winfo_width() - self.button_check.winfo_reqwidth() - S(16)
        if room < S(100):
            return  # not laid out yet
        columns: list[tk.Widget] = list(self._control_columns)
        self._controls_flow.arrange(columns, [column.winfo_reqwidth() for column in columns], room)

    def _build_summary(self) -> None:
        """Top to bottom: the bias selector; the suggestion beside the steps; the trade plan."""
        self.summary = tk.Frame(self.root, bg=BG)
        self.summary.pack(fill="x", padx=S(18), pady=(S(8), 0))

        # 1. which side to look for
        side = tk.Frame(self.summary, bg=BG)
        side.pack(fill="x")
        tk.Label(side, text="BIAS", font=F(UI, 8, "bold"), fg=MUTED, bg=BG).pack(side="left", padx=(0, S(10)))
        self.var_side = tk.StringVar(value=SIDE_AUTO_VALUE)
        self.side_buttons: dict[str, ttk.Radiobutton] = {}
        for value, label in self.controller.side_choices():
            button = ttk.Radiobutton(
                side, text=f"{SIDE_GLYPH.get(value, '')}{label}", value=value or SIDE_AUTO_VALUE, variable=self.var_side,
                style="Side.Toolbutton", command=self._on_side_changed, takefocus=True, width=8,
            )  # fmt: skip
            button.pack(side="left", padx=(0, S(4)))
            self.side_buttons[value] = button
        self.label_side = tk.Label(side, text="", font=F(UI, 10), fg=MUTED, bg=BG, anchor="w")
        self.label_side.pack(side="left", padx=(S(12), 0))
        self.label_auto = tk.Label(side, text="", font=F(UI, 10, "bold"), fg=WARN, bg=BG, anchor="w")
        self.label_auto.pack(side="left", padx=(S(10), 0))

        # 2. the suggestion with the state of its idea (left), what has to happen (right)
        main = tk.Frame(self.summary, bg=BG)
        main.pack(fill="x", pady=(S(8), 0))
        self._main = main
        main.columnconfigure(0, weight=5, uniform="summary")
        main.columnconfigure(1, weight=7, uniform="summary")
        neutral = tones(LOOK.theme)["neutral"]
        self.banner = tk.Frame(main, bg=neutral[1])
        self.banner.grid(row=0, column=0, sticky="nsew")
        self.stripe = tk.Frame(self.banner, bg=neutral[0], width=S(8))
        self.stripe.pack(side="left", fill="y")
        because = tk.Frame(self.banner, bg=neutral[1])
        because.pack(side="left", fill="both", expand=True, padx=(S(16), S(14)), pady=(S(6), S(10)))
        self.label_decision = tk.Label(because, text="", font=F(UI, 24, "bold"), anchor="w", justify="left", bg=neutral[1], fg=neutral[0])
        self.label_decision.pack(anchor="w", fill="x")
        self.label_state = tk.Label(because, text="", font=F(UI, 11, "bold"), anchor="w", justify="left", bg=neutral[1], fg=TEXT)
        self.label_why = tk.Label(because, text="", font=F(UI, 10), anchor="w", justify="left", bg=neutral[1], fg=MUTED)
        self.label_why.pack(anchor="w", fill="x", pady=(S(4), 0))
        self.label_note = tk.Label(because, text="", font=F(UI, 10), anchor="w", justify="left", bg=neutral[1], fg=WARN)
        # shown only when TradingView cannot be reached: one click to the saved history
        self.button_fallback = ttk.Button(because, text="Use saved history instead", takefocus=False, command=self.use_history)
        self._banner_parts: list[tk.Widget] = [self.banner, because, self.label_decision, self.label_state, self.label_why, self.label_note]
        self._probe = tk.Label(because, font=F(UI, 10), anchor="w", justify="left")  # never shown: measures the reason at its full length
        self.banner.bind("<Configure>", self._on_banner_resized)

        self.steps = tk.Frame(main, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        self.steps.grid(row=0, column=1, sticky="nsew", padx=(S(8), 0))
        head = tk.Frame(self.steps, bg=SURFACE)
        head.pack(fill="x", padx=S(12), pady=(S(7), S(3)))
        tk.Label(head, text="WHAT HAS TO HAPPEN", font=F(UI, 8, "bold"), fg=MUTED, bg=SURFACE).pack(side="left")
        legend = "   ".join(f"{STEP_GLYPH[name]} {name}" for name in ("done", "next", "later", "blocked"))
        tk.Label(head, text=legend, font=F(UI, 9), fg=FAINT, bg=SURFACE).pack(side="right")
        self.step_rows: list[dict[str, tk.Widget]] = []
        for _ in range(MAX_STEPS):
            row = tk.Frame(self.steps, bg=SURFACE)
            mark = tk.Label(row, text="", font=F(UI, 10, "bold"), width=10, anchor="w", bg=SURFACE)
            mark.pack(side="left", anchor="n", padx=(S(8), 0), pady=S(3))
            frame = tk.Label(row, text="", font=F(MONO, 11, "bold"), width=4, anchor="w", bg=SURFACE, fg=TEXT)
            frame.pack(side="left", anchor="n", pady=S(3))
            words = tk.Frame(row, bg=SURFACE)
            words.pack(side="left", fill="x", expand=True, padx=(S(4), S(8)), pady=S(3))
            label = tk.Label(words, text="", font=F(UI, 10), anchor="w", justify="left", bg=SURFACE)
            label.pack(anchor="w", fill="x")
            detail = tk.Label(words, text="", font=F(UI, 11), anchor="w", justify="left", bg=SURFACE, fg=TEXT)
            self.step_rows.append(dict(row=row, mark=mark, frame=frame, words=words, label=label, detail=detail))
        self.label_steps = tk.Label(self.steps, text="", font=F(UI, 10), fg=FAINT, bg=SURFACE, anchor="w", justify="left")
        self.steps.bind("<Configure>", self._on_steps_resized)

        # 3. the trade plan on one line (wrapping onto a second when the window is narrow), with the way to the full checklist at its end
        strip = tk.Frame(self.summary, bg=FIELD, highlightthickness=1, highlightbackground=BORDER)
        strip.pack(fill="x", pady=(S(8), 0))
        self.button_details = ttk.Button(strip, text="", style="Quiet.TButton", takefocus=False, command=self.toggle_details)
        self.button_details.pack(side="right", anchor="n", padx=(S(8), S(10)), pady=S(6))
        self.label_plan = tk.Label(strip, text="", font=F(UI, 10, "bold"), fg=MUTED, bg=FIELD, anchor="w")
        self.label_plan.pack(side="left", anchor="n", padx=(S(14), 0), pady=S(9))
        self.levels = tk.Frame(strip, bg=FIELD)
        self.levels.pack(side="left", fill="x", expand=True, padx=(S(22), 0), pady=S(6))
        self._levels_flow = Flow(self.levels, FIELD, gap=22, row_gap=4)
        self._level_cells: list[tuple[tk.Frame, tk.Label, tk.Label, tk.Label]] = []
        self._cells_shown = 0
        self._strip = strip
        strip.bind("<Configure>", lambda _event: self._reflow_plan())

    def _reflow_plan(self) -> None:
        """Entry, stop, target and the last close side by side; onto a second row rather than under the Details button."""
        cells = self._level_cells[: self._cells_shown]
        room = self._strip.winfo_width() - self.button_details.winfo_reqwidth() - self.label_plan.winfo_reqwidth() - S(14 + 22 + 8 + 10 + 6)
        if room < S(60):
            return  # not laid out yet
        widths = [name.winfo_reqwidth() + S(8) + price.winfo_reqwidth() + S(7) + note.winfo_reqwidth() for _holder, name, price, note in cells]
        self._levels_flow.arrange([holder for holder, _name, _price, _note in cells], widths, room)

    def _build_footer(self) -> None:
        footer = tk.Frame(self.root, bg=BG)
        footer.pack(side="bottom", fill="x", padx=S(18), pady=(S(4), S(8)))
        self.label_source = tk.Label(footer, text="", font=F(UI, 9), fg=MUTED, bg=BG, anchor="w")
        self.label_source.pack(side="left")
        # always on screen: overlays, direction colours, text size and the resets, without knowing about right-click
        self.button_display = ttk.Button(footer, text=f"{GEAR}  Display", style="Gear.TButton", takefocus=True, command=self._open_display_menu)
        self.button_display.pack(side="right", padx=(S(12), 0))
        self.label_hint = tk.Label(footer, text=HINT, font=F(UI, 9), fg=FAINT, bg=BG, anchor="e")
        self.label_hint.pack(side="right")
        self._footer = footer
        footer.bind("<Configure>", lambda _event: self._fit_hint())

    def _fit_hint(self) -> None:
        """The key hints in full when they fit beside the source note, shorter when they do not."""
        room = self._footer.winfo_width() - self.label_source.winfo_reqwidth() - self.button_display.winfo_reqwidth() - S(36)
        font = F(UI, 9)
        text = next((words for words in (HINT, HINT_SHORT) if font.measure(words) <= room), "")
        if self.label_hint.cget("text") != text:
            self.label_hint.configure(text=text)

    def _build_body(self) -> None:
        """The charts, or (behind the Details button) the read in full and the whole checklist."""
        # not a tab stop: it shows no focus ring. (A check still hands it the keyboard, for the arrow keys.)
        self.body = tk.Frame(self.root, bg=BG, takefocus=False, highlightthickness=0)
        self.body.pack(fill="both", expand=True, padx=S(18), pady=(S(8), 0))

        self.charts_frame = tk.Frame(self.body, bg=BG)
        self.charts: list[ChartPane] = []
        for index, role in enumerate(PANE_ROLES):
            pane = ChartPane(self.charts_frame, role, on_menu=self._open_chart_menu, on_zoom=self._on_zoom)
            pane.canvas.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else S(8), 0))
            self.charts_frame.columnconfigure(index, weight=1, uniform="charts")
            self.charts.append(pane)
        self.charts_frame.rowconfigure(0, weight=1)
        self._sync_panes()

        self.details_frame = tk.Frame(self.body, bg=BG)
        filters = tk.Frame(self.details_frame, bg=BG)
        filters.pack(fill="x", pady=(0, S(4)))
        tk.Label(filters, text="DETAILS  ·  the read, then every rule the style checked", font=F(UI, 8, "bold"), fg=MUTED, bg=BG).pack(side="left")
        self.var_hide_advisory = tk.BooleanVar()
        self.var_collapse_inactive = tk.BooleanVar()
        self.var_show_details = tk.BooleanVar()
        for text, variable in (
            ("Show what was observed", self.var_show_details),
            ("Collapse the path not in play", self.var_collapse_inactive),
            ("Hide advisory rows", self.var_hide_advisory),
        ):
            ttk.Checkbutton(filters, text=text, variable=variable, command=self._on_filter_changed, takefocus=False).pack(side="right", padx=(S(14), 0))

        # one scrolling body: the read, the plan, what invalidates, the rule summary, then the checklist
        holder = tk.Frame(self.details_frame, bg=SURFACE)
        holder.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(holder, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.checklist = tk.Text(
            holder, wrap="word", bg=SURFACE, fg=TEXT, font=F(UI, 11), relief="flat", borderwidth=0, highlightthickness=0,
            padx=S(16), pady=S(6), cursor="arrow", insertwidth=0, selectbackground=ACCENT_FILL, selectforeground=WHITE,
            yscrollcommand=scrollbar.set, height=8,
        )  # fmt: skip
        self.checklist.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.checklist.yview)
        self._configure_checklist()
        self.checklist.configure(state="disabled")
        self._show_body()

    def _configure_checklist(self) -> None:
        """The checklist's text styles. Its tab stop and margins come from the measured mark column, so they follow the text size."""
        text = self.checklist
        column = F(MONO, 11, "bold").measure("✗ FAIL") + S(18)
        text.configure(tabs=(str(column),))
        text.tag_configure("note_caption", font=F(UI, 8, "bold"), foreground=MUTED, spacing1=S(10), spacing3=S(2), lmargin1=S(6))
        text.tag_configure("note_body", font=F(UI, 10), foreground=TEXT, lmargin1=S(6), lmargin2=S(6), rmargin=S(10), spacing3=S(2))
        text.tag_configure("legend", font=F(UI, 9), foreground=FAINT, spacing1=S(16), lmargin1=S(6))
        text.tag_configure("group", font=F(UI, 10, "bold"), foreground=TEXT, spacing1=S(14), spacing3=S(5))
        text.tag_configure("group_off", font=F(UI, 10, "bold"), foreground=MUTED, spacing1=S(14), spacing3=S(5))
        text.tag_configure("tally", font=F(UI, 9), foreground=MUTED)
        text.tag_configure("row", lmargin1=S(6), lmargin2=column, spacing1=S(5), spacing3=1)
        text.tag_configure("label", font=F(UI, 11), foreground=TEXT)
        text.tag_configure("label_off", font=F(UI, 11), foreground=MUTED)
        text.tag_configure("tags", font=F(UI, 9), foreground=FAINT)
        text.tag_configure("detail", font=F(UI, 10), foreground=MUTED, lmargin1=column, lmargin2=column, rmargin=S(10), spacing3=S(5))
        text.tag_configure("empty", font=F(UI, 11), foreground=FAINT, spacing1=S(18), lmargin1=S(6))
        for status, colour in _row_colours().items():
            text.tag_configure(f"mark_{status}", font=F(MONO, 11, "bold"), foreground=colour)

    def _show_body(self) -> None:
        if self._details_open:
            self.charts_frame.pack_forget()
            self.details_frame.pack(fill="both", expand=True)
            self.button_details.configure(text="◂  Back to charts")
        else:
            self.details_frame.pack_forget()
            self.charts_frame.pack(fill="both", expand=True)
            self.button_details.configure(text="Details  ▸")

    # --- selections <-> widgets ---

    def _load_selections(self) -> None:
        controller, state = self.controller, self.controller.state
        self.box_data.configure(values=controller.data_choices())
        self.var_data.set(controller.data_label())
        self.box_symbol.configure(values=controller.symbols())
        self.box_stack.configure(values=controller.stack_choices())
        self.box_style.configure(values=controller.style_choices())
        frames = controller.timeframe_choices()
        for box in (self.box_bias, self.box_setup, self.box_entry):
            box.configure(values=frames)
        self.var_symbol.set(state.symbol)
        self.var_stack.set(state.stack)
        self.var_style.set(state.style)
        self.var_bias.set(state.custom_bias)
        self.var_setup.set(state.custom_setup)
        self.var_entry.set(state.custom_entry)
        self._show_when(state.when)
        self.var_hide_advisory.set(state.hide_advisory)
        self.var_collapse_inactive.set(state.collapse_inactive)
        self.var_show_details.set(state.show_details)
        self.var_side.set(state.direction or SIDE_AUTO_VALUE)
        self._paint_side()
        self.label_source.configure(text=controller.source_note())
        self._refresh_custom_row()
        self._apply_mode()

    def _apply_mode(self) -> None:
        """Live: the time is TradingView's, so its boxes only display it (and look it). Saved history: they are typed in."""
        live = self.controller.is_live
        for entry in (self.entry_date, self.entry_time):
            entry.configure(state="readonly" if live else "normal", cursor="arrow" if live else "xterm", takefocus=not live)
        self.caption_when.configure(text="LAST CLOSED BAR  ·  NEW YORK  ·  read-only" if live else "DATE AND TIME  ·  NEW YORK")
        if live:
            self.button_pause.pack(side="left", padx=(S(6), 0))
            self.button_pause.configure(text="Pause" if self.controller.state.auto_refresh else "Resume")
        else:
            self.button_pause.pack_forget()
            self.label_live.configure(text="")
        self.label_source.configure(text=self.controller.source_note())
        self._controls_flow.forget()
        self.root.after_idle(self._reflow_controls)

    def _read_selections(self) -> None:
        state = self.controller.state
        state.symbol = self.var_symbol.get()
        state.stack = self.var_stack.get()
        state.style = self.var_style.get()
        state.custom_bias = self.var_bias.get()
        state.custom_setup = self.var_setup.get()
        state.custom_entry = self.var_entry.get()
        if not self.controller.is_live:  # live: the time comes from TradingView, not from the boxes
            state.when = f"{self.var_date.get().strip()} {self.var_time.get().strip()}".strip()
        state.hide_advisory = self.var_hide_advisory.get()
        state.collapse_inactive = self.var_collapse_inactive.get()
        state.show_details = self.var_show_details.get()

    def _show_when(self, when: str) -> None:
        if self.controller.is_live and self.controller.live_time is None:
            when = ""  # nothing read from TradingView yet: no bar time to show
        date, _, clock = when.partition(" ")
        self.var_date.set(date)
        self.var_time.set(clock)

    def _refresh_custom_row(self) -> None:
        if self.var_stack.get() == CUSTOM_CHOICE:
            self.custom_row.pack(fill="x", pady=(S(12), 0), before=self.status_row)
            self.label_problem.configure(text=self.controller.stack_problem())
        else:
            self.custom_row.pack_forget()

    # --- display options ---

    def _screen_size(self) -> tuple[int, int]:
        return self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _apply_minsize(self) -> tuple[int, int]:
        """The smallest window that holds everything at the current Windows scaling and text size."""
        least = min_window(LOOK.scale, self._screen_size())
        self.root.minsize(*least)
        return least

    # --- a window the screen keeps short: the charts keep a drawable height ---

    def _on_window_resized(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if event.widget is self.root:
            self._schedule_fit()

    def _schedule_fit(self) -> None:
        if self._fit_job is None and not self._closed:
            self._fit_job = self.root.after(30, self._fit_height)

    def _cut_width(self, lines: int, room: int) -> float:
        """The width the reason is cut to, to take at most ``lines`` wrapped lines of ``room`` pixels."""
        return room - S(4) if lines <= 1 else 0.9 * lines * room

    def _banner_height(self, lines: int | None) -> int:
        """The banner's height with the reason and the note in full (``None``) or cut to ``lines`` lines and one line,
        whichever way they are shown now."""
        height = self.banner.winfo_reqheight()
        room, font = int(self.label_why.cget("wraplength")), F(UI, 10)
        for label, words, width in ((self.label_why, self._why, self._cut_width(lines or 1, room)), (self.label_note, self._note, self._cut_width(1, room))):
            if words:
                self._probe.configure(text=words if lines is None else _cut(words, font, width), wraplength=room)
                height += self._probe.winfo_reqheight() - label.winfo_reqheight()
        return height

    def _steps_height(self, compact: bool) -> int:
        """The steps panel's height with every step listed, or folded (``compact``), whichever way it is shown now."""
        height = self.steps.winfo_reqheight()
        if compact == self._compact:
            return height
        fold = F(UI, 10).metrics("linespace") + S(2) + S(6)  # the line that counts the folded steps
        if self._compact:  # folded now: what the full list would add
            return height + sum(row.winfo_reqheight() + 1 for row in self._folded) - (fold if self._folded else 0)
        view = self._steps_shown[0]
        steps = list(view.steps)[:MAX_STEPS] if view is not None else []
        hidden = [self.step_rows[index]["row"] for index, step in enumerate(steps) if step.status not in ("next", "blocked")]
        return height - sum(row.winfo_reqheight() + 1 for row in hidden) + (fold if hidden else 0)

    def _fit_height(self) -> None:
        """Reserve the charts their least drawable height.

        When the screen caps the window below what the text size was designed for, the
        regions above the charts give way first: the steps fold to the next one (and any
        blocked one) with a count of the rest, and the reason is cut to two lines, or to
        one when two are still too many. Everything is decided from what each layout
        would need, not from the one on screen, so the choice does not flip.
        """
        self._fit_job = None
        if self._closed:
            return
        self.root.update_idletasks()
        window = self.root.winfo_height()
        if window < S(200) or not self.charts:
            return  # not on screen yet
        row_full = max(self._banner_height(None), self._steps_height(False))
        others = window - self.body.winfo_height() - self._main.winfo_reqheight() + row_full
        reserve = self.charts[0].min_height() + S(2)
        compact, lines = needs_compact(window, others, reserve), 2
        if compact:
            row_two = max(self._banner_height(2), self._steps_height(True))
            if needs_compact(window, others - row_full + row_two, reserve):
                lines = 1
        if (compact, lines) == (self._compact, self._why_lines):
            return
        self._compact, self._why_lines = compact, lines
        self._paint_steps(*self._steps_shown)
        self._wrap_banner(self.banner.winfo_width())

    def _sync_panes(self) -> None:
        """Hand each chart the overlays and its remembered zoom."""
        overlays = self.controller.overlays()
        for pane in self.charts:
            pane.overlays = dict(overlays)
            pane.bars = self.controller.chart_bars(pane.role)

    def _sync_option_vars(self) -> None:
        state = self.controller.state
        self.var_text_size.set(state.text_size)
        self.var_scheme.set(state.colours)
        for name, shown in self.controller.overlays().items():
            self.var_overlays[name].set(shown)

    def build_menu(self, pane: ChartPane | None = None) -> tk.Menu:
        """The display options (``display.display_menu``): for ``pane`` (right-click on a chart, or its gear), or the footer's."""
        self._sync_option_vars()
        if self._menu is not None:
            self._menu.destroy()
        # every colour is set here: the system's menu colours are not readable on the dark window
        menu = tk.Menu(
            self.root, tearoff=0, bg=FIELD, fg=TEXT, activebackground=ACCENT_FILL, activeforeground=WHITE, disabledforeground=MUTED,
            selectcolor=TEXT, font=F(UI, 10), bd=1, activeborderwidth=S(3), relief="flat",
        )  # fmt: skip
        self._menu = menu
        commands: dict[str, Callable[[], None]] = {
            "reset_zoom_chart": lambda: self._reset_zoom(pane.role if pane is not None else None),
            "reset_zoom_all": lambda: self._reset_zoom(None),
            "reset_display": self._reset_display,
        }
        for item in display_menu(pane is not None, available_text_sizes(LOOK.dpi, self._screen_size())):
            if item.kind == "separator":
                menu.add_separator()
            elif item.kind == "heading":
                # a caption, not a choice: it does not light up. (A disabled entry is drawn embossed on Windows, which blurs it.)
                menu.add_command(label=item.label, font=F(UI, 8, "bold"), foreground=MUTED, activeforeground=MUTED, activebackground=FIELD)
            elif item.kind == "overlay":
                menu.add_checkbutton(label=item.label, variable=self.var_overlays[item.value], command=lambda name=item.value: self._on_overlay(name))
            elif item.kind == "scheme":
                menu.add_radiobutton(label=item.label, value=item.value, variable=self.var_scheme, command=self._on_scheme)
            elif item.kind == "text_size" and item.enabled:
                menu.add_radiobutton(
                    label=item.label, value=item.value, variable=self.var_text_size, command=lambda: self._set_text_size(self.var_text_size.get())
                )
            elif item.kind == "text_size":
                # a size this screen has no room for: listed with the reason, and it cannot be chosen (drawn like a heading, for the same reason)
                menu.add_command(label=item.label, foreground=FAINT, activeforeground=FAINT, activebackground=FIELD)
            else:
                menu.add_command(label=item.label, accelerator=item.accelerator, command=commands[item.value])
        return menu

    def _popup(self, menu: tk.Menu, x: int, y: int) -> None:
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _open_chart_menu(self, pane: ChartPane, x: int, y: int) -> None:
        self._popup(self.build_menu(pane), x, y)

    def _open_display_menu(self) -> None:
        """Above the footer's button, and ending inside the window: the button sits at the window's right edge."""
        button, root = self.button_display, self.root
        menu = self.build_menu(None)
        root.update_idletasks()
        box = (button.winfo_rootx(), button.winfo_rooty(), button.winfo_rootx() + button.winfo_width(), button.winfo_rooty() + button.winfo_height())
        # the system draws the menu wider and taller than Tk asks for: by its frame, and the margins round the marks
        size = (menu.winfo_reqwidth() + LOOK.dpx(18) + S(8), menu.winfo_reqheight() + LOOK.dpx(4))
        self._popup(menu, *menu_origin(box, size, (root.winfo_rootx(), root.winfo_rootx() + root.winfo_width()), S(2)))

    def _on_overlay(self, name: str) -> None:
        self.controller.set_overlay(name, self.var_overlays[name].get())
        self.controller.save()
        self._sync_panes()
        for pane in self.charts:
            pane.draw()

    def _on_scheme(self) -> None:
        self.controller.set_colours(self.var_scheme.get())
        self.controller.save()
        LOOK.set_scheme(self.controller.state.colours)
        self._configure_checklist()
        self._repaint()

    def _on_control_key(self, event: tk.Event) -> str | None:  # type: ignore[type-arg]
        """Ctrl with = / + bigger text, - smaller, 0 normal: on a chart, in a box, anywhere."""
        action = key_action(str(event.keysym), True, False)
        if action == "text_bigger":
            return self._step_text_size(1)
        if action == "text_smaller":
            return self._step_text_size(-1)
        if action == "text_normal":
            return self._set_text_size("normal")
        return None

    def _set_text_size(self, size: str) -> str:
        """The size asked for, or the largest under it that this screen has room for."""
        self.controller.set_text_size(size)
        wanted = self.controller.state.text_size
        self.controller.set_text_size(fit_text_size(wanted, LOOK.dpi, self._screen_size()))
        self._apply_text_size()
        if self.controller.state.text_size != wanted:
            self._set_status("That text size does not fit this screen: the largest that does is used.", WARN)
        return "break"

    def _step_text_size(self, direction: int) -> str:
        current = self.controller.state.text_size
        target = step_text_size(current, direction, LOOK.dpi, self._screen_size())
        self.controller.set_text_size(target)
        self._apply_text_size()
        if direction > 0 and target == current and any(available_text_sizes(LOOK.dpi, self._screen_size()).values()):
            self._set_status("Larger text does not fit this screen.", WARN)
        return "break"

    def _apply_text_size(self) -> None:
        """A new text size, now: the shared fonts change, and everything measured from them is laid out again."""
        self.controller.save()
        if text_scale(self.controller.state.text_size) == LOOK.text:
            return
        LOOK.set_text(self.controller.state.text_size)
        _apply_theme(self.root)
        self._configure_checklist()
        self._apply_minsize()
        self._controls_flow.forget()
        self._levels_flow.forget()
        self._repaint()
        self.root.after_idle(self._relayout)

    def _relayout(self) -> None:
        if self._closed:
            return
        self._reflow_controls()
        self._reflow_plan()
        self._fit_hint()
        self._wrap_banner(self.banner.winfo_width())
        self._wrap_steps(self.steps.winfo_width())
        self._schedule_fit()

    def _on_zoom(self, role: str, bars: int) -> None:
        self.controller.set_chart_bars(role, bars)
        self.controller.save()

    def _reset_zoom(self, role: str | None = None) -> None:
        self.controller.reset_zoom(role)
        self.controller.save()
        self._sync_panes()
        for pane in self.charts:
            pane.draw()

    def _reset_display(self) -> None:
        self.controller.reset_display()
        self.controller.save()
        self._sync_panes()
        LOOK.set_scheme(self.controller.state.colours)
        self._configure_checklist()
        if text_scale(self.controller.state.text_size) != LOOK.text:
            self._apply_text_size()
        else:
            self._repaint()

    def _repaint(self) -> None:
        """Paint what is on screen again (after a colour or size change), whatever it is."""
        if self._screen[0] == "outcome" and self._outcome is not None:
            self._render_outcome()
        elif self._screen[0] == "problem":
            self._show_problem(str(self._screen[1]), bool(self._screen[2]))
        else:
            status, colour = self.label_status.cget("text"), self.label_status.cget("fg")
            self._show_idle()
            self._set_status(status, colour)

    # --- events ---

    def _on_stack_changed(self, _event: object = None) -> None:
        self._read_selections()
        self._refresh_custom_row()
        self._restart_live()

    def _restart_live(self) -> None:
        """Live: a new symbol, stack or style is read straight away, from "now"."""
        if not self.controller.is_live:
            return
        self.controller.selection_changed()
        self._good = None
        self.check()  # not "auto": it must queue behind a check that is still running

    def _on_side_changed(self) -> None:
        """Auto / Long / Short was picked: remember it and read the same moment again for that side."""
        self._read_selections()
        self.controller.set_direction(self.var_side.get())
        self.controller.save()
        self._paint_side()
        self._good = None  # a kept live verdict was for the other side
        if self.controller.is_live or self._shown is not None:
            self.check()

    def _on_side_key(self, event: tk.Event, side: str) -> str | None:  # type: ignore[type-arg]
        if self._widget_class(event) in ("TEntry", "Entry", "Listbox", "TCombobox"):
            return None
        self.var_side.set(side or SIDE_AUTO_VALUE)
        self._on_side_changed()
        return "break"

    def _on_data_changed(self, _event: object = None) -> None:
        self._read_selections()
        controller = self.controller
        controller.set_data(self.var_data.get())
        self.box_symbol.configure(values=controller.symbols())
        self.var_symbol.set(controller.state.symbol)
        self._show_when(controller.state.when)
        self._good = self._shown = self._outcome = None
        self._pending = None
        self._sequence += 1  # a check still running belongs to the other mode: its result is dropped
        self._apply_mode()
        controller.save()
        self._show_idle()
        if controller.is_live:
            self.check()

    def use_history(self) -> None:
        """The button under a "TradingView is not reachable" message."""
        self.var_data.set(self.controller.data_choices()[-1])
        self.controller.set_data(DATA_HISTORY)
        self.var_data.set(self.controller.data_label())
        self._on_data_changed()

    def toggle_pause(self) -> None:
        controller = self.controller
        controller.set_auto_refresh(not controller.state.auto_refresh)
        self.button_pause.configure(text="Pause" if controller.state.auto_refresh else "Resume")
        controller.save()
        self._tick_live(reschedule=False)

    def _on_symbol_changed(self, _event: object = None) -> None:
        self._read_selections()
        controller = self.controller
        if controller.is_live:
            self._restart_live()
            return
        covered = controller.coverage(controller.state.symbol)
        try:
            if covered is not None and not covered[0] <= parse_when(controller.state.when) <= covered[1]:
                self._show_when(controller.jump_to_latest())
        except UserError:
            pass

    def _on_filter_changed(self) -> None:
        self._read_selections()
        self._collapsed.clear()
        self.controller.save()
        self._render_outcome()

    def _on_enter(self, event: tk.Event) -> str | None:  # type: ignore[type-arg]
        if self._widget_class(event) == "Listbox":  # choosing in an open drop-down
            return None
        self.check()
        return "break"

    def _on_arrow(self, event: tk.Event, direction: int) -> str | None:  # type: ignore[type-arg]
        if self._widget_class(event) in ("TEntry", "Entry", "Listbox"):  # the caret needs the arrows there
            return None
        self.step(direction)
        return "break"

    def _on_details_key(self, event: tk.Event) -> str | None:  # type: ignore[type-arg]
        if self._widget_class(event) in ("TEntry", "Entry", "Listbox", "TCombobox"):
            return None
        self.toggle_details()
        return "break"

    @staticmethod
    def _widget_class(event: tk.Event) -> str:  # type: ignore[type-arg]
        try:
            return str(event.widget.winfo_class())
        except (AttributeError, tk.TclError):
            return ""

    # --- actions ---

    def check(self, auto: bool = False) -> None:
        """Run the check the selections describe, off the UI thread.

        ``auto`` is the live mode checking by itself: it takes no focus, and it waits its
        turn rather than queueing behind a check that is still running.
        """
        if auto and self._busy:
            return
        self._read_selections()
        self._refresh_custom_row()
        try:
            request = self.controller.build_request()
        except UserError as error:
            self.controller.due = None  # nothing to retry until the selection changes
            self._show_problem(str(error))
            return
        self._show_when(self.controller.state.when)
        if not auto:
            self.controller.save()
        self._sequence += 1
        job = (self._sequence, request)
        if self._busy:
            self._pending = job  # the newest request wins; the one running is discarded
        else:
            self._launch(job)
        if not auto:
            self.body.focus_set()  # so the arrow keys step time straight away

    def step(self, direction: int) -> None:
        """Move one entry-timeframe bar and check again."""
        self._read_selections()
        try:
            when = self.controller.step(direction)
        except UserError as error:
            self._set_status(str(error), WARN)
            return
        self._show_when(when)
        self.check()

    def jump_to_latest(self) -> None:
        self._read_selections()
        self._show_when(self.controller.jump_to_latest())
        self.check()

    def toggle_details(self) -> None:
        self._details_open = not self._details_open
        if self._details_open and self._details_stale:
            self._paint_checklist(self._view)
        self._show_body()

    def _launch(self, job: tuple[int, CheckRequest]) -> None:
        self._busy = True
        request = job[1]
        when = request.when.strftime("%Y-%m-%d %H:%M")
        if request.live and self.controller.will_load(request):
            self._set_status(f"Reading {request.symbol} from TradingView. The first read of a symbol takes a few seconds…", TEXT)
        elif request.live and request.follow:
            self._set_status(f"Reading the latest {request.stack.entry} bar of {request.symbol} from TradingView…", MUTED)
        elif self.controller.will_load(request):
            self._set_status(f"Loading {request.symbol} history. The first check of a symbol takes a few seconds…", TEXT)
        else:
            self._set_status(f"Checking {request.symbol} at {when}…", MUTED)
        self.button_check.configure(text="Checking…")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        threading.Thread(target=self._work, args=job, name="companion-check", daemon=True).start()

    def _work(self, sequence: int, request: CheckRequest) -> None:
        self._results.put((sequence, self.controller.run_check(request)))

    def _poll(self) -> None:
        if self._closed:
            return
        try:
            while True:
                sequence, outcome = self._results.get_nowait()
                self._busy = False
                if self._pending is not None:
                    job, self._pending = self._pending, None
                    self._launch(job)
                    continue
                self.progress.stop()
                self.progress.configure(mode="determinate", value=0)
                self.button_check.configure(text="Check")
                if sequence != self._sequence or outcome.request.live != self.controller.is_live:
                    continue  # asked before the data source was switched
                self.controller.accept(outcome)
                if outcome.request.live:
                    self._show_when(self.controller.state.when)
                self._outcome = outcome
                self._render_outcome()
                self._tick_live(reschedule=False)
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self._poll)

    def _tick_live(self, reschedule: bool = True) -> None:
        """Twice a second: the live line, the stale mark, and the automatic check when a bar has closed."""
        if self._closed:
            return
        controller = self.controller
        if controller.is_live:
            status = controller.live_status(self._shown)
            mark, colour = LIVE_LOOK.get(status.state, ("", MUTED))
            colour = {"": LOOK.theme.up, "waiting": LOOK.theme.waiting}.get(colour, colour)
            self.label_live.configure(text=f"{mark}  {status.text}" if status.text else "", fg=colour)
            if self._shown is not None and status.stale != self._stale_drawn:
                self._render_outcome()  # a verdict that has gone stale must stop looking current
            if controller.should_refresh() and not self._busy:
                self.check(auto=True)
        if reschedule:
            self.root.after(LIVE_TICK_MS, self._tick_live)

    def close(self) -> None:
        self._closed = True
        self._read_selections()
        self.controller.state.geometry = self.root.geometry()
        self.controller.save()
        self.controller.shutdown()
        self.root.destroy()

    # --- drawing ---

    def _set_status(self, text: str, colour: str = MUTED) -> None:
        self.label_status.configure(text=text, fg=colour)

    def _paint_banner(self, tone: str, word: str, why: str, state: str = "", alert: bool = False, note: str = "") -> None:
        """The suggestion, the state of its idea right under it, then why."""
        families = tones(LOOK.theme)
        colour, background = families.get(tone, families["neutral"])
        for widget in self._banner_parts:
            widget.configure(bg=background)
        self.stripe.configure(bg=colour)
        glyph = TONE_GLYPH.get(tone, "")
        self.label_decision.configure(text=f"{glyph}  {word}" if glyph else word, fg=colour)
        self.label_state.configure(text=f"⚠  {state}" if alert and state else state, fg=WARN if alert else TEXT)
        self.label_state.pack_forget()
        if state:
            self.label_state.pack(anchor="w", fill="x", pady=(S(2), 0), before=self.label_why)
        self._why, self._note = why, note
        self.label_note.pack_forget()
        if note:
            self.label_note.pack(anchor="w", fill="x", pady=(S(4), 0), after=self.label_why)
        self._wrap_banner(self.banner.winfo_width())
        self._schedule_fit()

    def _wrap_banner(self, width: int) -> None:
        """Wrap the banner's lines to its width. Compact (a short screen): the reason in two lines or one, the note in one."""
        room = max(S(260), width - S(8 + 30 + 8))
        for label in (self.label_decision, self.label_state, self.label_why, self.label_note):
            label.configure(wraplength=room)
        font = F(UI, 10)
        self.label_why.configure(text=_cut(self._why, font, self._cut_width(self._why_lines, room)) if self._compact else self._why)
        self.label_note.configure(text=_cut(self._note, font, self._cut_width(1, room)) if self._compact else self._note)

    def _on_banner_resized(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._wrap_banner(event.width)

    def _paint_side(self, view: VerdictView | None = None) -> None:
        """The bias selector's caption: what the chosen side means, and what Auto reads when it differs."""
        side = self.controller.state.direction
        self.var_side.set(side or SIDE_AUTO_VALUE)
        self.label_side.configure(text=SIDE_HELP.get(side, ""))
        self.label_auto.configure(text=view.auto_note if view is not None else "")

    def _wrap_steps(self, width: int) -> None:
        first = self.step_rows[0]
        fixed = first["mark"].winfo_reqwidth() + first["frame"].winfo_reqwidth() + S(8 + 4 + 8 + 8 + 22)
        wrap = max(S(220), width - fixed)
        for widgets in self.step_rows:
            widgets["label"].configure(wraplength=wrap)  # type: ignore[call-arg]
            widgets["detail"].configure(wraplength=wrap)  # type: ignore[call-arg]
        self.label_steps.configure(wraplength=max(S(220), width - S(30)))

    def _on_steps_resized(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._wrap_steps(event.width)

    def _paint_steps(self, view: VerdictView | None, message: str = "", stale: bool = False) -> None:
        """One row per step. The next one is the row the eye should land on: tinted, larger, with its condition.

        On a stale verdict nothing is "next" any more: the row loses its tint and its colour.
        Compact (a screen that keeps the window short): only the next step and a blocked
        one are listed; the others are counted on one line.
        """
        self._steps_shown = (view, message, stale)
        rows = list(view.steps)[:MAX_STEPS] if view is not None else []
        colours = _step_colours()
        folded: dict[str, int] = {}
        self._folded = []
        for index, widgets in enumerate(self.step_rows):
            holder = widgets["row"]
            holder.pack_forget()
            if index >= len(rows):
                continue
            step = rows[index]
            upcoming = step.status == "next"
            background = NEXT_BG if upcoming and not stale else SURFACE
            colour = MUTED if stale else colours.get(step.status, FAINT)
            for name in ("row", "mark", "frame", "words", "label", "detail"):
                widgets[name].configure(bg=background)  # type: ignore[call-arg]
            word = step.word.upper() if upcoming and not stale else step.word
            widgets["mark"].configure(text=f"{STEP_GLYPH.get(step.status, '')}  {word}", fg=colour)  # type: ignore[call-arg]
            widgets["frame"].configure(text=step.timeframe, fg=TEXT if step.status != "later" and not stale else FAINT)  # type: ignore[call-arg]
            detail = widgets["detail"]
            detail.pack_forget()
            if upcoming:
                widgets["label"].configure(text=step.label, font=F(UI, 10, "bold"), fg=MUTED if stale else LOOK.theme.waiting)  # type: ignore[call-arg]
                if step.detail:
                    detail.configure(text=step.detail, fg=MUTED if stale else TEXT)  # type: ignore[call-arg]
                    detail.pack(anchor="w", fill="x")
            else:
                text = f"{step.label}  —  {step.detail}" if step.detail else step.label
                shade = {"done": MUTED, "blocked": TEXT}.get(step.status, FAINT)
                widgets["label"].configure(text=text, font=F(UI, 10), fg=MUTED if stale else shade)  # type: ignore[call-arg]
            if self._compact and step.status not in ("next", "blocked"):
                folded[step.status] = folded.get(step.status, 0) + 1
                self._folded.append(holder)
                continue
            holder.pack(fill="x", padx=S(4), pady=(0, 1))
        self.label_steps.pack_forget()
        if folded:
            counts = "   ".join(f"{STEP_GLYPH.get(name, '')} {count} {name}" for name, count in folded.items())
            self.label_steps.configure(text=f"{counts}   ·   listed in full in a taller window")
            self.label_steps.pack(fill="x", padx=S(14), pady=(S(2), S(6)))
        elif not rows:
            if view is None:
                text = message or "The steps appear here after a check: what has to happen, highest timeframe first."
            else:
                text = "This style gives no steps."
            self.label_steps.configure(text=text)
            self.label_steps.pack(fill="x", padx=S(14), pady=(S(4), S(10)))
        self._wrap_steps(self.steps.winfo_width())
        self._schedule_fit()

    def _paint_plan(self, view: VerdictView | None, stale: bool = False) -> None:
        """Entry, stop and target on one line; planned levels are said to be planned, stale ones to be stale."""
        plan = view.plan if view is not None else None
        cells: list[tuple[str, str, str, bool]] = []
        if plan is not None:
            title = f"{'▲' if plan.direction == 'long' else '▼'}  {plan.title}"
            colour = TEXT if plan.state == "triggered" else LOOK.theme.waiting
            self.label_plan.configure(text=f"STALE  ·  {title}" if stale else title, fg=MUTED if stale else colour)
            cells = [(level.name.upper(), level.price, level.note, True) for level in plan.levels]
        elif view is not None:
            self.label_plan.configure(text="NO TRADE PLAN YET  ·  the steps come first", fg=MUTED)
        else:
            self.label_plan.configure(text="TRADE PLAN", fg=MUTED)
        if view is not None and view.last is not None:
            cells.append(("LAST CLOSE", view.last.price, "", False))
        while len(self._level_cells) < len(cells):  # the labels are kept and re-used: stepping only changes their text
            holder = tk.Frame(self.levels, bg=FIELD)
            name = tk.Label(holder, font=F(UI, 8, "bold"), fg=MUTED, bg=FIELD)
            name.pack(side="left", pady=(S(4), 0))
            price = tk.Label(holder, bg=FIELD)
            price.pack(side="left", padx=(S(8), 0))
            note = tk.Label(holder, font=F(UI, 9), fg=MUTED, bg=FIELD)
            note.pack(side="left", padx=(S(7), 0), pady=(S(4), 0))
            self._level_cells.append((holder, name, price, note))
        for index, (_holder, name, price, note) in enumerate(self._level_cells[: len(cells)]):
            caption, value, remark, strong = cells[index]
            name.configure(text=caption)
            price.configure(text=value, font=F(MONO, 14 if strong else 12, "bold"), fg=TEXT if strong and not stale else MUTED)
            note.configure(text=remark)
        self._cells_shown = len(cells)
        self._levels_flow.forget()
        self._reflow_plan()

    def _paint_charts(self, view: VerdictView | None, message: str = "", stale: bool = False) -> None:
        charts = list(view.charts) if view is not None else []
        problem = view.chart_problem if view is not None else ""
        for index, pane in enumerate(self.charts):
            pane.show(charts[index] if index < len(charts) else None, problem or message, stale)

    def _offer_history(self, offered: bool) -> None:
        self.button_fallback.pack_forget()
        if offered:
            self.button_fallback.pack(anchor="w", pady=(S(6), 0))

    def _show_idle(self) -> None:
        self._screen = ("idle",)
        self._offer_history(False)
        if self.controller.is_live:
            self._paint_banner("neutral", "LIVE", "Reading TradingView. The verdict appears here and refreshes each time an entry bar closes.")
        else:
            self._paint_banner("neutral", "READY", "Pick a symbol, a stack and a New York time, then press Check.")
        self._paint_side()
        self._paint_steps(None)
        self._paint_plan(None)
        self._paint_charts(None)
        self._paint_checklist(None)
        self._set_status("Ready.")

    def _show_problem(self, message: str, offer_history: bool = False) -> None:
        """A request that cannot run, or a check that failed: say so, show no stale verdict."""
        self._screen = ("problem", message, offer_history)
        self._outcome = None
        self._shown = None
        self._view = None
        self._paint_banner("neutral", "NO LIVE DATA" if offer_history else "NO RESULT", message)
        self._offer_history(offer_history)
        self._paint_side()
        self._paint_steps(None, "No steps: the check did not run.")
        self._paint_plan(None)
        self._paint_charts(None, "No charts: the check did not run.")
        self._paint_checklist(None)
        self._set_status("Not checked. The reason is shown below.", ERROR)

    def _render_outcome(self) -> None:
        outcome = self._outcome
        if outcome is None:
            return
        trouble = ""
        if outcome.verdict is None:
            good = self._good
            same = good is not None and (good.request.symbol, good.request.stack, good.request.style, good.request.direction) == (
                outcome.request.symbol, outcome.request.stack, outcome.request.style, outcome.request.direction,
            )  # fmt: skip
            if not (outcome.problem and outcome.retry and same and self.controller.is_live):
                self._show_problem(outcome.error, outcome.offer_history)
                return
            # a live refresh failed: the last verdict stays, marked stale, with the reason
            trouble, shown = outcome.error, good
        else:
            shown = outcome
            self._good = outcome if outcome.request.live and outcome.request.follow else self._good
        assert shown is not None
        self._screen = ("outcome",)
        self._shown = shown
        view = self.controller.present(shown, self._collapsed)
        self._view = view
        why = view.why or view.summary or "The style gave no reason."
        status = self.controller.live_status(shown)
        self._stale_drawn = status.stale
        self._offer_history(bool(trouble) and outcome.offer_history)
        stale = bool(status.stale and shown.request.follow)  # not a current read: nothing below may look current
        if stale:
            closed = shown.data_time.strftime("%H:%M") if shown.data_time is not None else "?"
            note = trouble or f"Stale: the last bar TradingView sent closed at {closed}. This is not a current read."
            self._paint_banner("neutral", f"STALE  ·  {view.suggestion}", why, view.idea_state, view.idea_alert, note)
        elif shown.request.live and not shown.request.follow:
            note = "  ".join((*view.notes, "Looking back at an earlier bar: this is not now. Latest returns to live."))
            self._paint_banner(view.suggestion_tone, view.suggestion, why, view.idea_state, view.idea_alert, note)
        else:
            self._paint_banner(view.suggestion_tone, view.suggestion, why, view.idea_state, view.idea_alert, "  ".join(view.notes))
        self._paint_side(view)
        self._paint_steps(view, stale=stale)
        self._paint_plan(view, stale)
        self._paint_charts(view, stale=stale)
        self._paint_checklist(view)
        self.label_source.configure(text=view.source_note)
        if trouble:
            self._set_status("TradingView could not be read just now. The last result is kept, marked stale.", WARN)
        else:
            self._set_status(f"Checked {view.headline}.")

    def _toggle_group(self, name: str) -> None:
        if self._view is None:
            return
        for group in self._view.groups:
            if group.name == name:
                self._collapsed[name] = not group.collapsed
        self._render_outcome()

    def _paint_checklist(self, view: VerdictView | None) -> None:
        self._details_stale = not self._details_open
        if self._details_stale:
            return  # painted when Details is opened; keeps stepping quick
        text = self.checklist
        position = text.yview()[0]
        text.configure(state="normal")
        text.delete("1.0", "end")
        for tag in text.tag_names():
            if tag.startswith("toggle:"):
                text.tag_delete(tag)
        if view is None:
            text.insert("end", "The read and the checklist appear here after a check.\n", ("empty",))
            text.configure(state="disabled")
            return
        # the read in full sentences, the plan's note, what invalidates, the rule summary: the same scrolling body
        read = "\n".join(f"{row.timeframe}   {READ_GLYPH.get(row.status, '')} {row.word}:  {row.headline}.  {row.reason}".rstrip() for row in view.read)
        plan = view.plan.note if view.plan is not None else ""
        for name, body in (("TOP-DOWN READ", read), ("PLAN", plan), ("INVALIDATION", view.invalidation), ("RULE SUMMARY", view.summary)):
            if body:
                text.insert("end", name + "\n", ("note_caption",))
                text.insert("end", body + "\n", ("note_body",))
        legend = "CHECKLIST    ✓ passed    ✗ failed    – not evaluated"
        if view.hidden_advisory:
            legend += f"    ·    {view.hidden_advisory} advisory hidden"
        text.insert("end", legend + "\n", ("legend",))
        details = self.controller.state.show_details
        for group in view.groups:
            toggle = f"toggle:{group.name}"
            header = "group" if group.active else "group_off"
            text.insert("end", f"{'▸' if group.collapsed else '▾'}  {group.title}", (header, toggle))
            suffix = f"     {group.tally}" + ("" if group.active else "   ·   not the path in play")
            text.insert("end", suffix + "\n", (header, "tally", toggle))
            text.tag_bind(toggle, "<Button-1>", lambda _event, name=group.name: self._toggle_group(name))
            text.tag_bind(toggle, "<Enter>", lambda _event: text.configure(cursor="hand2"))
            text.tag_bind(toggle, "<Leave>", lambda _event: text.configure(cursor="arrow"))
            if group.collapsed:
                continue
            for row in group.rows:
                text.insert("end", f"{STATUS_GLYPH[row.status]} {row.mark}\t", ("row", f"mark_{row.status}"))
                text.insert("end", row.label, ("row", "label" if group.active else "label_off"))
                text.insert("end", f"     {row.tags}\n" if row.tags else "\n", ("row", "tags"))
                if details and row.detail:
                    text.insert("end", row.detail + "\n", ("detail",))
        text.configure(state="disabled")
        text.yview_moveto(position)


def _enable_sharp_text() -> None:
    """Ask Windows not to bitmap-scale the window on high-DPI screens."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _darken_title_bar(root: tk.Tk) -> None:
    """Match the Windows title bar to the dark window (Windows 10 2004 and later)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        root.update_idletasks()
        handle = int(root.wm_frame(), 16)
        flag = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(handle, 20, ctypes.byref(flag), ctypes.sizeof(flag))
    except Exception:
        pass


def main() -> int:
    _enable_sharp_text()
    root = tk.Tk()
    try:
        CompanionApp(root, CompanionController(default_data=DATA_LIVE))  # live unless the trader chose saved history
    except Exception as error:  # started by double-click there is no console to read
        from tkinter import messagebox

        root.withdraw()
        reason = f"{type(error).__name__}: {error}"
        messagebox.showerror("Trading Companion", "The companion could not start.\n\n" + reason)
        root.destroy()
        return 1
    _bring_to_front(root)
    root.mainloop()
    return 0


def _bring_to_front(root: tk.Tk) -> None:
    """Show the window above whatever is open (it otherwise starts behind a full-screen chart)."""
    try:
        root.deiconify()
        root.lift()
        root.attributes("-topmost", True)
        root.after(600, lambda: root.attributes("-topmost", False))
        root.focus_force()
    except tk.TclError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
