# ExtraLife MatrixPortal Display
# Author: St. John Johnson <st.john.johnson@gmail.com>
# Based on John Park's Metro Matrix Clock

import time
import board
import displayio
from adafruit_display_text.label import Label
from adafruit_bitmap_font import bitmap_font
from adafruit_matrixportal.matrixportal import MatrixPortal
from adafruit_datetime import datetime

DEBUG = False

# Get configuration settings from a secrets.py file
target_date = None
extralife_id = None
extralife_server = 'https://www.extra-life.org'
refresh_frequency = 30
hide_after = 26
hide_before = 999

try:
    from secrets import secrets # type: ignore

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

except ImportError:
    print("Configuration settings are kept in secrets.py, please add them there!")
    raise

if target_date == None or extralife_id == None:
    raise Exception("Target Date and ExtraLife ID Required")

print("Extra Life Countdown and Tracker")
print("Target Date: {}".format(target_date.isoformat()))
print("Extra Life ID: {}".format(extralife_id))
print("Extra Life Server: {}".format(extralife_server))
print("Refresh Frequency: {}s".format(refresh_frequency))
print("Hiding Counter After: {}h".format(hide_after))
print("Hiding Counter Before: {}h".format(hide_before))

# --- Display setup ---
matrix = MatrixPortal(
    status_neopixel=board.NEOPIXEL,
    debug=DEBUG
)
display = matrix.display

# --- Drawing setup ---
group = displayio.Group()  # Create a Group
bitmap = displayio.Bitmap(64, 32, 2)  # Create a bitmap object,width, height, bit depth
color = displayio.Palette(3)  # Create a color palette
color[0] = 0x000000  # black background
color[1] = 0x1AC1DD  # teal
color[2] = 0x85FF00  # greenish

# Create a TileGrid using the Bitmap and Palette
tile_grid = displayio.TileGrid(bitmap, pixel_shader=color)
group.append(tile_grid)  # Add the TileGrid to the Group
display.root_group = group
font = bitmap_font.load_font("/Micro5-Regular-21.bdf")

clock_label = Label(font, background_tight=True)
clock_label.color = color[1]
money_label = Label(font, background_tight=True)
money_label.color = color[2]

def time_until_target(target_date):
    """
    Calculates the difference between now and a target date.

    Args:
        target_date (datetime): The desination datetime.

    Returns:
        int: The hours until/from that date.
        int: The minutes until/from that date.
        int: The seconds until/from that date.
        int: The direction (-1 counting down, +1 counting up).
    """

    # Get the current UTC time
    current_time = datetime.now()

    # Calculate the difference
    time_difference = target_date - current_time
    direction = -1
    if time_difference.days < 0:
        direction = 1
        time_difference = current_time - target_date

    # Extract hours, minutes, and seconds
    seconds = time_difference.seconds
    hours = (time_difference.days * 24) + (seconds // 3600)
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    return hours, minutes, seconds, direction

def format_dollars(amount):
    """
    Converts money float to str

    Args:
        amount (float): The money to print.

    Returns:
        str: The money representation in the format $1,000.00.
    """
    # Convert the float to an integer
    amount_int = int(amount)
    # Convert the integer to a string with commas
    formatted = "${:,}".format(amount_int)
    return formatted

def money_raised():
    """
    Retrieves the current donations and goal

    Returns:
        str: The dollar donation total.
        str: The dollar donation goal.
        float: Percent of goal met.
    """

    url = "{}/api/participants/{}".format(extralife_server, extralife_id)
    print("Fetching text from {}".format(url))
    data = matrix.network.fetch(url).json()

    donation_total = data["sumDonations"]
    donation_goal = data["fundraisingGoal"]
    donation_percent = donation_total / donation_goal * 100

    return format_dollars(donation_total), format_dollars(donation_goal), donation_percent

def update_donation():
    """
    Updates the donation label with the current amounts.
    """
    total, goal, percent = money_raised()
    money_label.text = total


def update_time():
    """
    Updates the countdown/up clock with the current time.

    Returns:
        bool: Should we still display the time?
    """
    hours, minutes, seconds, direction = time_until_target(target_date)

    clock_label.text = "{hours}:{minutes:02d}:{seconds:02d}".format(
        hours=hours, minutes=minutes, seconds=seconds
    )
    bbx, bby, bbwidth, bbh = clock_label.bounding_box

    # Center the label
    center_label(clock_label, 1)

    # Hide if the hours exceeds configuration
    if direction < 0 and hours >= hide_before:
        return False
    if direction > 0 and hours >= hide_after:
        return False
    return True

def center_label(label, position):
    """
    Centers the label on the screen

    Args:
        label (Label): The label to align.
        position (int): The vertical position to place the label (1:top, 2:bottom, 3:center)
    """
    bbx, bby, bbwidth, bbh = label.bounding_box

    # Center the label horizontally
    label.x = round(display.width / 2 - bbwidth / 2) + 1

    # Position the label appropriately on the screen
    if position == 1: # Top
        label.y = (bbh // 2) + 1
    elif position == 2: # Bottom
        label.y = display.height - (bbh // 2) - 4
    elif position == 3: # Center
        label.y = (display.height // 2) - 2

    if DEBUG:
        print("Label bounding box: {},{},{},{}".format(bbx, bby, bbwidth, bbh))
        print("Label x: {} y: {}".format(label.x, label.y))

last_check = None
last_sync = None
# bootstrap the internet clock
matrix.get_local_time("UTC")
# add the labels
group.append(clock_label)
group.append(money_label)
# hide them
group[1].hidden = True
group[2].hidden = True
# get the latest data
update_donation()
if update_time():
    group[1].hidden = False
    money_label.color = color[2]
    center_label(money_label, 2)
else:
    group[1].hidden = True
    money_label.color = color[1]
    center_label(money_label, 3)
group[2].hidden = False

while True:
    # Check for donations every X seconds
    if last_check is None or time.monotonic() > last_check + refresh_frequency:
        try:
            update_donation()
            last_check = time.monotonic()
        except RuntimeError as e:
            print("Some error occured, retrying! -", e)

    # Sync time every 30 minutes
    if last_sync is None or time.monotonic() > last_sync + 1800:
        try:
            matrix.get_local_time("UTC")  # Synchronize Board's clock to Internet
            last_sync = time.monotonic()
        except RuntimeError as e:
            print("Some error occured, retrying! -", e)

    if update_time():
        group[1].hidden = False
        money_label.color = color[2]
        center_label(money_label, 2)
    else:
        group[1].hidden = True
        money_label.color = color[1]
        center_label(money_label, 3)

    time.sleep(1)
 # type: ignore