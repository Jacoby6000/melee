#!/usr/bin/env python3

from argparse import ArgumentParser
import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

script_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.abspath(os.path.join(script_dir, ".."))


UNIT_KEYS_TO_DIFF = [
    "fuzzy_match_percent",
    "matched_code_percent",
    "matched_data_percent",
    "complete_code_percent",
    "complete_data_percent",
]

FUNCTION_KEY = "fuzzy_match_percent"


@dataclass
class Change:
    # None for aggregate (Total / unit) rows, hex string for functions.
    address: Optional[int]
    # Previous name when the symbol was renamed at this address, else None.
    old_name: Optional[str]
    # "Total" for the whole-report row, unit path, or function name.
    name: Optional[str]
    key: str
    from_value: float
    to_value: float

    @property
    def is_rename(self) -> bool:
        return self.old_name is not None and self.old_name != self.name


def format_float(value: float) -> str:
    if value < 100.0 and value > 99.99:
        value = 99.99
    return "%6.2f" % value


def format_address(address: Optional[int]) -> str:
    if address is None:
        return ""
    return "0x%08X" % address


# DESNOTE(jbarber, 2026-07-07): objdiff's `report changes` keys functions by
# name, so a rename shows up as two entries at the same virtual address: the old
# name with only a `from`, and the new name with only a `to`. Correlating by
# address lets us collapse those into a single row (and drop the bogus
# 100% -> 0% "regressions" that renames would otherwise produce).
def get_changes(changes_file: str) -> tuple[list[Change], list[Change]]:
    changes_file = os.path.relpath(changes_file, root_dir)
    with open(changes_file, "r") as f:
        changes_json = json.load(f)

    regressions: list[Change] = []
    progressions: list[Change] = []

    def record(change: Change) -> None:
        if change.from_value > change.to_value:
            regressions.append(change)
        elif change.to_value > change.from_value:
            progressions.append(change)

    def diff_aggregate(name: Optional[str], obj: dict) -> None:
        for key in UNIT_KEYS_TO_DIFF:
            from_value = obj.get("from", {}).get(key, 0.0)
            to_value = obj.get("to", {}).get(key, 0.0)
            record(
                Change(
                    address=None,
                    old_name=None,
                    name=name,
                    key=key.removesuffix("_percent"),
                    from_value=from_value,
                    to_value=to_value,
                )
            )

    diff_aggregate(None, changes_json)

    for unit in changes_json.get("units", []):
        unit_name = unit["name"]
        diff_aggregate(unit_name, unit)

        # Group this unit's functions by address so renames collapse to one row.
        by_address: dict[int, dict[str, object]] = {}
        order: list[int] = []
        for func in unit.get("functions", []):
            metadata = func.get("metadata") or {}
            raw_address = metadata.get("virtual_address")
            if raw_address is None:
                continue
            address = int(raw_address)
            entry = by_address.get(address)
            if entry is None:
                entry = {}
                by_address[address] = entry
                order.append(address)
            if "from" in func:
                entry["from_name"] = func["name"]
                entry["from_exists"] = True
                entry["from_value"] = func["from"].get(FUNCTION_KEY)
            if "to" in func:
                entry["to_name"] = func["name"]
                entry["to_exists"] = True
                entry["to_value"] = func["to"].get(FUNCTION_KEY)

        for address in order:
            entry = by_address[address]
            from_name = entry.get("from_name")
            to_name = entry.get("to_name")
            name = to_name or from_name
            old_name = from_name if from_name is not None else None

            from_value = entry.get("from_value")
            to_value = entry.get("to_value")
            # DESNOTE(jbarber, 2026-07-07): objdiff sometimes emits a side with a
            # size but no fuzzy_match_percent. When the symbol still exists on
            # that side (e.g. a rename), inherit the other side's value so we
            # report "unchanged" rather than a fabricated drop to 0%. Only treat
            # a value as 0% when the symbol is genuinely absent on that side
            # (a real add or removal).
            if from_value is None and entry.get("from_exists") and to_value is not None:
                from_value = to_value
            if to_value is None and entry.get("to_exists") and from_value is not None:
                to_value = from_value

            record(
                Change(
                    address=address,
                    old_name=old_name,
                    name=name,
                    key="fuzzy_match",
                    from_value=from_value if from_value is not None else 0.0,
                    to_value=to_value if to_value is not None else 0.0,
                )
            )

    return regressions, progressions


def generate_changes_plaintext(changes: list[Change]) -> str:
    if len(changes) == 0:
        return ""

    show_rename = any(c.is_rename for c in changes)
    name_cap = 48

    def cap(text: str) -> str:
        if len(text) > name_cap:
            return text[: name_cap - len("[...]")] + "[...]"
        return text

    rows: list[tuple[str, str, str, str, str]] = []
    for change in changes:
        address = format_address(change.address)
        name = cap(change.name if change.name is not None else "Total")
        old_name = cap(change.old_name) if change.is_rename else ""
        percents = (
            f"{format_float(change.from_value)}% -> {format_float(change.to_value)}%"
        )
        rows.append((address, old_name, name, change.key, percents))

    addr_w = max(len(r[0]) for r in rows)
    old_w = max(len(r[1]) for r in rows)
    name_w = max(len(r[2]) for r in rows)
    key_w = max(len(r[3]) for r in rows)

    out_lines = []
    for address, old_name, name, key, percents in rows:
        parts = [f"{address:>{addr_w}}"]
        if show_rename:
            parts.append(f"{old_name:>{old_w}}")
        parts.append(f"{name:>{name_w}}")
        parts.append(f"{key:<{key_w}}")
        parts.append(percents)
        out_lines.append(" | ".join(parts))

    return "\n".join(out_lines)


def generate_changes_markdown(changes: list[Change], description: str) -> str:
    if len(changes) == 0:
        return ""

    show_rename = any(c.is_rename for c in changes)
    name_max_len = 100

    out_lines = []
    out_lines.append("<details>")
    out_lines.append(
        f"<summary>Detected {len(changes)} {description} compared to the base:</summary>"
    )
    out_lines.append("")  # Must include a blank line before a table

    header = ["Address"]
    if show_rename:
        header.append("Renamed from")
    header += ["Name", "Type", "Before", "After"]
    out_lines.append("| " + " | ".join(header) + " |")
    out_lines.append("| " + " | ".join(["----"] * len(header)) + " |")

    for change in changes:
        name = change.name if change.name is not None else "Total"
        if change.name is not None:
            if len(name) > name_max_len:
                name = name[: name_max_len - len("...")] + "..."
            name = f"`{name}`"
        old_name = ""
        if change.is_rename:
            old_name = f"`{change.old_name}`"
        key = change.key.replace("_", " ").capitalize()

        cells = [format_address(change.address)]
        if show_rename:
            cells.append(old_name)
        cells += [
            name,
            key,
            f"{format_float(change.from_value)}%",
            f"{format_float(change.to_value)}%",
        ]
        out_lines.append("| " + " | ".join(cells) + " |")

    out_lines.append("</details>")

    return "\n".join(out_lines)


def main():
    parser = ArgumentParser(description="Format objdiff-cli report changes.")
    parser.add_argument(
        "report_changes_file",
        type=Path,
        help="""path to the JSON file containing the changes, generated by objdiff-cli.""",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="""Output file (prints to console if unspecified)""",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="""Includes progressions as well.""",
    )
    args = parser.parse_args()

    regressions, progressions = get_changes(args.report_changes_file)

    if args.output:
        markdown_output = generate_changes_markdown(regressions, "regressions")
        if args.all:
            markdown_output += generate_changes_markdown(progressions, "progressions")
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(markdown_output)
    else:
        if args.all:
            changes = progressions + regressions
        else:
            changes = regressions
        text_output = generate_changes_plaintext(changes)
        print(text_output)


if __name__ == "__main__":
    main()
