"""Shared display logic for CircuitPython and CPython."""

PHASE_PRE = "pre"
PHASE_COUNTDOWN = "countdown"
PHASE_GAME_DAY = "game_day"
PHASE_POST = "post"
CARD_SECONDS = 15
ALIGN_CENTER = "center"
ALIGN_LEFT = "left"
ALIGN_RIGHT = "right"
KERNED_T = "\ue000"
URL_TEXT = "STJ.WATCH"
URL_GLYPHS = ("\ue001", "\ue002", "\ue003", "\ue004", "\ue005")
URL_J = "\ue006"
URL_GLYPH_TEXT = (
    URL_GLYPHS[0]
    + "T"
    + URL_J
    + URL_GLYPHS[1]
    + "W"
    + URL_GLYPHS[2]
    + "T"
    + URL_GLYPHS[3]
    + URL_GLYPHS[4]
)


def _pair_adjusted_text(text):
    """Return text with the visual AT-pair adjustment."""
    rendered = []
    previous = None
    for character in text:
        if previous == "A" and character == "T":
            rendered.append(KERNED_T)
        else:
            rendered.append(character)
        previous = character
    return "".join(rendered)


def display_text(text):
    """Return label glyph text with display-specific spacing adjustments."""
    if text == URL_TEXT:
        return URL_GLYPH_TEXT
    return _pair_adjusted_text(text)


def label_x(bounding_box, *, display_width, alignment, edge_margin=1):
    """Return the label origin that places its visible bounds horizontally."""
    x_offset, _, width, _ = bounding_box
    if alignment == ALIGN_LEFT and width <= display_width - edge_margin * 2:
        visible_left = edge_margin
    elif alignment == ALIGN_RIGHT and width <= display_width - edge_margin * 2:
        visible_left = display_width - edge_margin - width
    else:
        visible_left = (display_width - width) // 2
    return visible_left - x_offset


def two_line_positions(
    top_box,
    bottom_box,
    *,
    display_width,
    display_height,
    top_align,
    bottom_align,
    gap=3,
):
    """Return origins that center two visible bounds around a fixed gap."""
    _, top_y_offset, _, top_height = top_box
    _, bottom_y_offset, _, bottom_height = bottom_box
    block_height = top_height + gap + bottom_height
    block_top = (display_height - block_height) // 2
    top_position = (
        label_x(top_box, display_width=display_width, alignment=top_align),
        block_top - top_y_offset,
    )
    bottom_position = (
        label_x(bottom_box, display_width=display_width, alignment=bottom_align),
        block_top + top_height + gap - bottom_y_offset,
    )
    return top_position, bottom_position


def single_line_position(bounding_box, *, display_width, display_height):
    """Return the origin that centers one label's visible bounds."""
    _, y_offset, _, height = bounding_box
    return (
        label_x(
            bounding_box,
            display_width=display_width,
            alignment=ALIGN_CENTER,
        ),
        (display_height - height) // 2 - y_offset,
    )


def display_phase(*, target_date, now, hide_before: int, hide_after: int) -> str:
    """Return the annual display phase for the supplied time."""
    if now < target_date:
        remaining = target_date - now
        remaining_seconds = remaining.days * 86400 + remaining.seconds
        if remaining_seconds >= hide_before * 3600:
            return PHASE_PRE
        return PHASE_COUNTDOWN

    elapsed = now - target_date
    elapsed_seconds = elapsed.days * 86400 + elapsed.seconds
    if elapsed_seconds < hide_after * 3600:
        return PHASE_GAME_DAY
    return PHASE_POST


def track_rotation(*, current_phase, monotonic_now, active_phase, phase_started_at):
    """Return updated phase tracking and elapsed rotation seconds."""
    if current_phase != active_phase or phase_started_at is None:
        return current_phase, monotonic_now, 0.0
    return active_phase, phase_started_at, monotonic_now - phase_started_at


class RotationClock:
    """Pause card dwell time without pausing the real countdown/count-up."""

    def __init__(self):
        self.phase = None
        self.elapsed = 0.0
        self.updated_at = None
        self.paused = False

    def update(self, phase, now, paused=False):
        if phase != self.phase or self.updated_at is None:
            self.phase = phase
            self.elapsed = 0.0
        elif not self.paused:
            self.elapsed += max(0, now - self.updated_at)
        self.updated_at = now
        self.paused = paused
        return self.elapsed


class DisplayState:
    def __init__(
        self,
        *,
        phase: str,
        top_text: str,
        bottom_text: str,
        top_is_money: bool = False,
        bottom_is_money: bool = False,
        top_is_accent: bool = False,
        bottom_is_accent: bool = False,
        top_align: str = ALIGN_CENTER,
        bottom_align: str = ALIGN_CENTER,
    ):
        self.phase = phase
        self.top_text = top_text
        self.bottom_text = bottom_text
        self.top_is_money = top_is_money
        self.bottom_is_money = bottom_is_money
        self.top_is_accent = top_is_accent
        self.bottom_is_accent = bottom_is_accent
        self.top_align = top_align
        self.bottom_align = bottom_align


def _display_color(*, is_money, is_accent, context_color, money_color, accent_color):
    if is_money:
        return money_color
    if is_accent:
        return accent_color
    return context_color


def display_colors(state, *, context_color, money_color, accent_color):
    """Return the top and bottom colors for a rendered display state."""
    colors = {
        "context_color": context_color,
        "money_color": money_color,
        "accent_color": accent_color,
    }
    top_color = _display_color(
        is_money=state.top_is_money,
        is_accent=state.top_is_accent,
        **colors,
    )
    bottom_color = _display_color(
        is_money=state.bottom_is_money,
        is_accent=state.bottom_is_accent,
        **colors,
    )
    return top_color, bottom_color


def _time_parts(delta):
    seconds = delta.seconds
    hours = delta.days * 24 + seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds %= 60
    return hours, minutes, seconds


def format_dollars(amount: float) -> str:
    """Converts money float to str in the format $1,000."""
    return f"${int(amount):,}"


def _live_dollars(total_raised):
    if total_raised is None:
        return "--"
    return format_dollars(total_raised)


def _card(phase, values):
    (
        top_text,
        bottom_text,
        top_is_money,
        bottom_is_money,
        top_is_accent,
        bottom_is_accent,
        top_align,
        bottom_align,
    ) = values
    return DisplayState(
        phase=phase,
        top_text=top_text,
        bottom_text=bottom_text,
        top_is_money=top_is_money,
        bottom_is_money=bottom_is_money,
        top_is_accent=top_is_accent,
        bottom_is_accent=bottom_is_accent,
        top_align=top_align,
        bottom_align=bottom_align,
    )


def render_state(
    *,
    target_date,
    now,
    total_raised,
    hide_after: int,
    hide_before: int,
    last_raised: float,
    last_year: int,
    lifetime_raised: float,
    rotation_elapsed: float,
) -> DisplayState:
    phase = display_phase(
        target_date=target_date,
        now=now,
        hide_before=hide_before,
        hide_after=hide_after,
    )
    live_text = _live_dollars(total_raised)
    all_time_text = "--"
    if total_raised is not None:
        all_time_text = format_dollars(lifetime_raised + total_raised)

    if phase == PHASE_PRE:
        remaining = target_date - now
        days = remaining.days + (1 if remaining.seconds else 0)
        cards = (
            (
                format_dollars(last_raised),
                f"IN {last_year}",
                True,
                False,
                False,
                False,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
            (
                all_time_text,
                "ALL TIME",
                True,
                False,
                False,
                False,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
            (
                "RAISED",
                "FOR UCSF",
                False,
                False,
                False,
                True,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
            (
                f"{days} DAYS",
                "TO GO",
                False,
                False,
                True,
                False,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
            (
                "MORE AT",
                "STJ.WATCH",
                False,
                False,
                False,
                True,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
        )
    elif phase == PHASE_COUNTDOWN:
        hours, minutes, seconds = _time_parts(target_date - now)
        timer = f"{hours}:{minutes:02d}:{seconds:02d}"
        cards = (
            (
                timer,
                live_text,
                False,
                True,
                False,
                False,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
            (
                "RAISED",
                "FOR UCSF",
                False,
                False,
                False,
                True,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
            (
                timer,
                live_text,
                False,
                True,
                False,
                False,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
            (
                "MORE AT",
                "STJ.WATCH",
                False,
                False,
                False,
                True,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
        )
    elif phase == PHASE_GAME_DAY:
        hours, minutes, seconds = _time_parts(now - target_date)
        cards = (
            (
                f"{hours}:{minutes:02d}:{seconds:02d}",
                live_text,
                False,
                True,
                False,
                False,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
        )
    else:
        cards = (
            (
                live_text,
                f"IN {target_date.year}",
                True,
                False,
                False,
                False,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
            (
                "RAISED",
                "FOR UCSF",
                False,
                False,
                False,
                True,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
            (
                all_time_text,
                "ALL TIME",
                True,
                False,
                False,
                False,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
            (
                "MORE AT",
                "STJ.WATCH",
                False,
                False,
                False,
                True,
                ALIGN_CENTER,
                ALIGN_CENTER,
            ),
        )

    slot = int(rotation_elapsed // CARD_SECONDS) % len(cards)
    return _card(phase, cards[slot])
