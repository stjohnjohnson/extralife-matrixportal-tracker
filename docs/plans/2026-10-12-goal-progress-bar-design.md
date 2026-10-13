# Fundraising goal progress bar

Approved on October 12, 2026. Addresses [issue #1](https://github.com/stjohnjohnson/extralife-matrixportal-tracker/issues/1).

## Display behavior

Show a continuous progress bar across the bottom two rows of the 64x32 matrix
(x=0..63, y=30..31). Filled pixels use the existing money green, `0x85FF00`;
the remaining track uses the preview's dim green, `0x17280C`. Fill runs left to
right, with the same length on both rows. Text positions, colors, content,
countdown/count-up transitions, and 15-second rotation timing stay unchanged.

Only cards displaying the live current-year donation total show the bar:

- Countdown phase: both timer/total cards in the rotation.
- Game-day phase: the fixed count-up/total card.
- Post-event phase: the current-year total/year card.

The pre-countdown rotation, historical totals, all-time totals, UCSF context,
and website cards do not show the bar. The bar adds no percentage text or
additional rotation card.

## Data and failures

Use the participant API's existing `sumDonations` and `fundraisingGoal` values;
do not introduce another request or configuration setting. Preserve the raw
goal alongside the existing cached values so a zero goal can be distinguished
from valid zero-percent progress.

Fill length is the nearest whole pixel to `64 * total / goal`, clamped to
0..64. Thus 0% shows only the dim track, 73% fills 47 columns, and 100% or
greater fills all 64 columns. Above-goal donations retain the actual dollar
total in the existing label.

Hide the whole bar until the total and a valid, positive goal are available.
A zero goal hides the bar. Failed or invalid refreshes retain the last
successful total and goal together; startup failures keep the bar hidden.

## Rendering and celebrations

Keep card eligibility and fill calculation in the desktop-testable display
logic. Use a small, reusable bar bitmap with its own two-color palette in the
normal display group. This preserves the existing four-color animation
palette and snapshots and avoids allocation on each update.

Hide the bar from the start of a donation celebration through its exit.
Celebration snapshots continue to contain only the existing text. Restore
the bar on the next normal render if the resumed card is eligible. It must
also recover after a celebration error without leaving pixels on an
ineligible card. Donation queue behavior and rotation pause/resume timing
stay unchanged.

## Constraints and validation

- CircuitPython: 9.1.4; display: 64x32 RGB matrix.
- Do not add runtime dependencies or modify `secrets.py`.
- Keep embedded code small, readable, and compatible with CircuitPython.
- Preserve the existing text positions and rotation timing.
- Run `make lint` and `make test` before considering implementation complete.
- Deploy only through `make update`; deployment is a separate execution step.

Desktop checks cover eligibility across every phase/card, unavailable and zero
goals, 0%, partial progress, 100%, above goal, stale cached data after failures,
and celebration hide/restore behavior. BDF-backed previews must confirm that
the two bottom rows do not overlap timer or currency glyphs, including the
largest supported strings. Check the physical matrix for brightness, dim-track
visibility, text separation, and restoration after a live donation; desktop
previews cannot establish physical LED appearance.
