"""Tiny CPython mock for the MatrixPortal display logic."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from time import sleep

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from lib_display import render_state


def main():
    target_date = datetime(2026, 11, 7, 16, 30, tzinfo=timezone.utc)
    hide_after = 26
    hide_before = 1000
    last_raised = 28783
    last_year = 2025
    lifetime_raised = 88488

    total_raised = 1234.56
    for iteration in range(5):
        state = render_state(
            target_date=target_date,
            now=datetime.now(timezone.utc),
            total_raised=total_raised,
            hide_after=hide_after,
            hide_before=hide_before,
            last_raised=last_raised,
            last_year=last_year,
            lifetime_raised=lifetime_raised,
            rotation_elapsed=iteration * 15,
        )
        print(state.top_text)
        print(state.bottom_text)
        print("-" * 16)
        sleep(1)
        total_raised += 10


if __name__ == "__main__":
    main()
