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

from lib_celebration import (
    ENTRANCE_SECONDS,
    EXIT_SECONDS,
    FRAME_SECONDS,
    GAP_SECONDS,
    Celebration,
    paint_text,
    slide_frame,
    sparkle_pixels,
    star_thresholds,
    starburst_frame,
)
from lib_display import (
    RotationClock,
    display_colors,
    display_phase,
    display_text,
    format_dollars,
    render_state,
    single_line_position,
    two_line_positions,
)
from lib_donations import DonationTracker, PollSchedule, api_server, fetch_json

DEBUG = False

# Get configuration settings from a secrets.py file
target_date = None
extralife_id = None
extralife_server = "https://dd.extra-life.org"
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

extralife_server = api_server(extralife_server)

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
bitmap = displayio.Bitmap(64, 32, 4)
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
normal_group = displayio.Group()
normal_group.append(clock_label)
normal_group.append(money_label)
group.append(normal_group)

# Celebration labels and snapshots are reused, rather than allocated per frame.
gift_label = Label(font, background_tight=True)
gift_label.color = color[2]
donor_label = Label(font, background_tight=True)
donor_label.color = color[1]
donation_group = displayio.Group()
donation_group.append(gift_label)
donation_group.append(donor_label)
donation_group.hidden = True
group.append(donation_group)
old_snapshot = displayio.Bitmap(64, 32, 4)
new_snapshot = displayio.Bitmap(64, 32, 4)
reveal_thresholds = star_thresholds()
sparkles = displayio.Bitmap(64, 32, 4)
sparkle_colors = displayio.Palette(4)
sparkle_colors[3] = color[3]
sparkle_colors.make_transparent(0)
group.append(displayio.TileGrid(sparkles, pixel_shader=sparkle_colors))
# Caching
donation_cache = ["--", "--", 0.0, None]
tracker = DonationTracker()
schedule = PollSchedule(refresh_frequency)
rotation_clock = RotationClock()
active_celebration = None
celebration_donation = None
celebration_started_at = 0
next_celebration_at = 0
last_stage = None


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
        data = fetch_json(matrix.network, url)

        donation_total = data["sumDonations"]
        donation_goal = data["fundraisingGoal"]
        if (
            not isinstance(donation_total, (int, float))
            or not 0 <= donation_total <= 1e9
        ):
            raise ValueError("Invalid donation total")
        if not isinstance(donation_goal, (int, float)) or not 0 <= donation_goal <= 1e9:
            raise ValueError("Invalid fundraising goal")
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


def update_display():
    """Render the current phase and rotation card."""
    _, _, _, total_raised_value = money_raised()
    now = datetime.now()
    monotonic_now = time.monotonic()
    phase = display_phase(
        target_date=target_date,
        now=now,
        hide_after=hide_after,
        hide_before=hide_before,
    )
    rotation_elapsed = rotation_clock.update(
        phase,
        monotonic_now,
        paused=active_celebration is not None,
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

    top_text = display_text(state.top_text)
    bottom_text = display_text(state.bottom_text)
    if clock_label.text != top_text:
        clock_label.text = top_text
    if money_label.text != bottom_text:
        money_label.text = bottom_text
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


def snapshot(target, top, bottom):
    """Capture visible label pixels in the shared four-color palette."""
    target.fill(0)
    for label in (top, bottom):
        color_index = 1
        for index in (1, 2, 3):
            if label.color == color[index]:
                color_index = index
                break
        paint_text(target, font, label.text, (label.x, label.y), color_index)


def start_celebration(now):
    """Pause rotation and prepare one donor's entrance."""
    global active_celebration, celebration_donation, celebration_started_at, last_stage

    celebration_donation = tracker.pop()
    if celebration_donation is None:
        return
    # Assign before label work so display-error recovery can put this donor back.
    active_celebration = True
    update_display()
    snapshot(old_snapshot, clock_label, money_label)
    gift_label.text = display_text(celebration_donation.amount_text)
    gift_label.color = color[2] if gift_label.text.startswith("$") else color[1]
    donor_label.text = display_text(celebration_donation.name)
    active_celebration = Celebration(gift_label.bounding_box, donor_label.bounding_box)
    top_position, bottom_position = active_celebration.positions(0)
    gift_label.x, gift_label.y = top_position
    donor_label.x, donor_label.y = bottom_position
    snapshot(new_snapshot, gift_label, donor_label)
    normal_group.hidden = True
    donation_group.hidden = True
    celebration_started_at = time.monotonic()
    last_stage = None


def finish_celebration(now, retry=False):
    """Always clear effects and restore the normal display groups."""
    global active_celebration, celebration_donation, next_celebration_at, last_stage

    if retry and celebration_donation is not None:
        tracker.pending.insert(0, celebration_donation)
    active_celebration = None
    celebration_donation = None
    next_celebration_at = now + (5 if retry else GAP_SECONDS)
    last_stage = None
    bitmap.fill(0)
    sparkles.fill(0)
    donation_group.hidden = True
    normal_group.hidden = False


def update_celebration(now):
    """Paint only the moving layer; labels remain reusable display objects."""
    global last_stage

    elapsed = now - celebration_started_at
    stage = active_celebration.stage(elapsed)
    if stage == "done":
        finish_celebration(now)
        update_display()
        return
    if stage == "entrance":
        starburst_frame(
            bitmap,
            old_snapshot,
            new_snapshot,
            reveal_thresholds,
            elapsed / ENTRANCE_SECONDS,
        )
    elif stage == "exit":
        if last_stage != "exit":
            sparkles.fill(0)
            snapshot(old_snapshot, gift_label, donor_label)
            update_display()
            snapshot(new_snapshot, clock_label, money_label)
            donation_group.hidden = True
        slide_frame(
            bitmap,
            old_snapshot,
            new_snapshot,
            (elapsed - active_celebration.exit_at) / EXIT_SECONDS,
        )
    else:
        if last_stage == "entrance":
            bitmap.fill(0)
        donation_group.hidden = False
        top_position, bottom_position = active_celebration.positions(elapsed)
        gift_label.x, gift_label.y = top_position
        donor_label.x, donor_label.y = bottom_position
        sparkles.fill(0)
        if stage == "sparkles":
            for x, y in sparkle_pixels(elapsed - ENTRANCE_SECONDS):
                sparkles[y * 64 + x] = 3
    last_stage = stage


def run_forever():
    """Keep animation frames separate from rate-aware blocking network jobs."""
    last_normal_at = None
    last_frame_at = None
    while True:
        now = time.monotonic()
        job = schedule.ready(
            now,
            busy=active_celebration is not None,
            feed_has_room=tracker.has_room,
        )
        if job is not None:
            success = False
            try:
                if job == "sync":
                    matrix.get_local_time("UTC")
                elif job == "total":
                    money_raised(False)
                else:
                    data = fetch_json(
                        matrix.network,
                        tracker.url(extralife_server, extralife_id),
                        empty_list=True,
                    )
                    tracker.accept_page(data)
                    del data
                success = True
            except (
                RuntimeError,
                OSError,
                ValueError,
                TypeError,
                KeyError,
                MemoryError,
            ) as error:
                print("{} request failed, backing off: {}".format(job, error))
            schedule.record(job, time.monotonic(), success)

        now = time.monotonic()
        try:
            if active_celebration is not None:
                if last_frame_at is None or now - last_frame_at >= FRAME_SECONDS:
                    update_celebration(now)
                    last_frame_at = now
            else:
                if last_normal_at is None or now - last_normal_at >= 1:
                    update_display()
                    last_normal_at = now
                if tracker.pending and now >= next_celebration_at:
                    start_celebration(now)
                    now = time.monotonic()
                    update_celebration(now)
                    last_frame_at = now
        except (RuntimeError, OSError, ValueError, TypeError, MemoryError) as error:
            print("Display update error, retrying: {}".format(error))
            finish_celebration(now, retry=True)
        if active_celebration is not None:
            frame_cost = time.monotonic() - last_frame_at
            time.sleep(max(0.001, FRAME_SECONDS - frame_cost))
        else:
            time.sleep(0.1)


if __name__ == "__main__":
    run_forever()
# type: ignore
