# ExtraLife MatrixPortal Display
# Author: St. John Johnson <st.john.johnson@gmail.com>
# Based on John Park's Metro Matrix Clock

import time

import board
import displayio
from adafruit_bitmap_font import bitmap_font
from adafruit_datetime import datetime
from adafruit_display_text.label import Label
from adafruit_matrixportal.matrixportal import MatrixPortal

from lib_display import (
    display_colors,
    display_phase,
    display_text,
    format_dollars,
    render_state,
    single_line_position,
    track_rotation,
    two_line_positions,
)

DEBUG = False

# Get configuration settings from a secrets.py file
target_date = None
extralife_id = None
extralife_server = "https://www.extra-life.org"
refresh_frequency = 30
hide_after = 26
hide_before = 1000
last_raised = 0
last_year = 0
lifetime_raised = 0

try:
    from secrets import secrets  # type: ignore # noqa: I001

    if "target_date" in secrets:
        target_date = datetime.fromisoformat(secrets["target_date"])
    if "extralife_id" in secrets:
        extralife_id = secrets["extralife_id"]
    if "extralife_server" in secrets:
        extralife_server = secrets["extralife_server"]
    if "refresh_frequency" in secrets:
        refresh_frequency = secrets["refresh_frequency"]
    if "hide_after" in secrets:
        hide_after = secrets["hide_after"]
    if "hide_before" in secrets:
        hide_before = secrets["hide_before"]
    if "last_raised" in secrets:
        last_raised = secrets["last_raised"]
    if "last_year" in secrets:
        last_year = secrets["last_year"]
    if "lifetime_raised" in secrets:
        lifetime_raised = secrets["lifetime_raised"]

except ImportError:
    print("Configuration settings are kept in secrets.py, please add them there!")
    raise

if target_date is None or extralife_id is None:
    raise Exception("Target Date and ExtraLife ID Required")

print("Extra Life Countdown and Tracker")
print("Target Date: {}".format(target_date.isoformat()))
print("Extra Life ID: {}".format(extralife_id))
print("Extra Life Server: {}".format(extralife_server))
print("Refresh Frequency: {}s".format(refresh_frequency))
print("Hiding Counter After: {}h".format(hide_after))
print("Hiding Counter Before: {}h".format(hide_before))
print("Last Raised: ${} in {}".format(last_raised, last_year))
print("Lifetime Raised Through Last Year: ${}".format(lifetime_raised))

# --- Display setup ---
matrix = MatrixPortal(status_neopixel=board.NEOPIXEL, debug=DEBUG)
display = matrix.display

# --- Drawing setup ---
group = displayio.Group()  # Create a Group
bitmap = displayio.Bitmap(64, 32, 2)  # Create a bitmap object,width, height, bit depth
color = displayio.Palette(4)  # Create a color palette
color[0] = 0x000000  # black background
color[1] = 0x1AC1DD  # teal context
color[2] = 0x85FF00  # green money
color[3] = 0xFFB000  # gold accent

# Create a TileGrid using the Bitmap and Palette
tile_grid = displayio.TileGrid(bitmap, pixel_shader=color)
group.append(tile_grid)  # Add the TileGrid to the Group
display.root_group = group
font = bitmap_font.load_font("/Micro5-Regular-21.bdf")
# Labels
clock_label = Label(font, background_tight=True)
clock_label.color = color[1]
money_label = Label(font, background_tight=True)
money_label.color = color[2]
# Caching
donation_cache = ["--", "--", 0.0, None]


def money_raised(cached=True):
    """
    Retrieves the current donations and goal

    Args:
        cached (bool): Pull from cache?

    Returns:
        str: The dollar donation total.
        str: The dollar donation goal.
        float: Percent of goal met.
        float: The raw donation total.
    """
    global donation_cache
    if not cached:
        url = "{}/api/participants/{}".format(extralife_server, extralife_id)
        print("Fetching text from {}".format(url))
        data = matrix.network.fetch(url).json()

        donation_total = data["sumDonations"]
        donation_goal = data["fundraisingGoal"]
        donation_percent = 0.0
        if donation_goal > 0:
            donation_percent = donation_total / donation_goal * 100

        donation_cache = [
            format_dollars(donation_total),
            format_dollars(donation_goal),
            donation_percent,
            donation_total,
        ]

    return donation_cache[0], donation_cache[1], donation_cache[2], donation_cache[3]


active_phase = None
phase_started_at = None


def update_display():
    """Render the current phase and rotation card."""
    global active_phase, phase_started_at

    _, _, _, total_raised_value = money_raised()
    now = datetime.now()
    monotonic_now = time.monotonic()
    phase = display_phase(
        target_date=target_date,
        now=now,
        hide_after=hide_after,
        hide_before=hide_before,
    )
    active_phase, phase_started_at, rotation_elapsed = track_rotation(
        current_phase=phase,
        monotonic_now=monotonic_now,
        active_phase=active_phase,
        phase_started_at=phase_started_at,
    )

    state = render_state(
        target_date=target_date,
        now=now,
        total_raised=total_raised_value,
        hide_after=hide_after,
        hide_before=hide_before,
        last_raised=last_raised,
        last_year=last_year,
        lifetime_raised=lifetime_raised,
        rotation_elapsed=rotation_elapsed,
    )

    clock_label.text = display_text(state.top_text)
    money_label.text = display_text(state.bottom_text)
    clock_label.color, money_label.color = display_colors(
        state,
        context_color=color[1],
        money_color=color[2],
        accent_color=color[3],
    )
    display_labels(state, clock_label, money_label)


def display_labels(state, top, bottom=None):
    """Position one or two labels using their visible glyph bounds."""
    if bottom is None:
        top.x, top.y = single_line_position(
            top.bounding_box,
            display_width=display.width,
            display_height=display.height,
        )
        return

    top_position, bottom_position = two_line_positions(
        top.bounding_box,
        bottom.bounding_box,
        display_width=display.width,
        display_height=display.height,
        top_align=state.top_align,
        bottom_align=state.bottom_align,
    )
    top.x, top.y = top_position
    bottom.x, bottom.y = bottom_position

    if DEBUG:
        print("Top box: {} position: {},{}".format(top.bounding_box, top.x, top.y))
        print(
            "Bottom box: {} position: {},{}".format(
                bottom.bounding_box,
                bottom.x,
                bottom.y,
            )
        )


# Last Syncs
last_check = None
last_sync = None
# add the labels
group.append(clock_label)
group.append(money_label)

while True:
    # Check for donations every X seconds
    if last_check is None or time.monotonic() > last_check + refresh_frequency:
        try:
            money_raised(False)
            last_check = time.monotonic()
        except (RuntimeError, OSError) as e:
            print("Some error occurred, retrying! -", e)

    # Sync time every 30 minutes
    if last_sync is None or time.monotonic() > last_sync + 1800:
        try:
            matrix.get_local_time("UTC")  # Synchronize Board's clock to Internet
            last_sync = time.monotonic()
        except (RuntimeError, OSError) as e:
            print("Some error occurred, retrying! -", e)

    try:
        update_display()
    except (RuntimeError, OSError) as e:
        print("Display update error, retrying! -", e)

    time.sleep(1)
# type: ignore
