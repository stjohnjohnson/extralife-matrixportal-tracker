# extralife-matrixportal-tracker
Tracking donations for ExtraLife on a 32x64 RGB Matrix via an Adafruit Matrix Portal.

![Countdown in Action](https://github.com/user-attachments/assets/621276b6-5512-4727-baa7-6012e2433044)

## Features

The display adapts to four phases of the annual fundraiser:

- Before the countdown, it slowly rotates through the prior-year result, the
  live all-time total, the number of days until the event, and `stj.watch`.
- Below 1,000 remaining hours, the countdown and current-year donation amount
  appear every other card alongside UCSF and website context.
- During the 25-hour stream and one-hour celebration window, the display stays
  fixed on the count-up timer and live donation amount.
- After hour 26, it rotates through the current-year result, its UCSF purpose,
  the live all-time total, and `stj.watch` through the end of the year.

Cards remain visible for 15 seconds and change without animation so the display
stays calm when it appears in the background of video calls.

A two-pixel green progress bar appears below the current-year donation total
on countdown/count-up cards and the post-event current-year result card. It
fills toward the fundraising goal from the existing participant API, with a
dim green track for the remainder. The fill stops at 100% while the dollar
total continues to reflect donations above the goal. A zero or unavailable
goal hides the bar; failed refreshes retain the last valid progress.
Historical, all-time, and context cards hide it. Donation celebrations hide
the bar through their exit, then eligible normal cards restore it.

New donations interrupt the display year-round, one gift at a time. An expanding
gold arcade starburst reveals the green amount above the blue donor name over
1.8 seconds. Small gold sparkles play for 1.7 seconds before scrolling begins;
long names pan once while the amount stays still. Oversized amounts pan in a
separate beat. After at least 5.5 seconds on the card, it slides up over 0.9 seconds
and the normal display returns for two seconds before the next gift. The
interrupted card keeps its remaining rotation time;
countdown/count-up clocks still reflect the actual time.

Only public donor fields are displayed. A hidden name becomes `ANON`, and a
hidden or malformed amount becomes `THANKS!`. Unsupported font characters become `?`; names
are uppercased and capped at 48 characters with `...` when shortened. Registration
fees are skipped.

The first successful donation check establishes a baseline without replaying old
gifts. Tracking is kept in RAM: restarting establishes a new baseline, so gifts
received while the device was off are not replayed. Pages contain ten records,
the queue holds twelve gifts, and polling pauses when that queue fills, resuming
from the last accepted gift. Recent IDs are retained for a two-minute overlap,
up to 128 IDs. This catches ordinary overlapping responses, but donations that
arrive backdated beyond that window or behind an evicted ID's cursor may be
missed. Each forward-paged gift is still queued individually during a burst.

Donation and total requests share a 15-second cooldown and each refresh no faster
than every 30 seconds. Requests and time sync wait until the animation finishes;
network failures keep the last total visible and retry with bounded backoff.
After the baseline is established, records without a usable ID/timestamp are
logged and excluded so valid neighboring gifts can proceed. Invalid response
shapes, unordered pages, wholly unusable pages, and invalid initial baselines
retry without advancing tracking state.

## Hardware

The attached device is an Adafruit MatrixPortal S3 running CircuitPython 9.1.4
with a 64x32 RGB matrix.

Parts:
 - [Adafruit MatrixPortal S3](https://www.adafruit.com/product/5778)
 - [64x32 RGB LED Matrix - 4mm pitch](https://www.adafruit.com/product/2278)
 - [Black LED Diffusion Acrylic Panel - 10.2"x5.1"](https://www.adafruit.com/product/4749)
 - [Clear Adhesive Squares](https://www.adafruit.com/product/4813)
 - [Adjustable Bent-Wire Stand](https://www.adafruit.com/product/1679)
 - [Vertical Wall Power Supply USB C - 5V/3A with Switch](https://www.adafruit.com/product/5801)

## Installation

1. Follow [this guide](https://learn.adafruit.com/network-connected-metro-rgb-matrix-clock/code-the-matrix-clock) to install CircuitPython on the MatrixPortal.
2. Add the following libraries:
 - `adafruit_bitmap_font`
 - `adafruit_bus_device`
 - `adafruit_display_text`
 - `adafruit_esp32spi`
 - `adafruit_io`
 - `adafruit_matrixportal`
 - `adafruit_portalbase`
 - `adafruit_connection_manager.mpy`
 - `adafruit_datetime.mpy`
 - `adafruit_debouncer.mpy`
 - `adafruit_fakerequests.mpy`
 - `adafruit_lis3dh.mpy`
 - `adafruit_requests.mpy`
 - `neopixel.mpy`
3. Create your `secrets.py` file as listed below.
4. Run `make install` to install `code.py`, `lib_display.py`, `lib_donations.py`,
   `lib_celebration.py`, and `Micro5-Regular-21.bdf` with the local `lib` bundle.
5. Enjoy!

## Configuration

Create a `secrets.py` file with the following contents:
```python
secrets = {
    # WiFi Network Configuration
    'ssid': '_your_ssid_',
    'password': '_your_wifi_password_',

    # AIO API Config for local time
    'aio_username': '_your_aio_username_',
    'aio_key': '_your_aio_key_',
    
    # ExtraLife Participant ID from
    # https://www.extra-life.org/index.cfm?fuseaction=donordrive.participant&participantID=_your_id_
    'extralife_id': '_your_participant_id_',
    # ISO8601 formatted UTC time for your game day event
    'target_date': '2026-11-07T16:30:00',
}
```

### Optional Settings

```python
{
    # How many seconds between ExtraLife checks (minimum 30)
    'refresh_frequency': 30,
    # What ExtraLife server to use
    'extralife_server': 'https://dd.extra-life.org',
    # How many hours should it count up?
    'hide_after': 26,
    # Start the countdown below this many remaining hours. A value of 1000
    # permits the largest displayable countdown, 999:59:59.
    'hide_before': 1000,
    # Previous calendar year's final total
    'last_raised': 28783,
    'last_year': 2025,
    # Lifetime total through the end of the previous calendar year
    'lifetime_raised': 88488,
}
```

The planned stream lasts 25 hours. The default `hide_after` value keeps the
count-up visible for one additional hour while the stream wraps up and
celebrates.

The API now uses `https://dd.extra-life.org`. Existing configurations that still
specify `https://www.extra-life.org` or `https://extra-life.org` automatically
use the new API host; custom servers retain their configured host.

### Annual Rollover

Extra Life switches the participant API to the new campaign on January 1. At
the start of each calendar year, update `extralife_id`, `target_date`,
`last_raised`, `last_year`, and `lifetime_raised` in your local `secrets.py`.
The lifetime value should include every completed campaign through the end of
the prior year; the display adds the API's live current-year amount to it.

## Inspiration

Based on the Metro_Matrix_Clock from John Park at Adafruit Industries (MIT License)
 - [Source code](https://github.com/adafruit/Adafruit_Learning_System_Guides/blob/main/Metro_Matrix_Clock/code.py)
 - [Guide](https://learn.adafruit.com/network-connected-metro-rgb-matrix-clock/overview)

## Font

I've bundled a slightly modified version of the [Micro 5 font](https://fonts.google.com/specimen/Micro+5).  I've specified a specific font size, added an extra pixel column to the `1` to ensure they are monospaced.
## Development

### Linting & Formatting

This repo uses `ruff` (lint) and `black` (format) for local development:

```bash
make lint
make format
make test
```

### Deployment

Assuming your device is mounted at `/Volumes/CIRCUITPY`:

```bash
make install
make update
```

You can override the mount point:

```bash
make install CIRCUITPY=/path/to/device
```

### Serial Monitor

```bash
make serial
```

You can override the detected device:

```bash
make serial SERIAL=/dev/cu.usbmodemXXXX
```

To capture logs to a file:

```bash
make serial-log
```

This writes to `/tmp/circuitpy.log` until you press Ctrl-C.

### Mock Display (CPython)

You can run a tiny CPython-only mock to sanity-check the time/label logic:

```bash
python3 tools/mock_display.py
```

`make test` also exercises the donation queue, animation pixels/timing, and the
actual device loop using desktop display/network doubles. These checks do not
measure animation speed, available RAM, or live API behavior on the device.

Render every normal card and the donation entrance, scrolling, privacy fallbacks,
and return using the bundled BDF font, plus a goal progress comparison at 0%,
73%, 100%, and 117%:

```bash
python3 tools/render_display_previews.py /tmp/display-previews --celebrations
```

The implementation plan and hardware validation checklist are tracked in
[GitHub issue #2](https://github.com/stjohnjohnson/extralife-matrixportal-tracker/issues/2).
