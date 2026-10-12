.PHONY: lint format test install update serial serial-log

PYTHON ?= python3
CIRCUITPY ?= /Volumes/CIRCUITPY
SERIAL ?= $(shell ls /dev/cu.usbmodem* 2>/dev/null | head -n 1)
INSTALL_FILES = code.py lib_display.py lib_donations.py lib_celebration.py Micro5-Regular-21.bdf lib
UPDATE_FILES = code.py lib_display.py lib_donations.py lib_celebration.py Micro5-Regular-21.bdf

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m black . --check

format:
	$(PYTHON) -m ruff check . --fix
	$(PYTHON) -m black .

test:
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) tools/mock_display.py

install:
	rsync -av $(INSTALL_FILES) $(CIRCUITPY)/
	@if [ -f secrets.py ]; then rsync -av secrets.py $(CIRCUITPY)/; else echo "secrets.py not found; skipping."; fi

update:
	rsync -av $(UPDATE_FILES) $(CIRCUITPY)/
	@if [ -f secrets.py ]; then rsync -av secrets.py $(CIRCUITPY)/; else echo "secrets.py not found; skipping."; fi

serial:
	@if [ -z "$(SERIAL)" ]; then echo "No /dev/cu.usbmodem* device found. Set SERIAL=/dev/cu.usbmodemXXXX"; exit 1; fi
	screen $(SERIAL) 115200

serial-log:
	@if [ -z "$(SERIAL)" ]; then echo "No /dev/cu.usbmodem* device found. Set SERIAL=/dev/cu.usbmodemXXXX"; exit 1; fi
	@echo "Logging $(SERIAL) to /tmp/circuitpy.log (Ctrl-C to stop)"
	stty -f $(SERIAL) 115200 raw -echo
	cat $(SERIAL) | tee /tmp/circuitpy.log
