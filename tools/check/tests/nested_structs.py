#!/usr/bin/env python3
"""Tests for the nested-structs check. Run: python3 tools/check/tests/nested_structs.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from check.nested_structs import nested_structs_fix, nested_structs_scan  # noqa: E402

RESOURCE_ROOT = Path(__file__).resolve().parent / "resources" / "nested_structs"
SCAN_DIR = RESOURCE_ROOT / "scan"
FIX_DIR = RESOURCE_ROOT / "fix"


# ---------------------------------------------------------------------------
# Scan tests (detection)
# ---------------------------------------------------------------------------


class NestedStructsScanTest(unittest.TestCase):
    """Detection cases loaded from ``resources/nested_structs/scan/``.

    Each fixture provides a source and ``// violations:`` metadata listing the
    1-based line numbers expected to be flagged (empty for no findings).
    """

    def run_case(self, name: str) -> None:
        source, expected_violations = _load_scan_case(name)
        actual = [f.line for f in nested_structs_scan(Path("test.c"), source)]
        self.assertEqual(actual, expected_violations, f"{name}: violation lines mismatch")


def _make_scan_test(name: str) -> object:
    def test(self: "NestedStructsScanTest") -> None:
        self.run_case(name)
    test.__name__ = f"test_{name}"
    return test

def _load_scan_case(name: str) -> tuple[str, list[int]]:
    """Read a scan fixture from ``resources/nested_structs/scan/<name>.c``.

    File format::

        // violations: 2, 3
        <source>

    ``violations`` is a comma-separated list of 1-based line numbers expected
    to be flagged (empty meaning no findings).
    """
    raw = (SCAN_DIR / f"{name}.c").read_text()
    lines = raw.split("\n")
    meta, body = _strip_meta(lines)
    violations_str = meta.get("violations", "")
    violations = [int(x) for x in violations_str.split(",") if x.strip()]
    source = "\n".join(body) + "\n"
    return source, violations



for _path in sorted(SCAN_DIR.glob("*.c")):
    setattr(
        NestedStructsScanTest,
        f"test_{_path.stem}",
        _make_scan_test(_path.stem),
    )


# ---------------------------------------------------------------------------
# Fix tests (reformatting)
# ---------------------------------------------------------------------------


class NestedStructsRewriteTest(unittest.TestCase):
    """Reformatting regression cases loaded from ``resources/nested_structs/fix/``.

    Each fixture provides input and expected output separated by ``// ---``.
    Every assertion checks the extraction count, the full rewritten source,
    that the result has no remaining violations (unless
    ``// remaining-violations:`` is given), and that a second pass leaves the
    output untouched.
    """

    def run_case(self, name: str) -> None:
        source, expected, count, remaining = _load_fix_case(name)
        fixed, n = nested_structs_fix(Path("test.c"), source)
        self.assertEqual(n, count, f"{name}: extraction count mismatch")
        self.assertEqual(fixed, expected, f"{name}: rewritten source mismatch")
        self.assertEqual(
            [f.line for f in nested_structs_scan(Path("test.c"), fixed)],
            remaining,
            f"{name}: remaining violations mismatch",
        )
        refixed, rn = nested_structs_fix(Path("test.c"), fixed)
        self.assertEqual((refixed, rn), (fixed, 0), f"{name}: second pass not a no-op")


def _make_fix_test(name: str) -> object:
    def test(self: "NestedStructsRewriteTest") -> None:
        self.run_case(name)
    test.__name__ = f"test_{name}"
    return test

def _load_fix_case(name: str) -> tuple[str, str, int, list[int]]:
    """Read a fix fixture from ``resources/nested_structs/fix/<name>.c``.

    File format::

        // count: <N>
        // remaining-violations: a, b  (optional; lines still flagged after fix)
        <input source>
        // ---
        <expected output>

    Returns ``(source, expected, count, remaining_violations)``.
    """
    raw = (FIX_DIR / f"{name}.c").read_text()
    sep = "\n// ---\n"
    idx = raw.find(sep)
    if idx == -1:
        raise AssertionError(f"missing '// ---' separator in {name}.c")
    head = raw[:idx]
    expected = raw[idx + len(sep):]
    lines = head.split("\n")
    meta, body = _strip_meta(lines)
    if "count" not in meta:
        raise AssertionError(f"missing '// count:' metadata in {name}.c")
    count = int(meta["count"])
    remaining_str = meta.get("remaining-violations", "")
    remaining = [int(x) for x in remaining_str.split(",") if x.strip()]
    source = "\n".join(body) + "\n"
    return source, expected, count, remaining




for _path in sorted(FIX_DIR.glob("*.c")):
    setattr(
        NestedStructsRewriteTest,
        f"test_{_path.stem}",
        _make_fix_test(_path.stem),
    )


def _strip_meta(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """Pull leading ``// key: value`` comments off ``lines``.

    Returns ``(metadata, remaining_lines)``.
    """
    meta: dict[str, str] = {}
    i = 0
    while i < len(lines) and lines[i].lstrip().startswith("//"):
        stripped = lines[i].strip()
        if ":" in stripped:
            key, _, value = stripped.removeprefix("//").partition(":")
            meta[key.strip()] = value.strip()
        i += 1
    return meta, lines[i:]


if __name__ == "__main__":
    unittest.main()
