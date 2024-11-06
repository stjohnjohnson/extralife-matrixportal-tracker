# extralife-matrixportal-tracker
Tracking donations for ExtraLife on a 32x64 RGB Matrix via an Adafruit Matrix Portal.

![Countdown in Action](https://github.com/user-attachments/assets/621276b6-5512-4727-baa7-6012e2433044)

## Features

This tracker will display the number of hours, minutes, and seconds until your 24 hour game day event.  Once it hits that time, it will begin to count up so you can track how long you've been gaming for.

Additionally, it will show the current donation total.

## Hardware

To build this I got the following items:
 - [Adafruit Matrix Portal S3](https://www.adafruit.com/product/5778)
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
4. Copy the `code.py` and `Micro5-Regular-21.bdf` files.
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
    'target_date': '2024-11-02T17:30:00',
}
```

### Optional Settings

```python
{
    # How many seconds between ExtraLife checks
    'refresh_frequency': 30,
    # What ExtraLife server to use
    'extralife_server': 'https://www.extra-life.org',
    # How many hours should it count up?
    'hide_after': 26,
    # How many hours should it count down?
    'hide_before': 999,
}
```

## Inspiration

Based on the Metro_Matrix_Clock from John Park at Adafruit Industries (MIT License)
 - [Source code](https://github.com/adafruit/Adafruit_Learning_System_Guides/blob/main/Metro_Matrix_Clock/code.py)
 - [Guide](https://learn.adafruit.com/network-connected-metro-rgb-matrix-clock/overview)

## Font

I've bundled a slightly modified version of the [Micro 5 font](https://fonts.google.com/specimen/Micro+5).  I've specified a specific font size, added an extra pixel column to the `1` to ensure they are monospaced.