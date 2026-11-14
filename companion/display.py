"""How the companion window looks, without a display.

Colours, the direction-colour schemes, the contrast every text / background pair must
meet, and the geometry of a chart (how wide the price axis is, how tall a tag is, where
stacked tags go, how many candles fit, what the overlays leave on a chart) are decided
here as plain values and pure functions so they can be tested without Tk. So are the
smaller decisions the window makes about its own display: the order a chart is painted in,
which text sizes fit the screen, which price flags stay when a chart is short, what the
display menus hold and what a key does.
``companion.app`` measures its fonts, hands the numbers in, and draws what comes back.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Sequence, TypeVar

from companion.app_model import COLOUR_SCHEMES, MIN_BARS, OVERLAYS, TEXT_SIZE_LABELS, TEXT_SIZES, ChartView, chart_window

# --- colours ----------------------------------------------------------------------

BG = "#0d1117"  # window
SURFACE = "#151b23"  # panels, charts
FIELD = "#1e2631"  # inputs, cards, menus
HOVER = "#28323f"  # a plain button under the pointer
BORDER = "#2c3542"  # panel outlines (decoration)
EDGE = "#647080"  # outlines that say "this is a control": inputs, the scrollbar thumb
GRID = "#252e3a"
TEXT = "#e9edf2"
MUTED = "#9aa6b5"
FAINT = "#8a95a3"  # the quietest text that still carries information
WHITE = "#ffffff"
# Blue: the light one is for text and lines only; anything with white text on it uses the fills.
ACCENT = "#3d8bfd"
ACCENT_FILL = "#2a66d6"
ACCENT_FILL_HOT = "#2f6fd0"
ACCENT_FILL_PRESSED = "#2459bd"
WARN = "#ffc857"
ERROR = "#ff7b72"
# Status: blue is confirmed, amber is waiting, grey is failed. Confirmed and waiting are the
# defaults: each direction scheme carries its own (``Theme.confirmed``, ``Theme.waiting``), chosen
# to stay apart from that scheme's candles.
CONFIRMED = "#5b9dff"
WAITING = "#ffc857"
FAILED = "#c3ccd8"
NEUTRAL = "#b4bfcc"
POI = "#b69cff"
PROTECTED = "#d5dbe3"
NEXT_BG = "#2d2410"  # the row of the next step, and the WATCH banner
QUIET_BG = "#1a212b"  # the DON'T TRADE and neutral banners
ZONE_FILL = {"poi": "#231f3b", "confirm": "#14233b", "reference": "#1b222c"}


@dataclass(frozen=True)
class Theme:
    """One direction-colour scheme: up / long and down / short, wherever direction is shown."""

    key: str
    label: str
    up: str  # rising candles, a long
    down: str  # falling candles, a short
    long_bg: str  # banner of a long
    short_bg: str  # banner of a short
    reward_fill: str  # the reward zone of the risk / reward tool
    risk_fill: str  # its risk zone
    short_text: str  # the words on the banner of a short
    confirmed: str  # status: confirmed (rings, pointers, confirm lines and zone edges, done steps)
    waiting: str  # status: waiting (the next step, a planned plan, WATCH)


THEMES: dict[str, Theme] = {
    "green_red": Theme(
        "green_red", COLOUR_SCHEMES["green_red"], "#3fdc97", "#ff6b6b", "#0f2a1f", "#2f1518", "#173a2a", "#4a2025",
        short_text="#ff6b6b", confirmed=CONFIRMED, waiting=WAITING,
    ),
    # blue up candles: confirmed cannot be blue here (it was 1.04:1 against them; a light cyan sits too near the
    # protected level's grey), and amber sat too near the orange candles: mint and a clear yellow
    "blue_orange": Theme(
        "blue_orange", COLOUR_SCHEMES["blue_orange"], "#4c9bff", "#ff9f1c", "#10233d", "#622800", "#16304f", "#47300d",
        short_text="#ff9f1c", confirmed="#60f0a0", waiting="#ffe36e",
    ),
    # no hue for direction: a short is the solid one (black slab, white words), as its candles are the filled ones
    "mono": Theme(
        "mono", COLOUR_SCHEMES["mono"], "#e9edf2", "#9aa6b5", "#27303c", "#000000", "#2f3845", "#20262f",
        short_text=WHITE, confirmed="#44b4ff", waiting=WAITING,
    ),
}  # fmt: skip
DEFAULT_THEME = "green_red"


def theme_for(scheme: str) -> Theme:
    """The scheme saved in the state; the default for anything else."""
    return THEMES.get(scheme, THEMES[DEFAULT_THEME])


def tones(theme: Theme) -> dict[str, tuple[str, str]]:
    """Decision colour families: (foreground, banner background)."""
    return {
        "long": (theme.up, theme.long_bg),
        "short": (theme.short_text, theme.short_bg),
        "watch": (theme.waiting, NEXT_BG),
        "no_trade": (FAILED, QUIET_BG),
        "neutral": (NEUTRAL, QUIET_BG),
    }


# what a mark on a chart looks like, by its role: (colour, dash, line width)
MARK_STYLE: dict[str, tuple[str, tuple[int, ...] | None, int]] = {
    "reference": (MUTED, (4, 4), 1),
    "poi": (POI, (6, 3), 1),
    "protected": (PROTECTED, (1, 3), 1),
    "confirm": (CONFIRMED, None, 1),
    "waiting": (WAITING, (5, 3), 1),
    "entry": (WHITE, None, 2),
    "stop": (WHITE, (7, 4), 1),
    "target": (WHITE, (2, 3), 1),
    "next": (WAITING, (9, 3), 2),
    "session": (MUTED, (2, 4), 1),
}
MARK_PRIORITY = ("entry", "stop", "target", "next", "confirm", "waiting", "protected", "poi", "reference", "session")


def mark_style(theme: Theme, role: str) -> tuple[str, tuple[int, ...] | None, int]:
    """(colour, dash, line width) of a mark in ``theme``: the status roles take the scheme's status colours."""
    _colour, dash, width = style = MARK_STYLE.get(role, MARK_STYLE["reference"])
    if role == "confirm":
        return theme.confirmed, dash, width
    if role in ("waiting", "next"):
        return theme.waiting, dash, width
    return style


def status_colours(theme: Theme) -> dict[str, str]:
    """The colour of each state of the read in ``theme``."""
    return {"confirmed": theme.confirmed, "waiting": theme.waiting, "failed": FAILED, "not_applicable": FAINT}


# --- contrast ---------------------------------------------------------------------

TEXT_RATIO = 4.5  # WCAG AA, normal text
LARGE_RATIO = 3.0  # text of 18 pt, or 14 pt bold, and up; and graphics that carry meaning


def _channel(value: int) -> float:
    share = value / 255
    return share / 12.92 if share <= 0.03928 else ((share + 0.055) / 1.055) ** 2.4


def luminance(colour: str) -> float:
    """WCAG relative luminance of ``#rrggbb``."""
    red, green, blue = (int(colour[index : index + 2], 16) for index in (1, 3, 5))
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast(one: str, other: str) -> float:
    """WCAG contrast ratio of two colours, 1 .. 21."""
    first, second = luminance(one), luminance(other)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


@dataclass(frozen=True)
class Pair:
    """A foreground the window draws on a background, and the least contrast it needs."""

    what: str
    fg: str
    bg: str
    need: float = TEXT_RATIO

    @property
    def ratio(self) -> float:
        return contrast(self.fg, self.bg)

    @property
    def ok(self) -> bool:
        return self.ratio >= self.need


def contrast_pairs(theme: Theme) -> list[Pair]:
    """Every text / background pair and every meaningful graphic the window draws in ``theme``."""
    pairs: list[Pair] = []

    def text(what: str, fg: str, *backgrounds: str) -> None:
        pairs.extend(Pair(f"{what} on {bg}", fg, bg) for bg in backgrounds)

    def large(what: str, fg: str, *backgrounds: str) -> None:
        pairs.extend(Pair(f"{what} on {bg}", fg, bg, LARGE_RATIO) for bg in backgrounds)

    banners = [background for _fg, background in tones(theme).values()]
    fills = (theme.reward_fill, theme.risk_fill)
    text("text", TEXT, BG, SURFACE, FIELD, HOVER, NEXT_BG, *banners)
    text("muted text (captions, the reason, done steps, read-only boxes)", MUTED, BG, SURFACE, FIELD, HOVER, *banners)
    text("faint text (axis prices, later steps, legends, hints, tags)", FAINT, BG, SURFACE, FIELD)
    text("warning text", WARN, BG, SURFACE, *banners)
    text("error text", ERROR, SURFACE)
    text("confirmed (headers, done steps, passed rows)", theme.confirmed, SURFACE)
    text("waiting (headers, the next step, a planned plan)", theme.waiting, SURFACE, NEXT_BG, FIELD, BG)
    text("failed (headers, blocked steps, failed rows)", FAILED, SURFACE)
    text("point of interest name", POI, SURFACE)
    text("protected level name", PROTECTED, SURFACE)
    text("entry / stop / target name", WHITE, SURFACE)
    text("white on a blue button, selection or menu row", WHITE, ACCENT_FILL, ACCENT_FILL_HOT, ACCENT_FILL_PRESSED)
    marks = {role: mark_style(theme, role)[0] for role in MARK_STYLE}
    for role, colour in marks.items():
        text(f"price on the {role} flag", BG, colour)
        text(f"{role} name or marker label, on the chart and inside the risk / reward tool", colour, SURFACE, *fills)
    text("note on the chart (off the scale, more levels), also inside the risk / reward tool", MUTED, *fills)
    text("price on the crosshair tag", TEXT, FIELD)
    text("up word (hover readout, live line)", theme.up, SURFACE)
    text("down word (hover readout)", theme.down, SURFACE)
    text("REWARD caption", theme.up, theme.reward_fill)
    text("RISK caption", theme.down, theme.risk_fill)
    for tone, (colour, background) in tones(theme).items():
        large(f"{tone} suggestion (24 pt bold)", colour, background)
    # graphics that carry meaning
    large("up candle", theme.up, SURFACE, *fills, *ZONE_FILL.values())
    large("down candle", theme.down, SURFACE, *fills, *ZONE_FILL.values())
    for role, colour in marks.items():
        large(f"{role} line", colour, SURFACE, *fills, *ZONE_FILL.values())
    large("input border, scrollbar thumb", EDGE, SURFACE, BG)
    large("checkbox border", FAINT, BG)
    large("focus ring", ACCENT, SURFACE, BG)
    large("crosshair", FAINT, SURFACE)
    return pairs


# --- telling colours apart ----------------------------------------------------------
# Contrast says a colour can be read on its background. This says two colours can be told
# from each other: their distance in CIE L*a*b* (1976), with normal vision and as the three
# kinds of colour blindness see them (Machado, Oliveira and Fernandes 2009, severity 1.0).

VISIONS = ("normal", "protan", "deutan", "tritan")
_SEEN: dict[str, tuple[tuple[float, float, float], ...]] = {
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}
MARK_MARGIN = 20.0  # a status colour against a candle, or against another mark's colour
BANNER_BG_MARGIN = 9.0  # two banner backgrounds (large areas, all of them dark)
BANNER_TEXT_MARGIN = 15.0  # the words on two banners


def _lab(colour: str, vision: str) -> tuple[float, float, float]:
    rgb = [_channel(int(colour[index : index + 2], 16)) for index in (1, 3, 5)]
    if vision != "normal":
        rgb = [min(1.0, max(0.0, sum(weight * value for weight, value in zip(row, rgb)))) for row in _SEEN[vision]]
    red, green, blue = rgb
    xyz = (
        (0.4124564 * red + 0.3575761 * green + 0.1804375 * blue) / 0.95047,
        0.2126729 * red + 0.7151522 * green + 0.0721750 * blue,
        (0.0193339 * red + 0.1191920 * green + 0.9503041 * blue) / 1.08883,
    )
    x, y, z = (value ** (1 / 3) if value > 0.008856 else 7.787 * value + 16 / 116 for value in xyz)
    return 116 * y - 16, 500 * (x - y), 200 * (y - z)


def difference(one: str, other: str, vision: str = "normal") -> float:
    """How far apart two colours look (CIE76 delta E) with ``vision``. About 2 is just noticeable."""
    first, second = _lab(one, vision), _lab(other, vision)
    return sum((a - b) ** 2 for a, b in zip(first, second)) ** 0.5


def distinctness(one: str, other: str) -> float:
    """The smallest ``difference`` of two colours over normal vision and the three colour-blind ones."""
    return min(difference(one, other, vision) for vision in VISIONS)


@dataclass(frozen=True)
class Apart:
    """Two colours of one scheme that must not be mistaken for each other, and by how much they must differ."""

    what: str
    one: str
    other: str
    need: float

    @property
    def distance(self) -> float:
        return distinctness(self.one, self.other)

    @property
    def ok(self) -> bool:
        return self.distance >= self.need


def distinct_pairs(theme: Theme) -> list[Apart]:
    """The colours of ``theme`` that have to be told apart at a glance, with every kind of colour vision.

    The status colours against both candle colours and against the protected level's
    light grey; and the banner of a short against the WATCH and DON'T TRADE banners,
    background and words.
    """
    pairs: list[Apart] = []
    for status, colour in (("confirmed", theme.confirmed), ("waiting", theme.waiting)):
        pairs.append(Apart(f"{status} / up candle", colour, theme.up, MARK_MARGIN))
        pairs.append(Apart(f"{status} / down candle", colour, theme.down, MARK_MARGIN))
        pairs.append(Apart(f"{status} / protected level", colour, PROTECTED, MARK_MARGIN))
    pairs.append(Apart("confirmed / waiting", theme.confirmed, theme.waiting, MARK_MARGIN))
    families = tones(theme)
    short_text, short_bg = families["short"]
    for tone in ("watch", "no_trade"):
        colour, background = families[tone]
        pairs.append(Apart(f"short banner / {tone} banner, background", short_bg, background, BANNER_BG_MARGIN))
        pairs.append(Apart(f"short banner / {tone} banner, words", short_text, colour, BANNER_TEXT_MARGIN))
    return pairs


# --- the order a chart is painted in ---------------------------------------------------

# Back to front. A zone's fill never covers a line, and never repaints the risk / reward tool:
# every fill is down before the first line, and the tool's fills go over the zones' fills.
LAYERS = ("grid", "zone_fill", "tool_fill", "zone_edge", "level_line", "tool_outline", "tool_line", "candle", "text")
_Step = TypeVar("_Step")


def paint_order(steps: Iterable[tuple[str, _Step]]) -> list[tuple[str, _Step]]:
    """``(layer, what to draw)`` steps in the order they must be painted; steps of one layer keep their order."""
    return sorted(steps, key=lambda step: LAYERS.index(step[0]))


def backing(box: Box, areas: Sequence[tuple[Box, str]]) -> list[tuple[Box, str]]:
    """What to paint behind a label at ``box``: the parts of it over each filled area, with that area's fill.

    The label is first backed with the chart surface; these go over it, so a label inside
    the risk / reward tool sits on the tool's colour and does not cut a dark hole in it.
    """
    parts = []
    for (left, top, right, bottom), fill in areas:
        part = (max(box[0], left), max(box[1], top), min(box[2], right), min(box[3], bottom))
        if part[0] < part[2] and part[1] < part[3]:
            parts.append((part, fill))
    return parts


# --- sizes ------------------------------------------------------------------------

POINTS_PER_INCH = 72.0
BASE_DPI = 96.0  # Windows at 100 %
MIN_WINDOW = (1040, 860)  # at 100 % scaling and Normal text: the selections wrap to two rows and the charts keep about 250 px


def text_scale(size: str) -> float:
    return TEXT_SIZES.get(size, 1.0)


def dpi_scale(tk_scaling: float) -> float:
    """Windows scaling as a factor (1.0 at 100 %, 1.5 at 150 %) from Tk's pixels per point."""
    return max(0.5, float(tk_scaling) * POINTS_PER_INCH / BASE_DPI)


def font_points(base: int, scale: float) -> int:
    """A font's size in points at a text size. Points already follow Windows scaling."""
    return max(6, round(base * scale))


def pixels(value: float, scale: float) -> int:
    """A pixel size written for 100 % scaling, at ``scale``; never less than one pixel."""
    return max(1, round(value * scale))


def usable_screen(screen: tuple[int, int]) -> tuple[int, int]:
    """The most of the screen a window can take: the screen less the task bar, the title bar and a margin."""
    return max(640, screen[0] - 40), max(480, screen[1] - 90)


def min_window(scale: float, screen: tuple[int, int]) -> tuple[int, int]:
    """The smallest window that still holds everything at ``scale``, never more than the screen."""
    width, height = usable_screen(screen)
    return min(pixels(MIN_WINDOW[0], scale), width), min(pixels(MIN_WINDOW[1], scale), height)


TEXT_SIZE_REASON = "does not fit this screen"
SMALLEST_TEXT = next(iter(TEXT_SIZES))


def text_size_fits(size: str, dpi: float, screen: tuple[int, int]) -> bool:
    """Whether the window at this text size and Windows scaling still fits the height of the screen.

    The smallest size is always offered: there is nothing below it to fall back to.
    """
    return size == SMALLEST_TEXT or pixels(MIN_WINDOW[1], dpi * text_scale(size)) <= usable_screen(screen)[1]


def available_text_sizes(dpi: float, screen: tuple[int, int]) -> dict[str, str]:
    """Every text size, with why it cannot be chosen on this screen ("" when it can)."""
    return {size: "" if text_size_fits(size, dpi, screen) else TEXT_SIZE_REASON for size in TEXT_SIZES}


def fit_text_size(wanted: str, dpi: float, screen: tuple[int, int]) -> str:
    """``wanted``, or the largest size under it that fits the screen (a saved size on a smaller screen)."""
    sizes = list(TEXT_SIZES)
    position = sizes.index(wanted) if wanted in sizes else 0
    return next((size for size in reversed(sizes[: position + 1]) if text_size_fits(size, dpi, screen)), SMALLEST_TEXT)


def step_text_size(current: str, direction: int, dpi: float, screen: tuple[int, int]) -> str:
    """One size up or down from ``current`` (Ctrl+= / Ctrl+-); it stays where it is rather than outgrow the screen."""
    sizes = list(TEXT_SIZES)
    position = sizes.index(current) if current in sizes else 0
    target = sizes[min(max(position + (1 if direction > 0 else -1), 0), len(sizes) - 1)]
    return fit_text_size(target if direction <= 0 or text_size_fits(target, dpi, screen) else current, dpi, screen)


def needs_compact(window_height: float, others_height: float, reserve: float) -> bool:
    """Whether the regions above the charts must shrink: laid out in full they would leave the charts under ``reserve``.

    ``others_height`` is everything but the charts, at its full height. This happens when
    the screen caps the window below the height its text size was designed for.
    """
    return window_height - others_height < reserve


def room_message(can_shrink_text: bool) -> str:
    """What a chart says in place of a drawing it has no room for."""
    return "Not enough room — Ctrl+− for smaller text" if can_shrink_text else "Not enough room — make the window larger"


# --- chart geometry ---------------------------------------------------------------

Box = tuple[float, float, float, float]  # left, top, right, bottom


@dataclass(frozen=True)
class ChartMetrics:
    """Everything a chart's layout is derived from. All of it comes from measured fonts and one scale.

    ``scale`` is Windows scaling times the text size; ``dpi`` is Windows scaling alone
    (candles do not grow with the text size).
    """

    scale: float
    dpi: float
    line: int  # line height of the annotation font (names, marker labels, time labels)
    flag_line: int  # line height of the flag price font
    title_line: int  # line height of the timeframe in the header
    readout_line: int  # line height of the OHLC readout
    price_width: int  # width of the widest price the axis can show, in the flag price font

    def px(self, value: float) -> int:
        return pixels(value, self.scale)

    @property
    def tag_height(self) -> int:
        """Height of a name tag, a marker label and a price flag: one line and a pixel or two around it."""
        return max(self.line, self.flag_line) + 2 * self.px(1)

    @property
    def tag_gap(self) -> int:
        """Centre-to-centre distance of two stacked tags."""
        return self.tag_height + self.px(1)

    @property
    def pointer(self) -> int:
        """Width of a flag's point, between the plot and its box."""
        return self.px(6)

    @property
    def axis(self) -> int:
        """Width of the price axis: the point, the widest price, and padding on both sides."""
        return self.pointer + self.px(3) + self.price_width + self.px(5)

    @property
    def header(self) -> int:
        """Height of the header: the title line and the OHLC readout under it."""
        return self.px(7) + self.title_line + self.px(2) + self.readout_line + self.px(5)

    @property
    def readout_y(self) -> int:
        return self.px(7) + self.title_line + self.px(2)

    @property
    def foot(self) -> int:
        """Height of the time axis: a tick, one line of labels, and a margin."""
        return self.px(4) + self.line + self.px(3)

    @property
    def inset(self) -> int:
        """Room above and below the prices for marker labels."""
        return self.tag_height + self.px(8)

    @property
    def min_pitch(self) -> float:
        """The narrowest a candle gets: a hollow body must still read as hollow."""
        return MIN_PITCH * self.dpi

    @property
    def min_height(self) -> int:
        """The shortest chart that is drawn: the header, the time axis, and a plot that stacks four price flags
        (entry, stop, target and the next step's level) without one leaving it."""
        return self.header + self.px(2) + self.foot + ESSENTIAL_FLAGS * self.tag_gap

    @property
    def min_width(self) -> int:
        """The narrowest chart that is drawn: the price axis, a few names and the fewest candles."""
        return self.axis + self.px(150)


ESSENTIAL_FLAGS = 4  # entry, stop, target and the next step's level: the flags a chart never drops
MIN_PITCH = 6.0  # pixels per candle at 100 %: a 4 px body with a 3 px hollow
FIT_PITCH = 9.0  # what the automatic fit aims for
MAX_PITCH = 14.0  # the widest an automatically fitted candle gets
ZOOM_STEP = 1.25  # one notch of the mouse wheel


def candle_body(pitch: float, dpi: float = 1.0) -> int:
    """Width of a candle's body in whole pixels; never under 4 at 100 %, so up stays hollow."""
    return int(max(pixels(4, dpi), min(round(pitch * 0.64), pixels(26, dpi))))


def stack_tags(wanted: Sequence[float], height: float, top: float, bottom: float) -> list[float]:
    """Centres for tags of ``height`` that want to sit at ``wanted`` (ascending) without overlapping.

    Tags keep their order, are moved apart by at least ``height``, and stay between
    ``top`` and ``bottom`` whenever that many fit there.
    """
    placed = [float(value) for value in wanted]
    if not placed:
        return placed
    low, high = top + height / 2, bottom - height / 2
    placed[0] = max(placed[0], low)
    for index in range(1, len(placed)):
        placed[index] = max(placed[index], placed[index - 1] + height)
    if placed[-1] > high:
        placed[-1] = high
        for index in range(len(placed) - 2, -1, -1):
            placed[index] = min(placed[index], placed[index + 1] - height)
        if placed[0] < low:  # more tags than the height holds: keep the top ones inside
            placed[0] = low
            for index in range(1, len(placed)):
                placed[index] = max(placed[index], placed[index - 1] + height)
    return placed


def overlaps(one: Box, other: Box) -> bool:
    return one[0] < other[2] and other[0] < one[2] and one[1] < other[3] and other[1] < one[3]


def choose_box(candidates: Iterable[Box], placed: Sequence[Box], obstacles: Sequence[Box] = ()) -> Box | None:
    """The first candidate clear of every box already placed that covers the fewest obstacles.

    ``placed`` are other labels (never covered); ``obstacles`` are candles (avoided when
    possible). ``None`` when every candidate would cover a label.
    """
    best: tuple[int, Box] | None = None
    for box in candidates:
        if any(overlaps(box, other) for other in placed):
            continue
        covered = sum(overlaps(box, other) for other in obstacles)
        if covered == 0:
            return box
        if best is None or covered < best[0]:
            best = (covered, box)
    return best[1] if best is not None else None


@dataclass
class Flag:
    """A label at the right edge of a chart: its name inside the plot, its price on the axis."""

    y: float  # where its price is
    price: float | None  # None: a name only (the middle of a zone)
    forms: tuple[str, ...]  # the name, fullest first; () when it has none
    colour: str
    role: str
    keep: bool = False  # the shortest form is a role word (Entry / Stop / Target) and is never cut
    at: float = 0.0  # where the tag is drawn once stacked


def merge_flags(flags: Iterable[Flag]) -> list[Flag]:
    """Flags sorted top to bottom, with those at exactly one price sharing a tag ("Swing low = Prev low")."""
    merged: list[Flag] = []
    for flag in sorted(flags, key=lambda item: (item.y, MARK_PRIORITY.index(item.role))):
        same = bool(merged) and abs(merged[-1].y - flag.y) < 1.5
        if same and merged[-1].price is not None and flag.price is not None:
            same = abs(merged[-1].price - flag.price) < 1e-9
        if not same:
            merged.append(replace(flag, at=flag.y))
            continue
        previous = merged[-1]
        lead, other = previous, flag
        if MARK_PRIORITY.index(flag.role) < MARK_PRIORITY.index(previous.role):
            lead, other = flag, previous
        names = [forms[0] for forms in (lead.forms, other.forms) if forms]
        joined = " = ".join(dict.fromkeys(names))
        shorter = lead.forms[1:] if lead.forms else other.forms[1:]
        previous.forms = tuple(dict.fromkeys(form for form in (joined, *shorter) if form))
        previous.colour, previous.role = lead.colour, lead.role
        previous.keep = lead.keep if lead.forms else other.keep
        if previous.price is None:
            previous.price = flag.price
    return merged


def fit_flags(flags: Sequence[Flag], gap: float, top: float, bottom: float) -> tuple[list[Flag], list[Flag]]:
    """``(kept, dropped)``: the flags that can be stacked ``gap`` apart between ``top`` and ``bottom``.

    When they do not all fit, the ones that matter most stay (entry, stop, target, the
    next step's level, then the rest in ``MARK_PRIORITY`` order) and keep their order top
    to bottom; the chart says how many it left out. With what is kept, ``stack_tags``
    never has to place a flag outside the plot.
    """
    room = max(0, int((bottom - top + 1e-6) // max(gap, 1e-9)))
    if len(flags) <= room:
        return list(flags), []
    ranked = sorted(range(len(flags)), key=lambda index: (MARK_PRIORITY.index(flags[index].role), index))
    keep = set(ranked[:room])
    return [flag for index, flag in enumerate(flags) if index in keep], [flag for index, flag in enumerate(flags) if index not in keep]


def more_note(dropped: int) -> str:
    """The note a chart shows for the level labels it had no room for."""
    return f"+{dropped} more level{'' if dropped == 1 else 's'}"


def name_gutter(widths: Sequence[float], plot_width: float, scale: float = 1.0) -> int:
    """Width kept free of candles at the right of the plot for the level names.

    As wide as the widest name (after merging), but never more than 190 px at 100 % or
    45 % of the plot, so the candles always keep most of the chart.
    """
    padding = pixels(12, scale)
    least = pixels(12, scale)
    cap = max(least, min(pixels(190, scale), plot_width * 0.45))
    return int(min(cap, max([least] + [width + padding for width in widths])))


def bar_limits(total: int, room: float, min_pitch: float) -> tuple[int, int]:
    """Fewest and most candles a chart of ``room`` pixels may show."""
    most = max(1, min(total, int(room // max(min_pitch, 1e-9))))
    return min(most, MIN_BARS), most


def clamp_bars(bars: int, total: int, room: float, min_pitch: float) -> int:
    least, most = bar_limits(total, room, min_pitch)
    return min(max(int(bars), least), most)


def zoom_bars(current: int, notches: int, total: int, room: float, min_pitch: float) -> int:
    """Candles to show after ``notches`` of the wheel: positive zooms in (fewer, wider candles).

    Always moves by at least one candle per notch and stops at the limits: no closer
    than ``MIN_BARS``, no further out than the minimum candle pitch allows.
    """
    wanted = current
    for _ in range(abs(notches)):
        step = round(wanted / ZOOM_STEP) if notches > 0 else round(wanted * ZOOM_STEP)
        wanted = min(step, wanted - 1) if notches > 0 else max(step, wanted + 1)
    return clamp_bars(wanted, total, room, min_pitch)


def chart_span(chart: ChartView, room: float, dpi: float = 1.0, bars: int = 0) -> tuple[int, int, float]:
    """``(first candle, candles shown, pixels per candle)`` for a plot ``room`` pixels wide.

    ``bars`` is the trader's zoom (0: fit automatically, reaching back to what the read
    marked). Either way a candle is never narrower than the minimum pitch: fewer bars
    are shown instead.
    """
    total = len(chart.candles)
    if total == 0:
        return 0, 0, MAX_PITCH * dpi
    min_pitch = MIN_PITCH * dpi
    _least, most = bar_limits(total, room, min_pitch)
    if bars > 0:
        count = clamp_bars(bars, total, room, min_pitch)
        return total - count, count, min(room / count, 40.0 * dpi)
    fit = max(1, min(most, int(room // (FIT_PITCH * dpi))))
    first = chart_window(chart, fit, most)
    count = total - first
    return first, count, min(MAX_PITCH * dpi, room / count)


def apply_overlays(chart: ChartView, shown: dict[str, bool]) -> ChartView:
    """What the chart is asked to draw with the overlays in ``shown`` (keys of ``OVERLAYS``; missing means on).

    Zones off: no zone marks. Level names off: the levels keep their lines and price
    flags but lose their names. Marker labels off: the marked candles keep their ring
    and pointer but lose their words. Risk / reward box off: the tool keeps its entry,
    stop and target lines and their flags, without the two zones.
    """
    on = {name: bool(shown.get(name, True)) for name in OVERLAYS}
    marks = []
    for mark in chart.marks:
        if mark.role == "session":
            continue  # the session reference levels are a layer of the web window only
        if mark.kind == "zone" and not on["zones"]:
            continue
        if mark.kind in ("level", "zone") and not on["level_names"]:
            mark = replace(mark, label="")
        if mark.kind == "marker" and not on["marker_labels"]:
            mark = replace(mark, label="")
        marks.append(mark)
    tool = chart.tool
    if tool is not None:
        tool = replace(tool, box=tool.box and on["rr_box"], named=tool.named and on["level_names"])
    return replace(chart, marks=tuple(marks), tool=tool)


# --- the display menus and the keys ----------------------------------------------------


@dataclass(frozen=True)
class MenuItem:
    """One row of a display menu. ``kind``: heading, overlay, scheme, text_size, command or separator."""

    kind: str
    label: str = ""
    value: str = ""  # the overlay, scheme or text size it sets; the name of a command
    enabled: bool = True
    accelerator: str = ""


SCHEME_NOTES = {"green_red": "", "blue_orange": "   (colour-blind safe)", "mono": "   (hollow up, filled down)"}


def display_menu(on_chart: bool, sizes: dict[str, str] | None = None) -> list[MenuItem]:
    """The rows of a display menu: a chart's (right-click, its gear) or the footer's "Display".

    Both hold the overlays, which apply to all charts, the direction colours and the text
    size. A chart's menu resets that chart's zoom, the footer's resets every chart's.
    ``sizes`` is ``available_text_sizes``: a size with a reason is listed but cannot be chosen.
    """
    sizes = sizes if sizes is not None else {size: "" for size in TEXT_SIZES}
    items = [MenuItem("heading", "SHOW ON THE CHARTS")]
    items += [MenuItem("overlay", label, name) for name, label in OVERLAYS.items()]
    items += [MenuItem("separator"), MenuItem("heading", "DIRECTION COLOURS  ·  candles, risk / reward, long / short")]
    items += [MenuItem("scheme", f"{label}{SCHEME_NOTES.get(key, '')}", key) for key, label in COLOUR_SCHEMES.items()]
    items += [MenuItem("separator"), MenuItem("heading", "TEXT SIZE  ·  Ctrl+=  bigger   Ctrl+−  smaller   Ctrl+0  normal")]
    for key, label in TEXT_SIZE_LABELS.items():
        reason = sizes.get(key, "")
        items.append(MenuItem("text_size", f"{label}   ({reason})" if reason else label, key, enabled=not reason))
    items.append(MenuItem("separator"))
    if on_chart:
        items.append(MenuItem("command", "Reset zoom (this chart)", "reset_zoom_chart", accelerator="wheel zooms"))
    else:
        items.append(MenuItem("command", "Reset zoom (all charts)", "reset_zoom_all"))
    items.append(MenuItem("command", "Reset display defaults", "reset_display"))
    return items


def menu_origin(button: Box, menu_size: tuple[int, int], window: tuple[int, int], gap: int = 2) -> tuple[int, int]:
    """Where a menu that opens above ``button`` goes (screen pixels): left edges in line, moved left
    as far as needed to end inside the window, whose left and right edges are ``window``."""
    left = min(button[0], window[1] - menu_size[0])
    return int(max(window[0], left)), int(button[1] - menu_size[1] - gap)


_BIGGER = ("plus", "equal", "KP_Add")
_SMALLER = ("minus", "KP_Subtract")
_ZERO = ("0", "KP_0", "KP_Insert")


def key_action(keysym: str, control: bool, on_chart: bool) -> str:
    """What =, +, - and 0 do: ``text_bigger``, ``text_smaller``, ``text_normal``, ``zoom_in``, ``zoom_out`` or "".

    With Ctrl they are the text size, wherever the keyboard focus is. Without it, on a
    focused chart, + / = / - zoom that chart.
    """
    if control:
        return "text_bigger" if keysym in _BIGGER else "text_smaller" if keysym in _SMALLER else "text_normal" if keysym in _ZERO else ""
    if on_chart:
        return "zoom_in" if keysym in _BIGGER else "zoom_out" if keysym in _SMALLER else ""
    return ""
