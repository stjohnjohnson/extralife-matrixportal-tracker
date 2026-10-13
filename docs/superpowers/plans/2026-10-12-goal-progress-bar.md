# Fundraising Goal Progress Bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display the approved two-pixel goal bar only on live current-year total cards.

**Architecture:** Display state carries an optional filled-column count, calculated
from the existing participant total and raw goal. A reusable 64x2 bitmap and
two-color palette live in the normal display group; hide them throughout donation
celebrations, preserving the existing animation snapshots and four-color palette.

**Tech Stack:** CircuitPython, displayio, existing Adafruit libraries; desktop
unittest and the existing BDF preview renderer.

**Spec:** [Approved design](../../plans/2026-10-12-goal-progress-bar-design.md).

## Global Constraints

- CircuitPython: 9.1.4; display: 64x32 RGB matrix.
- Do not add runtime dependencies or modify `secrets.py`.
- Keep embedded code small, readable, and compatible with CircuitPython.
- Preserve the existing text positions and rotation timing.
- Run `make lint` and `make test` before considering implementation complete.
- Deploy only through `make update`; deployment is a separate execution step.

## Review Focus

- Startup with no successful total request: no track or fill should appear.
- A valid zero goal replacing a positive goal: hide the previous bar immediately.
- A failed or malformed refresh: retain the previous total and goal together.
- Rotation from a total card to context: remove all bar pixels without moving text.
- Celebration snapshot failure/retry: keep the bar hidden while busy and restore it
  only with an eligible normal card after recovery.

## Files and responsibilities

- `lib_display.py`: bar geometry/color constants, fill calculation, card state.
- `code.py`: retain raw goal in cache, allocate and update the normal bar layer.
- `tools/render_display_previews.py`: render the same bar in normal-card previews.
- `tests/test_lib_display.py`: numeric boundaries and phase/card eligibility.
- `tests/test_runtime.py`: cache, layering, rotation, and celebration integration.
- `tests/test_display_previews.py`: exact bottom-row pixels and text separation.
- `tests/test_celebration_previews.py`: preserve bar-free celebration transitions.
- `README.md`: describe the feature and its visibility rules.

### Task 1: Model goal progress and eligible cards

**Interfaces:**
- Add `GOAL_BAR_HEIGHT = 2` and `GOAL_TRACK_COLOR = 0x17280C` in `lib_display.py`.
- Add `goal_bar_width(total_raised, fundraising_goal, width=64)`, returning an
  integer in `0..width`, or `None` when the inputs are unavailable or invalid.
- Extend `DisplayState.__init__` with optional `goal_width=None`.
- Extend `render_state` with optional `fundraising_goal=None`; existing callers
  retain their existing text and layout. Only countdown slots 0 and 2, game-day
  slot 0, and post-event slot 0 receive the calculated `goal_width`.

- [x] **Step 1: Add failing display tests.** In `tests/test_lib_display.py`, test
  the exact fill values below. Test missing total/goal, zero and negative goals,
  nonnumeric/bool inputs, negative totals, and NaN/infinite values return `None`.
  Positive goals with zero donations return `0`, distinguishing unavailable data.

  ```python
  for total, expected in ((0, 0), (250, 16), (730, 47), (1000, 64), (1170, 64)):
      self.assertEqual(goal_bar_width(total, 1000), expected)
  ```

  Extend `RenderStateTests.render` to accept `fundraising_goal`. At goal 2000 and
  total 1000, assert `goal_width == 32` only for the four eligible phase/slot
  combinations (two countdown cards, game day, and the post-event total card).
  All other slots return `None`; eligible slots also return `None`
  for missing total or zero goal. Assert text/alignment remain unchanged.

- [x] **Step 2: Run `python3 -m unittest tests.test_lib_display -v`.** Expect
  failures identifying the missing helper/state behavior.

- [x] **Step 3: Implement the interfaces above in `lib_display.py`.** Reject
  invalid inputs before division; use `int(clamped_fraction * width + 0.5)` for
  nearest-pixel fill. Use explicit phase/card eligibility, never label parsing
  or money-color inference, since historical and all-time cards also show money.

- [x] **Step 4: Run `python3 -m unittest tests.test_lib_display -v`.** Expect all
  existing and new display tests to pass.

- [x] **Step 5: Commit only this task's display logic and tests.** Suggested
  subject: `feat: model fundraising goal progress on current-year cards`.
  Include a body explaining card eligibility and unavailable/zero-goal handling.

### Task 2: Render the bar and verify runtime integration

**Interfaces:**
- Consume Task 1's `state.goal_width` and shared constants.
- Extend the existing `donation_cache` and `money_raised(cached=True)` return
  tuple to five fields: formatted total, formatted goal, percent, raw total,
  raw goal. Initialize raw total and raw goal to `None`; replace the cache only
  after both fetched values validate. Update the docstring and sole consumer.
- Allocate `goal_bitmap = displayio.Bitmap(64, GOAL_BAR_HEIGHT, 2)` once, with
  palette index 0 as the dim track and index 1 as the existing money green.
- Append its TileGrid `goal_bar` to `normal_group`, with `y=30` and initially
  hidden. `update_display()` hides it when `state.goal_width is None` or a
  celebration is active; otherwise paints two identical track/fill rows.
- Preserve the four-color animation bitmaps and label-only `snapshot()`.
- Make preview `render_card(font, state, text_transform=display_text)` include
  the optional bar without changing its public signature or label origins.

- [x] **Step 1: Add failing integration tests.** Extend the existing Simulation
  with optional request outcomes and display observations, keeping defaults
  unchanged. In `tests/test_runtime.py`, assert: unavailable startup hides the
  layer; a successful 730/1000 response fills 47 pixels per row; a subsequent
  zero goal hides it; failed/malformed refreshes preserve all five cache fields;
  context/history/all-time cards hide it; an eligible card restores it. Cover
  countdown, game-day, and post-event phases and their existing rotation slots.
  Observe that the bar is hidden from `start_celebration` through exit and visible
  again after completion on eligible cards. Extend the existing snapshot-failure
  retry test to assert the same visibility recovery.

- [x] **Step 2: Add failing pixel preview tests.** In
  `tests/test_display_previews.py`, compare every row above y=30 against the
  same state with `goal_width=None`. Assert y=30 and y=31 contain the exact
  green/track split for widths 0, 47, and 64. Verify `999:59:59`, `$999,999`, and
  the post-event total/year pair have no text pixels in the reserved rows.
  In `tests/test_celebration_previews.py`, assert celebration hold and transition
  snapshots remain bar-free and preserve the existing pixel expectations.

- [x] **Step 3: Run `python3 -m unittest tests.test_runtime
  tests.test_display_previews tests.test_celebration_previews -v` as one shell
  command.** Expect new tests to fail on missing cache/layer/preview behavior.

- [x] **Step 4: Implement the runtime interfaces in `code.py`.** Feed raw goal
  into `render_state`, reuse the allocated layer, and preserve atomic cache
  updates. Hide the bar before celebration snapshots, including exit snapshots;
  the normal render after finish/error recovery decides whether to restore it.
  Keep API requests, refresh timers, label positioning, and animation code intact.

- [x] **Step 5: Update `tools/render_display_previews.py`.** Draw the shared
  geometry/colors only when `state.goal_width is not None`. Keep the existing
  default preview states bar-free for snapshot tests. Add
  `render_goal_progress_previews(output_dir)` returning written paths, called
  by the existing preview CLI; write `goal-progress.png` comparing 0%, 73%,
  100%, and 117% using eligible states. Test the file and pixel states in
  `tests/test_display_previews.py`.

- [x] **Step 6: Update `README.md`.** Describe the two-pixel bar, eligible cards,
  goal from the existing API, zero/missing-goal suppression, celebration hiding,
  and retained progress after refresh failures. No new configuration setting.

- [x] **Step 7: Run `make lint` and `make test`.** Both must exit 0. If the
  default interpreter lacks ruff/black, use a temporary desktop virtualenv and
  the Makefile's existing `PYTHON` override; do not add device dependencies.
  Run `python3 tools/render_display_previews.py /tmp/goal-progress-previews
  --celebrations` as one command and inspect normal and celebration sheets.

- [x] **Step 8: Commit this task's runtime, previews, documentation, and tests.**
  Suggested subject: `feat: render two-pixel fundraising goal bar`.
  Include a body explaining the separate normal layer and integration checks.

## Physical-device follow-through

Implementation completed on `codex/goal-progress-bar` in commits `8e03b53` and
`7994f1d`. `make lint` and `make test` pass using the temporary desktop Python
environment (93 tests plus the mock display). Goal and celebration previews
were rendered and inspected. Independent whole-branch review found no critical,
important, or minor issues and confirmed readiness to merge. Hardware appearance
and device runtime/memory remain unverified until deployment; supported display
dimensions remain the specified 64x32.

- [ ] After implementation review and deployment authorization, use `make update`.
- [ ] Check physical visibility of the bright fill and dim track and separation
  from text. Confirm countdown/count-up and post-event eligibility, removal on
  context cards, and hiding/restoration around a real donation celebration.
- [ ] Use `make serial` or `make serial-log` if behavior differs from previews;
  report any device check that cannot be completed instead of claiming it passed.
