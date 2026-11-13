"""The companion window's look, tested without a display.

Display options in the saved state, the direction-colour schemes, their contrast and how
far apart their colours are, what the overlays leave on a chart, the zoom and its minimum
candle pitch, the chart's layout maths (axis width, tag heights, stacked tags) at every
text size and Windows scaling, and the window's own display decisions: the order a chart
is painted in, which text sizes fit a screen, which price flags a short chart keeps, what
the display menus hold and what the size and zoom keys do.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from companion import display
from companion.app_model import (
    CHART_BARS,
    COLOUR_SCHEMES,
    MIN_BARS,
    OVERLAYS,
    TEXT_SIZES,
    Candle,
    ChartMark,
    ChartView,
    CompanionController,
    RiskRewardTool,
    UiState,
    load_state,
)
from companion.display import (
    ChartMetrics,
    Flag,
    apply_overlays,
    available_text_sizes,
    backing,
    bar_limits,
    candle_body,
    chart_span,
    choose_box,
    contrast,
    contrast_pairs,
    difference,
    display_menu,
    distinct_pairs,
    distinctness,
    dpi_scale,
    fit_flags,
    fit_text_size,
    font_points,
    key_action,
    mark_style,
    menu_origin,
    merge_flags,
    min_window,
    name_gutter,
    needs_compact,
    overlaps,
    paint_order,
    stack_tags,
    status_colours,
    step_text_size,
    text_size_fits,
    theme_for,
    tones,
    zoom_bars,
)


def make_controller(tmp_path: Path) -> CompanionController:
    return CompanionController(state_path=tmp_path / "ui_state.json", coverage=lambda symbol: None)


def chart(candles: int = 120, marks: tuple[ChartMark, ...] = (), tool: RiskRewardTool | None = None) -> ChartView:
    start = pd.Timestamp("2026-02-18 03:00")
    bars = tuple(
        Candle(start + pd.Timedelta(minutes=5 * index), 100.0 + index, 102.0 + index, 99.0 + index, 101.0 + index, False, f"{index}")
        for index in range(candles)
    )
    return ChartView("entry", "5m", bars, marks, tool=tool)


MARKS = (
    ChartMark("level", "reference", "Prev high", "Previous high", price=150.0),
    ChartMark("zone", "poi", "POI: gap", "Fair value gap", top=140.0, bottom=130.0, start=40),
    ChartMark("marker", "confirm", "CISD", "Change in state of delivery", price=120.0, start=90),
    ChartMark("level", "protected", "Swing low", "Protected swing low", price=110.0),
)
TOOL = RiskRewardTool("long", False, entry=200.0, stop=190.0, target=220.0, start=100, r_multiple=2.0)


# --- the options in the saved state --------------------------------------------------


def test_display_options_have_defaults_and_persist(tmp_path: Path) -> None:
    fresh = UiState()
    assert (fresh.text_size, fresh.colours) == ("normal", "green_red")
    assert all(getattr(fresh, f"show_{name}") is True for name in OVERLAYS)
    assert (fresh.bars_bias, fresh.bars_setup, fresh.bars_entry) == (0, 0, 0)

    first = make_controller(tmp_path)
    first.set_text_size("Larger")
    first.set_colours("Blue / orange")
    first.set_overlay("zones", False)
    first.set_overlay("rr_box", False)
    first.set_chart_bars("entry", 48)
    assert first.save() is True
    saved = json.loads(first.state_path.read_text(encoding="utf-8"))
    assert (saved["text_size"], saved["colours"], saved["show_zones"], saved["bars_entry"]) == ("larger", "blue_orange", False, 48)

    second = make_controller(tmp_path)
    assert second.state == first.state
    assert second.text_scale() == 1.5
    assert second.overlays() == {"level_names": True, "zones": False, "marker_labels": True, "rr_box": False}
    assert (second.chart_bars("bias"), second.chart_bars("entry")) == (0, 48)


@pytest.mark.parametrize(
    "saved",
    [
        {"text_size": "huge", "colours": "rainbow"},
        {"text_size": 2, "colours": None, "show_zones": "no", "show_rr_box": 0},
        {"bars_bias": True, "bars_setup": -5, "bars_entry": 3},
        {"bars_bias": 10_000, "bars_setup": "40", "bars_entry": 2.5},
    ],
)
def test_invalid_saved_display_values_fall_back_to_the_defaults(tmp_path: Path, saved: dict[str, object]) -> None:
    path = tmp_path / "ui_state.json"
    path.write_text(json.dumps({**saved, "symbol": "NQ", "unknown_option": 1}), encoding="utf-8")
    state = load_state(path)
    assert state == UiState(symbol="NQ")


def test_valid_saved_display_values_are_kept(tmp_path: Path) -> None:
    path = tmp_path / "ui_state.json"
    path.write_text(json.dumps({"text_size": "large", "colours": "mono", "show_level_names": False, "bars_setup": MIN_BARS}), encoding="utf-8")
    state = load_state(path)
    assert (state.text_size, state.colours, state.show_level_names, state.bars_setup) == ("large", "mono", False, MIN_BARS)


def test_text_size_steps_stop_at_the_ends_and_reset_restores_everything(tmp_path: Path) -> None:
    controller = make_controller(tmp_path)
    assert [controller.step_text_size(1) for _ in range(3)] == ["large", "larger", "larger"]
    assert [controller.step_text_size(-1) for _ in range(3)] == ["large", "normal", "normal"]
    controller.set_text_size("nonsense")
    assert controller.state.text_size == "normal"
    controller.set_colours("nonsense")
    assert controller.state.colours == "green_red"

    controller.set_text_size("large")
    controller.set_colours("mono")
    controller.set_overlay("level_names", False)
    controller.set_overlay("not an overlay", False)  # ignored
    controller.set_chart_bars("bias", 3)  # too few: the closest zoom
    controller.set_chart_bars("setup", 10_000)  # too many: everything fetched
    controller.set_chart_bars("nowhere", 50)  # ignored
    assert (controller.chart_bars("bias"), controller.chart_bars("setup")) == (MIN_BARS, CHART_BARS + 1)
    controller.state.symbol, controller.state.direction = "ES", "long"
    controller.reset_zoom("bias")
    assert (controller.chart_bars("bias"), controller.chart_bars("setup")) == (0, CHART_BARS + 1)
    controller.reset_display()
    fresh = UiState()
    for name in ("text_size", "colours", "show_level_names", "show_zones", "show_marker_labels", "show_rr_box", "bars_bias", "bars_setup", "bars_entry"):
        assert getattr(controller.state, name) == getattr(fresh, name)
    assert (controller.state.symbol, controller.state.direction) == ("ES", "long")  # the selections are not display options


# --- text size and palette -> the derived theme ---------------------------------------


def test_text_scale_and_windows_scaling_give_the_font_and_pixel_sizes() -> None:
    assert TEXT_SIZES == {"normal": 1.0, "large": 1.25, "larger": 1.5}
    assert [font_points(10, scale) for scale in TEXT_SIZES.values()] == [10, 12, 15]
    assert [font_points(8, scale) for scale in TEXT_SIZES.values()] == [8, 10, 12]
    assert dpi_scale(96 / 72) == pytest.approx(1.0)  # Tk's pixels per point at 100 %
    assert dpi_scale(144 / 72) == pytest.approx(1.5)  # and at 150 %
    assert display.pixels(8, 1.0) == 8 and display.pixels(8, 1.5 * 1.25) == 15 and display.pixels(0.2, 1.0) == 1
    assert min_window(1.0, (3440, 1440)) == display.MIN_WINDOW
    assert min_window(1.5, (3440, 1440)) == (1560, 1290)
    assert min_window(2.25, (1920, 1080)) == (1880, 990)  # never larger than the screen


def test_one_scheme_drives_candles_zones_and_banners_together() -> None:
    assert set(display.THEMES) == set(COLOUR_SCHEMES)
    assert theme_for("anything else") is display.THEMES["green_red"]
    green, blue, mono = (theme_for(key) for key in ("green_red", "blue_orange", "mono"))
    assert (green.up, green.down) == ("#3fdc97", "#ff6b6b")  # the trader's convention is the default
    assert (blue.up, blue.down) == ("#4c9bff", "#ff9f1c")
    assert display.luminance(mono.up) > display.luminance(mono.down)  # light hollow up, grey filled down
    for theme in (green, blue, mono):
        families = tones(theme)
        assert families["long"] == (theme.up, theme.long_bg) and families["short"] == (theme.short_text, theme.short_bg)
        assert families["watch"] == (theme.waiting, display.NEXT_BG) and families["no_trade"] == (display.FAILED, display.QUIET_BG)
        assert len({theme.up, theme.down, theme.reward_fill, theme.risk_fill, theme.long_bg, theme.short_bg}) == 6
        assert theme.label == COLOUR_SCHEMES[theme.key]
        # the status colours of the scheme reach the marks, the read and the banner alike
        assert mark_style(theme, "confirm")[0] == theme.confirmed
        assert mark_style(theme, "waiting")[0] == mark_style(theme, "next")[0] == theme.waiting
        assert mark_style(theme, "confirm")[1:] == display.MARK_STYLE["confirm"][1:]  # the dash and the width are not the scheme's
        assert mark_style(theme, "poi") == display.MARK_STYLE["poi"] and mark_style(theme, "unheard of") == display.MARK_STYLE["reference"]
        assert status_colours(theme) == {"confirmed": theme.confirmed, "waiting": theme.waiting, "failed": display.FAILED, "not_applicable": display.FAINT}
    assert (green.short_text, blue.short_text) == (green.down, blue.down)  # a short keeps its candles' colour where that has a hue
    assert (green.confirmed, green.waiting) == (display.CONFIRMED, display.WAITING)  # the default scheme keeps blue and amber


# --- contrast -------------------------------------------------------------------------


def test_contrast_ratio_is_the_wcag_one() -> None:
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#ffffff", "#ffffff") == pytest.approx(1.0)
    assert contrast("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)
    assert contrast("#3d8bfd", "#ffffff") < 4.5  # the old light blue under white text: what this replaced


@pytest.mark.parametrize("scheme", list(COLOUR_SCHEMES))
def test_every_text_and_graphic_meets_its_contrast_in_every_scheme(scheme: str) -> None:
    pairs = contrast_pairs(theme_for(scheme))
    assert len(pairs) > 80
    failing = [f"{pair.what}: {pair.fg} on {pair.bg} is {pair.ratio:.2f}, needs {pair.need}" for pair in pairs if not pair.ok]
    assert not failing, "\n".join(failing)
    text = [pair for pair in pairs if pair.need == display.TEXT_RATIO]
    assert min(pair.ratio for pair in text) >= 4.5
    # white text sits only on the darkened blues, in normal, hover and pressed states
    for fill in (display.ACCENT_FILL, display.ACCENT_FILL_HOT, display.ACCENT_FILL_PRESSED):
        assert contrast(display.WHITE, fill) >= 4.5
    # controls are outlined at 3:1 against what they sit on
    assert contrast(display.EDGE, display.SURFACE) >= 3.0 and contrast(display.EDGE, display.BG) >= 3.0


# --- telling the colours of a scheme apart ---------------------------------------------


def test_colour_difference_is_measured_for_every_kind_of_colour_vision() -> None:
    assert difference("#123456", "#123456") == pytest.approx(0.0)
    assert difference("#000000", "#ffffff") == pytest.approx(100.0, abs=0.1)  # L* 0 to 100
    assert display.VISIONS == ("normal", "protan", "deutan", "tritan")
    red, green = "#ff0000", "#00a000"
    assert difference(red, green) > 100  # far apart with normal vision
    assert difference(red, green, "deutan") < difference(red, green) / 2  # and much closer without the red / green channel
    assert distinctness(red, green) == min(difference(red, green, vision) for vision in display.VISIONS)
    # what the review found: "confirmed" blue on the blue up candles of Blue / orange, and that scheme's short and watch banners
    assert distinctness("#5b9dff", "#4c9bff") < 3 and contrast("#5b9dff", "#4c9bff") < 1.1
    assert distinctness("#33230c", display.NEXT_BG) < 3
    # the cyan suggested for Blue / orange clears the candles but not the protected level's light grey: it was not adopted
    assert distinctness("#9be8ff", "#4c9bff") > display.MARK_MARGIN and distinctness("#9be8ff", display.PROTECTED) < display.MARK_MARGIN


@pytest.mark.parametrize("scheme", list(COLOUR_SCHEMES))
def test_status_colours_and_banners_stay_apart_in_every_scheme(scheme: str) -> None:
    theme = theme_for(scheme)
    pairs = distinct_pairs(theme)
    failing = [f"{pair.what}: {pair.one} / {pair.other} differ by {pair.distance:.1f}, need {pair.need}" for pair in pairs if not pair.ok]
    assert not failing, "\n".join(failing)
    named = {pair.what: pair for pair in pairs}
    # confirmed (rings, pointers, confirm lines, zone edges) and waiting, against both candle colours
    for status, colour in (("confirmed", theme.confirmed), ("waiting", theme.waiting)):
        for candle, other in (("up", theme.up), ("down", theme.down)):
            pair = named[f"{status} / {candle} candle"]
            assert (pair.one, pair.other, pair.need) == (colour, other, display.MARK_MARGIN)
            assert all(difference(colour, other, vision) >= display.MARK_MARGIN for vision in display.VISIONS)
        assert distinctness(colour, display.PROTECTED) >= display.MARK_MARGIN
    assert distinctness(theme.confirmed, theme.waiting) >= display.MARK_MARGIN
    assert display.MARK_MARGIN >= 20 and display.BANNER_BG_MARGIN >= 9 and display.BANNER_TEXT_MARGIN >= 15
    # TRADE SHORT against WATCH and DON'T TRADE: another background and other words
    families = tones(theme)
    for tone in ("watch", "no_trade"):
        assert families["short"][1] != families[tone][1]
        assert distinctness(families["short"][1], families[tone][1]) >= display.BANNER_BG_MARGIN
        assert distinctness(families["short"][0], families[tone][0]) >= display.BANNER_TEXT_MARGIN
    assert contrast(families["short"][0], families["short"][1]) >= 4.5  # and the words still read on it


def test_blue_orange_keeps_every_light_mark_apart() -> None:
    """The scheme offered as colour-blind safe: its status colours clear the other marks' colours too."""
    blue = theme_for("blue_orange")
    for colour in (blue.confirmed, blue.waiting):
        for other in (display.POI, display.PROTECTED, display.WHITE, blue.up, blue.down):
            assert distinctness(colour, other) >= display.MARK_MARGIN, (colour, other)
    assert contrast(blue.confirmed, display.SURFACE) >= 4.5 and contrast(blue.waiting, display.NEXT_BG) >= 4.5


# --- the order a chart is painted in ----------------------------------------------------


def test_fills_are_painted_before_lines_and_zone_fills_before_the_tool() -> None:
    layers = display.LAYERS
    assert layers.index("grid") < layers.index("zone_fill") < layers.index("tool_fill")  # the tool's fill goes over a zone's
    assert layers.index("tool_fill") < layers.index("zone_edge") < layers.index("tool_outline")  # a zone inside the tool keeps its edge
    assert layers.index("tool_fill") < layers.index("level_line") < layers.index("tool_outline") < layers.index("tool_line")
    assert layers.index("tool_line") < layers.index("candle") < layers.index("text")
    # found in the order the read lists them: a level, then a zone that covers its price, then the tool
    found = [
        ("level_line", "4h wick 50%"), ("zone_fill", "POI"), ("zone_edge", "POI top"), ("zone_edge", "POI bottom"),
        ("tool_line", "entry"), ("tool_fill", "risk"), ("zone_fill", "confirm"), ("zone_edge", "confirm top"), ("tool_outline", "risk"),
        ("grid", "axis"), ("level_line", "Prev low"), ("tool_fill", "reward"),
    ]  # fmt: skip
    painted = paint_order(found)
    assert sorted(painted) == sorted(found)  # nothing lost, nothing added
    order = [name for _layer, name in painted]
    assert order.index("POI") < order.index("4h wick 50%")  # no fill over a level line
    assert max(order.index("POI"), order.index("confirm")) < min(order.index("risk"), order.index("reward"))  # no zone repaints the tool
    assert order.index("reward") < order.index("confirm top")  # its edge is still drawn, over the fill
    fills = [index for index, (layer, _name) in enumerate(painted) if layer.endswith("_fill")]
    lines = [index for index, (layer, _name) in enumerate(painted) if layer.endswith(("_edge", "_line", "_outline"))]
    assert max(fills) < min(lines)
    assert [name for layer, name in painted if layer == "zone_fill"] == ["POI", "confirm"]  # one layer keeps the order it was found in
    assert [name for layer, name in painted if layer == "level_line"] == ["4h wick 50%", "Prev low"]
    assert paint_order([]) == []


def test_a_label_inside_the_tool_is_backed_with_the_fill_under_it() -> None:
    reward, risk = ((100.0, 50.0, 400.0, 150.0), "#173a2a"), ((100.0, 150.0, 400.0, 220.0), "#4a2025")
    areas = [reward, risk]
    assert backing((200.0, 60.0, 260.0, 80.0), areas) == [((200.0, 60.0, 260.0, 80.0), "#173a2a")]  # wholly inside the reward
    assert backing((10.0, 60.0, 60.0, 80.0), areas) == []  # outside the tool: the plain surface
    assert backing((80.0, 60.0, 140.0, 80.0), areas) == [((100.0, 60.0, 140.0, 80.0), "#173a2a")]  # across its left edge: only the part inside
    across = backing((300.0, 140.0, 380.0, 160.0), areas)  # across the entry line: each half its own colour
    assert across == [((300.0, 140.0, 380.0, 150.0), "#173a2a"), ((300.0, 150.0, 380.0, 160.0), "#4a2025")]
    assert backing((200.0, 60.0, 260.0, 80.0), []) == []


# --- overlays -------------------------------------------------------------------------


def test_everything_is_drawn_by_default() -> None:
    view = chart(marks=MARKS, tool=TOOL)
    assert apply_overlays(view, {}) == view
    assert apply_overlays(view, {name: True for name in OVERLAYS}) == view


def test_overlay_flags_filter_what_the_chart_draws_and_the_plan_survives() -> None:
    view = chart(marks=MARKS, tool=TOOL)

    no_zones = apply_overlays(view, {"zones": False})
    assert [mark.kind for mark in no_zones.marks] == ["level", "marker", "level"]
    assert no_zones.tool == TOOL

    no_names = apply_overlays(view, {"level_names": False})
    assert [(mark.kind, mark.label) for mark in no_names.marks] == [("level", ""), ("zone", ""), ("marker", "CISD"), ("level", "")]
    assert [mark.price for mark in no_names.marks if mark.kind == "level"] == [150.0, 110.0]  # the lines and their price flags stay
    assert no_names.tool is not None and no_names.tool.named is False and no_names.tool.box is True

    no_marker_words = apply_overlays(view, {"marker_labels": False})
    assert [(mark.kind, mark.label, mark.start) for mark in no_marker_words.marks if mark.kind == "marker"] == [("marker", "", 90)]

    no_box = apply_overlays(view, {"rr_box": False})
    assert no_box.tool is not None and no_box.tool.box is False and no_box.marks == view.marks

    bare = apply_overlays(view, {name: False for name in OVERLAYS})
    assert bare.tool is not None
    assert (bare.tool.entry, bare.tool.stop, bare.tool.target) == (200.0, 190.0, 220.0)  # entry, stop and target always remain
    assert (bare.tool.direction, bare.tool.start, bare.tool.r_multiple) == ("long", 100, 2.0)
    assert bare.candles == view.candles
    assert all(mark.kind != "zone" and mark.label == "" for mark in bare.marks)
    assert view.marks == MARKS and view.tool == TOOL  # the chart handed in is not changed


# --- zoom and the minimum candle pitch -------------------------------------------------


@pytest.mark.parametrize("dpi", [1.0, 1.5])
def test_automatic_fit_never_draws_candles_under_the_minimum_pitch(dpi: float) -> None:
    far = chart(marks=(ChartMark("marker", "confirm", "CISD", "", price=101.0, start=0),))  # wants all 120 candles on screen
    for room in (120.0, 240.0, 400.0, 700.0, 2000.0):
        first, count, pitch = chart_span(far, room, dpi)
        assert first + count == 120
        assert pitch >= display.MIN_PITCH * dpi - 1e-9  # fewer bars rather than unreadable ones
        assert count * pitch <= room + 1e-9
        assert candle_body(pitch, dpi) >= 4 * dpi and candle_body(pitch, dpi) <= pitch  # a hollow body stays hollow
    assert chart_span(far, 2000.0, 1.0)[1] == 120  # with room, what the read marked is on screen
    assert chart_span(far, 240.0, 1.0)[1] == 40  # without, as many as stay readable
    assert chart_span(chart(candles=0), 400.0) == (0, 0, display.MAX_PITCH)


def test_zoom_is_clamped_and_moves_one_notch_at_a_time() -> None:
    room, pitch = 600.0, display.MIN_PITCH
    assert bar_limits(160, room, pitch) == (MIN_BARS, 100)
    assert bar_limits(6, room, pitch) == (6, 6)  # fewer candles than the closest zoom
    assert zoom_bars(60, 1, 160, room, pitch) == 48  # wheel up: fewer, wider candles
    assert zoom_bars(60, -1, 160, room, pitch) == 75
    assert zoom_bars(11, 1, 160, room, pitch) == MIN_BARS and zoom_bars(10, 5, 160, room, pitch) == MIN_BARS
    assert zoom_bars(90, -1, 160, room, pitch) == 100 and zoom_bars(100, -5, 160, room, pitch) == 100  # the minimum pitch stops it
    assert zoom_bars(12, -1, 160, room, pitch) > 12 and zoom_bars(12, 1, 160, room, pitch) < 12

    view = chart(candles=160)
    first, count, width = chart_span(view, room, 1.0, bars=48)
    assert (first, count, width) == (112, 48, pytest.approx(12.5))
    first, count, width = chart_span(view, room, 1.0, bars=1000)  # a saved zoom wider than this window allows
    assert count == 100 and width == pytest.approx(6.0)
    assert chart_span(view, room, 1.5, bars=1000)[1] == 66  # at 150 % a candle needs 9 px


def test_zoom_is_remembered_per_chart_role(tmp_path: Path) -> None:
    controller = make_controller(tmp_path)
    controller.set_chart_bars("bias", 30)
    controller.set_chart_bars("entry", 80)
    controller.save()
    again = make_controller(tmp_path)
    assert [again.chart_bars(role) for role in ("bias", "setup", "entry")] == [30, 0, 80]
    again.reset_zoom()
    assert [again.chart_bars(role) for role in ("bias", "setup", "entry")] == [0, 0, 0]


# --- layout maths at every text size and Windows scaling ---------------------------------


def metrics(text: float, dpi: float, widest: str = "88,888.88") -> ChartMetrics:
    """Sizes as Tk reports them for Segoe UI and Consolas: about 1.33 x the pixel size per line, 0.55 em per digit."""

    def line(points: int, ratio: float) -> int:
        return round(font_points(points, text) * dpi * 96 / 72 * ratio)

    digit = font_points(10, text) * dpi * 96 / 72 * 0.55
    return ChartMetrics(
        scale=text * dpi, dpi=dpi, line=line(10, 1.28), flag_line=line(10, 1.13), title_line=line(13, 1.33), readout_line=line(10, 1.13),
        price_width=round(len(widest) * digit),
    )  # fmt: skip


SIZES = [(text, dpi) for text in (1.0, 1.25, 1.5) for dpi in (1.0, 1.5)]


@pytest.mark.parametrize(("text", "dpi"), SIZES)
def test_the_axis_fits_the_widest_price_and_tags_hold_their_text(text: float, dpi: float) -> None:
    for widest in ("8,888.88", "88,888.88", "888,888.88", "-88,888.88"):
        m = metrics(text, dpi, widest)
        assert m.axis >= m.pointer + m.price_width + 2  # the whole price, beside the flag's point
        assert m.tag_height > max(m.line, m.flag_line)  # a line of text and a margin
        assert m.tag_gap > m.tag_height
        assert m.header >= m.title_line + m.readout_line  # the readout has its own line under the title
        assert m.readout_y >= m.title_line
        assert m.foot > m.line  # the time labels are not clipped at the bottom
        assert m.inset > m.tag_height  # a marker label fits above the highest candle
        assert m.min_pitch == pytest.approx(6 * dpi)
    small, big = metrics(1.0, 1.0), metrics(text, dpi)
    if (text, dpi) != (1.0, 1.0):
        assert big.axis > small.axis and big.header > small.header and big.tag_height > small.tag_height and big.foot > small.foot


@pytest.mark.parametrize(("text", "dpi"), SIZES)
def test_stacked_tags_never_overlap_and_stay_inside_the_plot(text: float, dpi: float) -> None:
    m = metrics(text, dpi)
    top, bottom = float(m.header), m.header + 420.0 * dpi
    cases = [
        [top + 100, top + 101, top + 103, top + 200],  # three levels almost on one price
        [bottom - 3, bottom - 2, bottom - 1, bottom],  # a cluster at the very bottom
        [top, top + 1, top + 2],  # and at the very top
        [top - 40, bottom + 40],  # prices outside the plot
        [top + 50 + index * 3 for index in range(8)],
    ]
    for wanted in cases:
        placed = stack_tags(wanted, m.tag_gap, top, bottom)
        assert placed == sorted(placed)  # their order is kept
        boxes = [(0.0, at - m.tag_height / 2, 10.0, at + m.tag_height / 2) for at in placed]
        assert not any(overlaps(one, other) for index, one in enumerate(boxes) for other in boxes[index + 1 :])
        assert all(box[1] >= top - 1e-9 and box[3] <= bottom + 1e-9 for box in boxes)  # whole tags, inside the plot
    clear = [top + 60.0, top + 60.0 + 3 * m.tag_gap]
    assert stack_tags(clear, m.tag_gap, top, bottom) == clear  # tags with room are left on their prices
    assert stack_tags([], m.tag_gap, top, bottom) == []


@pytest.mark.parametrize(("text", "dpi"), SIZES)
def test_the_name_gutter_is_sized_from_the_merged_names_and_capped(text: float, dpi: float) -> None:
    scale = text * dpi
    plot = 900.0 * dpi
    assert name_gutter([], plot, scale) == display.pixels(12, scale)
    assert name_gutter([40.0 * scale, 80.0 * scale], plot, scale) == int(80.0 * scale + display.pixels(12, scale))
    assert name_gutter([5000.0], plot, scale) == min(display.pixels(190, scale), int(plot * 0.45))
    assert name_gutter([5000.0], 300.0, scale) <= 300.0 * 0.45 + 1  # the candles always keep most of a narrow chart


def test_names_at_one_price_share_a_tag_and_role_words_survive() -> None:
    flags = [
        Flag(300.0, 24449.25, ("Prev low",), display.MUTED, "reference"),
        Flag(300.4, 24449.25, ("Swing low",), display.PROTECTED, "protected"),
        Flag(120.0, 25265.75, ("Target 2.00R  +340.00", "Target 2.00R", "Target"), display.WHITE, "target", keep=True),
        Flag(120.9, 25265.75, ("Prev high",), display.MUTED, "reference"),
        Flag(200.0, None, ("POI: gap",), display.POI, "poi"),
        Flag(201.0, 24800.0, (), display.POI, "poi"),
        Flag(500.0, 24000.0, ("Far",), display.MUTED, "reference"),
        Flag(500.5, 24000.25, ("Near",), display.MUTED, "reference"),  # a pixel apart but another price: its own tag
    ]
    merged = merge_flags(flags)
    assert [flag.forms[0] if flag.forms else "" for flag in merged] == ["Target 2.00R  +340.00 = Prev high", "POI: gap", "Swing low = Prev low", "Far", "Near"]
    target, zone, swing = merged[0], merged[1], merged[2]
    assert target.forms[-1] == "Target" and target.keep and target.role == "target" and target.colour == display.WHITE
    assert zone.price == 24800.0  # the zone's name takes the price of the edge it sits on
    assert (swing.role, swing.colour, swing.keep) == ("protected", display.PROTECTED, False)
    assert [flag.at for flag in merged] == [flag.y for flag in merged]
    assert flags[0].forms == ("Prev low",)  # the flags handed in are not changed


def test_a_caption_takes_the_first_place_clear_of_labels_and_candles() -> None:
    spots = [(0.0, 0.0, 50.0, 10.0), (60.0, 0.0, 110.0, 10.0), (120.0, 0.0, 170.0, 10.0)]
    name, candle = (40.0, 0.0, 70.0, 10.0), (125.0, 5.0, 130.0, 40.0)
    assert choose_box(spots, [], []) == spots[0]
    assert choose_box(spots, [name], []) == spots[2]  # never over another label
    assert choose_box(spots, [], [(10.0, 0.0, 15.0, 30.0)]) == spots[1]  # nor over a candle when there is a free place
    assert choose_box(spots[2:], [], [candle]) == spots[2]  # a candle is covered only when nothing else is left
    assert choose_box(spots[:2], [name], [candle]) is None  # no room: the line's name carries the word instead
    assert choose_box([], [], []) is None


# --- text sizes a screen has room for ----------------------------------------------------


def test_only_text_sizes_that_fit_the_screen_are_offered() -> None:
    reason = display.TEXT_SIZE_REASON
    # 3440 x 1440 at 100 %: every size
    assert available_text_sizes(1.0, (3440, 1440)) == {"normal": "", "large": "", "larger": ""}
    # 1920 x 1080 at 100 %: the window may be 990 high; Large needs 1075, Larger 1290
    assert display.usable_screen((1920, 1080)) == (1880, 990)
    assert available_text_sizes(1.0, (1920, 1080)) == {"normal": "", "large": reason, "larger": reason}
    assert available_text_sizes(1.0, (1920, 1200)) == {"normal": "", "large": "", "larger": reason}
    # 1920 x 1080 at 150 %: the smallest size is always there, nothing above it
    assert available_text_sizes(1.5, (1920, 1080)) == {"normal": "", "large": reason, "larger": reason}
    assert available_text_sizes(2.0, (3440, 1440)) == {"normal": "", "large": reason, "larger": reason}
    assert available_text_sizes(1.25, (2560, 1440)) == {"normal": "", "large": "", "larger": reason}
    for dpi, screen in ((1.0, (3440, 1440)), (1.0, (1920, 1080)), (1.5, (1920, 1080)), (2.0, (3840, 2160)), (1.25, (2560, 1440))):
        for size, why in available_text_sizes(dpi, screen).items():
            assert (why == "") == text_size_fits(size, dpi, screen)
            if size != "normal":  # offered exactly when the window it needs is no taller than the screen allows
                assert text_size_fits(size, dpi, screen) == (display.pixels(display.MIN_WINDOW[1], dpi * TEXT_SIZES[size]) <= screen[1] - 90)
                assert text_size_fits(size, dpi, screen) == (min_window(dpi * TEXT_SIZES[size], screen)[1] == display.pixels(display.MIN_WINDOW[1], dpi * TEXT_SIZES[size]))
    assert list(available_text_sizes(1.0, (1920, 1080))) == list(TEXT_SIZES)  # all listed, in order: the menu shows why


def test_a_saved_or_stepped_text_size_is_clamped_to_the_screen() -> None:
    big, hd = (3440, 1440), (1920, 1080)
    assert [fit_text_size(size, 1.0, big) for size in TEXT_SIZES] == ["normal", "large", "larger"]
    assert [fit_text_size(size, 1.0, hd) for size in TEXT_SIZES] == ["normal", "normal", "normal"]  # saved on a larger screen
    assert [fit_text_size(size, 1.0, (1920, 1200)) for size in TEXT_SIZES] == ["normal", "large", "large"]
    assert fit_text_size("large", 1.5, hd) == "normal" and fit_text_size("larger", 2.0, big) == "normal"
    assert fit_text_size("nonsense", 1.0, big) == "normal"
    # Ctrl+= stops at the largest size that fits; Ctrl+- always works
    assert [step_text_size(size, 1, 1.0, big) for size in TEXT_SIZES] == ["large", "larger", "larger"]
    assert [step_text_size(size, -1, 1.0, big) for size in TEXT_SIZES] == ["normal", "normal", "large"]
    assert step_text_size("normal", 1, 1.5, hd) == "normal"  # 150 % on 1080p: Large is refused
    assert step_text_size("normal", 1, 1.0, (1920, 1200)) == "large" and step_text_size("large", 1, 1.0, (1920, 1200)) == "large"
    assert step_text_size("larger", -1, 1.5, hd) == "normal"  # down from a size that no longer fits lands on one that does
    assert step_text_size("larger", 1, 1.0, hd) == "normal"  # and "up" from one never stays above what fits


def test_the_charts_keep_a_drawable_height_on_a_screen_that_caps_the_window() -> None:
    for text, dpi in SIZES + [(1.0, 2.0)]:
        m = metrics(text, dpi)
        plot = m.min_height - m.header - m.px(2) - m.foot
        assert plot >= display.ESSENTIAL_FLAGS * m.tag_gap  # entry, stop, target and the next step's level stack inside it
        assert m.min_height > m.header + m.foot and m.min_width > m.axis + 10 * m.min_pitch
    m = metrics(1.0, 1.5)
    reserve = m.min_height
    # 1920 x 1080 at 150 %: the window is capped at 990; laid out in full the other regions would leave the charts too little
    assert needs_compact(990, 990 - 182, reserve) is True
    assert needs_compact(1290, 1290 - 375, reserve) is False  # the designed minimum: nothing has to give
    assert needs_compact(reserve + 600, 600, reserve) is False and needs_compact(reserve + 599, 600, reserve) is True
    assert display.room_message(True) == "Not enough room — Ctrl+− for smaller text"
    assert display.room_message(False).startswith("Not enough room") and "Ctrl" not in display.room_message(False)


# --- price flags on a short chart ----------------------------------------------------------


def flag(y: float, role: str, name: str = "") -> Flag:
    return Flag(y, 24000.0 - y, (name,) if name else (), display.WHITE, role, keep=role in ("entry", "stop", "target"))


@pytest.mark.parametrize(("text", "dpi"), SIZES + [(1.0, 2.0)])
def test_flags_never_leave_the_plot_and_the_plan_keeps_its_own(text: float, dpi: float) -> None:
    m = metrics(text, dpi)
    top = float(m.header + m.px(2))
    crowd = [
        flag(10, "reference", "Prev high"), flag(22, "poi"), flag(30, "poi", "POI: gap"), flag(38, "poi"), flag(52, "target", "Target"),
        flag(60, "confirm", "CISD"), flag(71, "next", "Next: close above"), flag(80, "entry", "Entry"), flag(84, "protected", "Swing low"),
        flag(96, "waiting", "Wait"), flag(110, "stop", "Stop"), flag(130, "reference", "Prev low"),
    ]  # fmt: skip
    crowd = [Flag(top + f.y * dpi, f.price, f.forms, f.colour, f.role, f.keep) for f in crowd]
    for slots in (0.5, 1, 2, 3, 4, 5, 7, 11.5, 12, 20):
        bottom = top + slots * m.tag_gap
        kept, dropped = fit_flags(crowd, m.tag_gap, top, bottom)
        assert len(kept) == min(len(crowd), int(slots)) and len(kept) + len(dropped) == len(crowd)
        assert [f.y for f in kept] == sorted(f.y for f in kept)  # still top to bottom
        assert sorted(id(f) for f in kept + dropped) == sorted(id(f) for f in crowd)
        placed = stack_tags([f.y for f in kept], m.tag_gap, top, bottom)
        boxes = [(0.0, at - m.tag_height / 2, 10.0, at + m.tag_height / 2) for at in placed]
        assert all(box[1] >= top - 1e-6 and box[3] <= bottom + 1e-6 for box in boxes), (slots, boxes)  # every flag whole, inside the plot
        assert not any(overlaps(one, other) for index, one in enumerate(boxes) for other in boxes[index + 1 :])
        roles = [f.role for f in kept]
        if slots >= display.ESSENTIAL_FLAGS:  # the shortest chart that is drawn holds these four
            assert {"entry", "stop", "target", "next"} <= set(roles)
        # nothing is dropped while something less important is kept
        worst_kept = max((display.MARK_PRIORITY.index(role) for role in roles), default=-1)
        assert all(display.MARK_PRIORITY.index(f.role) >= worst_kept for f in dropped)
        assert display.more_note(len(dropped)).startswith(f"+{len(dropped)} more level") if dropped else kept == crowd
    # the least plot of a drawn chart, at this size: exactly the four that matter, the rest counted
    plot_bottom = top + (m.min_height - m.header - m.px(2) - m.foot)
    kept, dropped = fit_flags(crowd, m.tag_gap, top, plot_bottom)
    assert [f.role for f in kept] == ["target", "next", "entry", "stop"] and len(dropped) == 8
    assert display.more_note(8) == "+8 more levels" and display.more_note(1) == "+1 more level"
    assert fit_flags([], m.tag_gap, top, plot_bottom) == ([], [])


# --- the display menus and the keys ----------------------------------------------------------


def test_the_footer_menu_holds_the_overlays_and_resets_every_chart() -> None:
    footer = display_menu(False)
    assert [(item.kind, item.label) for item in footer] == [
        ("heading", "SHOW ON THE CHARTS"),
        ("overlay", "Level names"), ("overlay", "Zones"), ("overlay", "Marker labels"), ("overlay", "Risk / reward box"),
        ("separator", ""),
        ("heading", "DIRECTION COLOURS  ·  candles, risk / reward, long / short"),
        ("scheme", "Green / red"), ("scheme", "Blue / orange   (colour-blind safe)"), ("scheme", "Monochrome   (hollow up, filled down)"),
        ("separator", ""),
        ("heading", "TEXT SIZE  ·  Ctrl+=  bigger   Ctrl+−  smaller   Ctrl+0  normal"),
        ("text_size", "Normal"), ("text_size", "Large"), ("text_size", "Larger"),
        ("separator", ""),
        ("command", "Reset zoom (all charts)"), ("command", "Reset display defaults"),
    ]  # fmt: skip
    assert [item.value for item in footer if item.kind == "overlay"] == list(OVERLAYS)  # all four, by the keys the state saves
    assert [item.value for item in footer if item.kind == "scheme"] == list(COLOUR_SCHEMES)
    assert [item.value for item in footer if item.kind == "text_size"] == list(TEXT_SIZES)
    assert [item.value for item in footer if item.kind == "command"] == ["reset_zoom_all", "reset_display"]
    assert all(item.enabled for item in footer)

    on_chart = display_menu(True)
    assert [item for item in on_chart if item.kind != "command"] == [item for item in footer if item.kind != "command"]
    assert [(item.label, item.value) for item in on_chart if item.kind == "command"] == [
        ("Reset zoom (this chart)", "reset_zoom_chart"), ("Reset display defaults", "reset_display"),
    ]  # fmt: skip

    # 1920 x 1080 at 150 %: the sizes that do not fit are listed, say why, and cannot be chosen
    capped = display_menu(False, available_text_sizes(1.5, (1920, 1080)))
    sizes = [(item.label, item.value, item.enabled) for item in capped if item.kind == "text_size"]
    assert sizes == [("Normal", "normal", True), ("Large   (does not fit this screen)", "large", False), ("Larger   (does not fit this screen)", "larger", False)]


def test_the_footer_menu_opens_inside_the_window() -> None:
    window = (100, 1140)  # the window's left and right edges on the screen
    button = (1030.0, 930.0, 1122.0, 952.0)  # "Display", at the window's right edge
    assert menu_origin(button, (350, 420), window) == (790, 508)  # moved left: it ends at the window's right edge
    assert menu_origin((200.0, 930.0, 292.0, 952.0), (350, 420), window) == (200, 508)  # room to the right: under the button's left edge
    assert menu_origin(button, (2000, 420), window)[0] == 100  # wider than the window: from its left edge
    x, _y = menu_origin(button, (350, 420), window)
    assert x + 350 <= window[1]


def test_control_keys_are_the_text_size_wherever_the_focus_is() -> None:
    for on_chart in (True, False):
        for key in ("equal", "plus", "KP_Add"):
            assert key_action(key, True, on_chart) == "text_bigger"  # Ctrl+= is the text size, on a focused chart too
        for key in ("minus", "KP_Subtract"):
            assert key_action(key, True, on_chart) == "text_smaller"
        for key in ("0", "KP_0"):
            assert key_action(key, True, on_chart) == "text_normal"
        assert key_action("d", True, on_chart) == ""
    for key in ("equal", "plus", "KP_Add"):  # a plain "=" zooms as "+" does: no Shift needed
        assert key_action(key, False, True) == "zoom_in" and key_action(key, False, False) == ""
    for key in ("minus", "KP_Subtract"):
        assert key_action(key, False, True) == "zoom_out" and key_action(key, False, False) == ""
    assert key_action("0", False, True) == "" and key_action("space", False, True) == ""


def test_the_look_needs_no_display() -> None:
    assert "tkinter" not in Path(display.__file__).read_text(encoding="utf-8")


def test_the_plan_lines_keep_their_role_words_and_take_over_a_missing_caption() -> None:
    from companion.app import ChartPane  # importing the widgets needs no display

    lines = {role: forms for role, _price, forms in ChartPane._tool_lines(TOOL)}
    assert lines["entry"] == ("Long entry", "Entry")
    assert lines["stop"][0] == "Stop  −10.00" and lines["stop"][-1] == "Stop"
    assert lines["target"][0] == "Target 2.00R  +20.00" and lines["target"][-1] == "Target"
    worded = {role: forms for role, _price, forms in ChartPane._tool_lines(TOOL, risk_word=True, reward_word=True)}
    assert worded["stop"][0].startswith("Stop · risk") and worded["target"][0].startswith("Target · reward")
    assert worded["stop"][-1] == "Stop" and worded["target"][-1] == "Target"
    bare = ChartPane._tool_lines(apply_overlays(chart(tool=TOOL), {"level_names": False}).tool)  # type: ignore[arg-type]
    assert [(role, price, forms) for role, price, forms in bare] == [("entry", 200.0, ("Entry",)), ("stop", 190.0, ("Stop",)), ("target", 220.0, ("Target",))]
    waiting = RiskRewardTool("short", True, 200.0, 210.0, 180.0, 5, 2.0, entry_note="Next: 5m close below")
    assert ChartPane._tool_lines(waiting)[0][2] == ("Next: 5m close below = entry", "Next = entry", "Entry")
    hit = RiskRewardTool("long", False, 200.0, 190.0, 220.0, 5, 2.0, outcome="stopped")
    assert "HIT" in ChartPane._tool_lines(hit)[1][2][0] and ChartPane._tool_lines(hit)[1][2][-1] == "Stop"
