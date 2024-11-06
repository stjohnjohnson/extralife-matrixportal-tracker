# ExtraLife MatrixPortal Display
# Author: St. John Johnson <st.john.johnson@gmail.com>
# Based on John Park's Metro Matrix Clock

import time
import board
import displayio
import terminalio
from adafruit_display_text.label import Label
from adafruit_bitmap_font import bitmap_font
from adafruit_matrixportal.network import Network
from adafruit_matrixportal.matrix import Matrix
from adafruit_matrixportal.matrixportal import MatrixPortal
from adafruit_datetime import datetime

DEBUG = False

# Get configuration settings from a secrets.py file
target_date = None
extralife_id = None
extralife_server = 'https://www.extra-life.org'
refresh_frequency = 30

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

except ImportError:
    print("Configuration settings are kept in secrets.py, please add them there!")
    raise

print("Extra Life Countdown and Tracker")
print("Target Date: {}".format(target_date.isoformat()))
print("Extra Life ID: {}".format(extralife_id))
print("Extra Life Server: {}".format(extralife_server))
print("Refresh Frequency: {}".format(refresh_frequency))

# --- Display setup ---
matrix = MatrixPortal(
    status_neopixel=board.NEOPIXEL,
    debug=DEBUG
)
display = matrix.display

# --- Drawing setup ---
group = displayio.Group()  # Create a Group
bitmap = displayio.Bitmap(64, 32, 2)  # Create a bitmap object,width, height, bit depth
color = displayio.Palette(4)  # Create a color palette
color[0] = 0x000000  # black background
color[1] = 0x1AC1DD  # teal
color[2] = 0x85FF00  # greenish

# Create a TileGrid using the Bitmap and Palette
tile_grid = displayio.TileGrid(bitmap, pixel_shader=color)
group.append(tile_grid)  # Add the TileGrid to the Group
display.root_group = group

if not DEBUG:
    font = bitmap_font.load_font("/Micro5-Regular-21.bdf") 
else:
    font = terminalio.FONT

clock_label = Label(font, background_tight=True)
clock_label.color = color[1]
money_label = Label(font, background_tight=True)
money_label.color = color[2]

def time_until_target(target_date):
    # Get the current UTC time
    current_time = datetime.now()
    
    # Calculate the difference
    time_difference = target_date - current_time
    if time_difference.days < 0:
        time_difference = current_time - target_date
    
    # Extract hours, minutes, and seconds
    seconds = time_difference.seconds
    hours = (time_difference.days * 24) + (seconds // 3600)
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    return hours, minutes, seconds

def format_dollars(amount):
    # Convert the float to an integer
    amount_int = int(amount)
    # Convert the integer to a string with commas
    formatted = "${:,}".format(amount_int)
    return formatted


def money_raised():
    print("Fetching text from")
    data = matrix.network.fetch(
        url="{}/api/participants/{}".format(extralife_server, extralife_id)
    ).json()
    donation_total = data["sumDonations"]
    donation_goal = data["fundraisingGoal"]
    donation_percent = donation_total / donation_goal * 100

    return format_dollars(donation_total), format_dollars(donation_goal), donation_percent

def update_donation():
    total, goal, percent = money_raised()
    
    money_label.text = "{total}".format(
        total=total
    )
    bbx, bby, bbwidth, bbh = money_label.bounding_box

    # Center the label
    money_label.x = round(display.width / 2 - bbwidth / 2) + 1
    money_label.y = display.height - (bbh // 2) - 3

    if DEBUG:
        print("Money Label bounding box: {},{},{},{}".format(bbx, bby, bbwidth, bbh))
        print("Money Label x: {} y: {}".format(money_label.x, money_label.y))

def update_time(*, hours=None, minutes=None, seconds=None, show_colon=False):
    hours, minutes, seconds = time_until_target(target_date)

    clock_label.text = "{hours}:{minutes:02d}:{seconds:02d}".format(
        hours=hours, minutes=minutes, seconds=seconds
    )
    bbx, bby, bbwidth, bbh = clock_label.bounding_box

    # Center the label
    clock_label.x = round(display.width / 2 - bbwidth / 2) + 1
    clock_label.y = bbh // 2
    if DEBUG:
        print("Clock Label bounding box: {},{},{},{}".format(bbx, bby, bbwidth, bbh))
        print("Clock Label x: {} y: {}".format(clock_label.x, clock_label.y))

last_check = None
last_sync = None
# bootstrap the internet clock
matrix.get_local_time("UTC")
# get the latest data
update_time()
update_donation()
# add the clock label to the group
group.append(clock_label)  
group.append(money_label)

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

    update_time()
    time.sleep(1)
 # type: ignore