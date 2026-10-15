# AGENTS.md

## Project Overview
CircuitPython app for Adafruit MatrixPortal M4 that displays an Extra Life countdown and donation total on a 64x32 RGB matrix. The main runtime file is `code.py`.

## Targets
- CircuitPython: 9.1.4 (installed on the MatrixPortal).
- Hardware: Adafruit MatrixPortal M4 + 64x32 RGB matrix.

## Key Files
- `code.py` — main application logic and display updates.
- `Micro5-Regular-21.bdf` — bundled font used for labels.
- `secrets.py` — user-provided configuration (not committed).
- `secrets.py.example` — sample configuration for new users.

## Configuration
- `secrets.py` must define WiFi, AIO credentials, Extra Life participant ID, and `target_date`.
- Do not modify or commit `secrets.py`. If a sample is needed, update `secrets.py.example`.

## Style & Formatting
- Use 4-space indentation and keep string quotes consistent with existing code (double quotes).
- Prefer small, readable functions; avoid heavy abstraction in embedded code.
- Aim for a max line length around 88–100 characters.
- If you add linting locally, prefer `ruff` (lint) and `black` (format) with a 88–100 line length. Do not add runtime deps to the device.

## Behavior Expectations
- Countdown transitions to count-up at the target date.
- Donation total is refreshed on a timer; time sync every 30 minutes.
- UI should remain legible on 64x32; avoid layout changes that overflow.

## Testing / Validation
- No automated tests yet. Validate changes by running on device.
- If adding test scaffolding, keep it optional and desktop-only (e.g., simple CPython helper scripts).
- Before considering work complete, ensure `make lint` and `make test` both pass.
- For debugging, use `make serial` (interactive) or `make serial-log` (capture to `/tmp/circuitpy.log`).

## Deployment
- Use `make update` for deploying changes to the MatrixPortal device.
- Avoid manual file copies to the mounted CIRCUITPY drive unless explicitly requested.

## Contribution Guidelines
- Keep file edits minimal and focused.
- Keep design and implementation plans local and untracked; do not commit them.
- Preserve CircuitPython compatibility (avoid CPython-only modules).
