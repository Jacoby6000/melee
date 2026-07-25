"""Per-check suppressions via comments

Syntax:

    // checks:disable nested-structs
    // checks:disable jobj-flags, assert-macros
    // checks:enable
    // checks:enable nested-structs
"""

import re

_DIRECTIVE_RE = re.compile(r"//\s*checks:\s*(disable|enable)\b\s*(.*)")


def _parse_names(args: str) -> list[str]:
    return [a.strip() for a in args.split(",") if a.strip()]


def suppressed_ranges(text: str, check: str) -> list[tuple[int, int]]:
    """Return inclusive 1-based line ranges where ``check`` is suppressed."""
    lines = text.split("\n")
    suppressed_all = False
    active: set[str] = set()
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for i, raw in enumerate(lines):
        lineno = i + 1
        m = _DIRECTIVE_RE.search(raw)
        if m:
            action = m.group(1)
            names = _parse_names(m.group(2))
            if action == "disable":
                if not names:
                    suppressed_all = True
                else:
                    active.update(names)
            else:  # enable
                if not names:
                    suppressed_all = False
                    active.clear()
                else:
                    for nm in names:
                        active.discard(nm)
        disabled = suppressed_all or check in active
        if disabled and start is None:
            start = lineno
        elif not disabled and start is not None:
            ranges.append((start, lineno - 1))
            start = None
    if start is not None:
        ranges.append((start, len(lines)))
    return ranges


def is_suppressed(check: str, line: int, text: str) -> bool:
    """Return ``True`` if ``line`` of ``text`` is suppressed for ``check``."""
    for s, e in suppressed_ranges(text, check):
        if s <= line <= e:
            return True
    return False
