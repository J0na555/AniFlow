"""Shared neo-brutalist form widget styling.

Centralizes the Tailwind classes applied to Django form controls so settings,
library, and future forms all render with one consistent ``neo-input`` look
instead of redefining widget classes per app.
"""

from __future__ import annotations

NEO_INPUT_CLASS = "neo-input w-full text-base h-14 focus:outline-none focus-visible:ring-0"

NEO_SELECT_CLASS = NEO_INPUT_CLASS

NEO_CHECKBOX_CLASS = (
    "w-6 h-6 rounded-none border-4 border-black bg-neo-white "
    "text-neo-ink accent-neo-accent focus-visible:ring-2 "
    "focus-visible:ring-black focus-visible:ring-offset-2"
)

NEO_TEXT_INPUT_ATTRS = {"class": NEO_INPUT_CLASS}
NEO_SELECT_ATTRS = {"class": NEO_SELECT_CLASS}
NEO_CHECKBOX_ATTRS = {"class": NEO_CHECKBOX_CLASS}
