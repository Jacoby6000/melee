#!/usr/bin/env python3
"""Nested-struct check backed by the clang AST (libclang).

CONTRIBUTING.md (``#structs``) forbids struct/union *definitions* that appear
inside another struct/union body. This check detects them via
``cursor.lexical_parent`` — the decisive signal is a struct/union declaration
whose lexical parent is itself a struct/union.

A nested struct with no tag and no field declarator cannot be auto-named and is
left flagged for manual review (this is the "poorly understood struct"
placeholder exception in CONTRIBUTING.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clang.cindex import (
    Config,
    Cursor,
    CursorKind,
    File,
    Index,
    SourceLocation,
    SourceRange,
    TranslationUnit,
)

_NESTED_MESSAGE = (
    "Nested struct definition: move it out of the parent and reference it "
    "by name (CONTRIBUTING.md #structs)"
)
_MAX_FIX_PASSES = 256

_CONTAINER_KINDS = frozenset({CursorKind.STRUCT_DECL, CursorKind.UNION_DECL})

_INDEX: Index | None = None



@dataclass(frozen=True)
class _Extent:
    start_offset: int
    end_offset: int


class NestedStructError(RuntimeError):
    """Raised when the AST-based rewriter cannot proceed on a given nested struct.

    The message always carries the source path, the 1-based line/column of the
    offending cursor, the cursor's tag, and the specific tokenization step that
    failed. This makes a crash on one file actionable — typically a sign that
    libclang parsed a cursor whose extent is in an ``#include``d file (rejected
    explicitly below) or a malformed tree from incomplete preprocessor handling.
    """


@dataclass(frozen=True)
class NestedStruct:
    """A struct/union definition declared inside another struct/union.

    All offsets index into the source text passed to ``scan``/``fix``.
    """

    kind: str  # "struct" or "union"
    name: str | None  # resolved name (tag or PascalCased field), or None
    def_start: int  # source offset of the 'struct'/'union' keyword
    brace_open: int  # source offset of '{'
    brace_close: int  # source offset of '}'
    decl_end: int  # source offset of ';' terminating the member declaration
    enclosing_line: int  # 1-based line of the enclosing struct's keyword
    line: int  # 1-based line of the definition keyword
    column: int  # 1-based column of the definition keyword


def _index():
    global _INDEX

    if(_INDEX is None):
        _INDEX = Index.create()

    return _INDEX


def _strip_directives(text: str) -> str:
    """Blank every ``#``-directive line (with continuations), preserving offsets.
    This check does not need to import other files/process macros to be able to determine what is/isnt a nested struct.
    """
    out: list[str] = []
    in_directive = False
    for line in text.split("\n"):
        if not in_directive and line.lstrip().startswith("#"):
            in_directive = True
        if in_directive:
            out.append(" " * len(line))
            in_directive = line.rstrip().endswith("\\")
        else:
            out.append(line)
    return "\n".join(out)


def _parse(path: Path, text: str) -> tuple[TranslationUnit, File]:
    idx = _index()
    name = str(path)
    stripped = _strip_directives(text)
    tu = idx.parse(
        name,
        args=["-x", "c"],
        unsaved_files=[(name, stripped)],
        options=(
            TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
            | TranslationUnit.PARSE_INCOMPLETE
        ),
    )
    return tu, tu.get_file(name)


def _cursor_kind_name(cur: Cursor) -> str:
    return "union" if cur.kind == CursorKind.UNION_DECL else "struct"


def _describe(cur: Cursor) -> str:
    """Location + tag for an error message, e.g. ``test.c:12:5 'struct Foo'``."""
    tag = cur.spelling or "<anonymous>"
    if cur.is_anonymous():
        tag = "<anonymous>"
    kind = _cursor_kind_name(cur)
    loc = cur.extent.start
    return f"{loc.file}:{loc.line}:{loc.column} '{kind} {tag}'"


def _find_token(
    tu: TranslationUnit,
    fileobj: File,
    start: int,
    end: int,
    spelling: str,
    *,
    cur: Cursor,
    path: Path,
    what: str,
    reverse: bool = False,
) -> int:
    """Offset of ``spelling`` in tokens over [start, end)
    ``what`` is a short noun phrase describing what the token represents, for
    the error message.
    """
    tokens = _tokens_between(tu, fileobj, start, end)
    order = reversed(tokens) if reverse else tokens
    for tok, off in order:
        if tok == spelling:
            return off
    where = _describe(cur)
    raise NestedStructError(
        f"{path}: {what} not found in cursor {where} "
        f"(tokenized extent [{start}, {end}); "
        f"usual cause: cursor's source location is in an #included file"
    )


def _tokens_between(
    tu: TranslationUnit, fileobj: File, start: int, end: int
) -> list[tuple[str, int]]:
    """``(spelling, start_offset)`` for tokens in [start, end)."""
    rng = SourceRange.from_locations(
        SourceLocation.from_offset(tu, fileobj, start),
        SourceLocation.from_offset(tu, fileobj, end),
    )
    return [(t.spelling, t.extent.start.offset) for t in tu.get_tokens(extent=rng)]


def _line_offsets(text: str) -> list[int]:
    """Byte offset of the start of each line, indexed by 1-based line number.
    """
    offsets = [0]
    pos = 0
    while True:
        nl = text.find("\n", pos)
        if nl < 0:
            return offsets
        offsets.append(nl + 1)
        pos = nl + 1


def _to_pascal(name: str) -> str:
    parts = [p for p in name.split("_") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


def _iter_nested(tu: TranslationUnit, fileobj: File) -> list[Cursor]:
    """Deduplicated struct/union defs whose lexical parent is a struct/union.
    """
    seen: set[_Extent] = set()
    out: list[Cursor] = []
    for cur in tu.cursor.walk_preorder():
        if cur.kind not in _CONTAINER_KINDS:
            continue
        if not cur.is_definition():
            continue
        if cur.location.file != fileobj:
            continue
        key = _Extent(cur.extent.start.offset, cur.extent.end.offset)
        if key in seen:
            continue
        seen.add(key)
        lex = cur.lexical_parent
        if lex is None or lex.kind not in _CONTAINER_KINDS:
            continue
        out.append(cur)
    return out


def _field_decls(struct_cur: Cursor) -> list[Cursor]:
    """Direct FIELD_DECL children of a struct/union cursor."""
    return [
        c
        for c in struct_cur.get_children()
        if c.kind == CursorKind.FIELD_DECL
    ]


def _resolve_name(struct_cur: Cursor, enclosing: Cursor) -> str | None:
    # libclang fills spelling with a generated "(unnamed at ...)" string for
    # anonymous structs, so check is_anonymous() rather than truthiness.
    if not struct_cur.is_anonymous():
        tag = struct_cur.spelling
        if tag:
            return tag
    for field in _field_decls(enclosing):
        decl = field.type.get_declaration()
        if decl and decl.extent == struct_cur.extent:
            pascal = _to_pascal(field.spelling)
            if pascal:
                return pascal
    return None


def _wrapping_field(
    struct_cur: Cursor, enclosing: Cursor
) -> Cursor | None:
    """The last FIELD_DECL member whose declarator wraps ``struct_cur``.

    A nested definition may have several declarators (``struct { ... } a, b;``)
    or a compound one (``struct { ... } (*fp)(void);``); the last such field's
    extent ends just before the terminating ``;``.
    """
    ns, ne = struct_cur.extent.start.offset, struct_cur.extent.end.offset
    fields = [
        f
        for f in enclosing.get_children()
        if f.kind == CursorKind.FIELD_DECL
        and f.extent.start.offset <= ns
        and f.extent.end.offset >= ne
    ]
    return fields[-1] if fields else None


def _collect(path: Path, text: str) -> list[NestedStruct]:
    tu, fileobj = _parse(path, text)
    results: list[NestedStruct] = []
    for cur in _iter_nested(tu, fileobj):
        enclosing = cur.lexical_parent
        assert enclosing is not None
        name = _resolve_name(cur, enclosing)

        brace_open = _find_token(
            tu, fileobj,
            cur.extent.start.offset, cur.extent.end.offset,
            "{", cur=cur, path=path, what="'{' (open brace)",
        )
        brace_close = _find_token(
            tu, fileobj,
            cur.extent.start.offset, cur.extent.end.offset,
            "}", cur=cur, path=path, what="'}' (close brace)", reverse=True,
        )

        wrapping = _wrapping_field(cur, enclosing)
        scan_from = (
            wrapping.extent.end.offset if wrapping else cur.extent.end.offset
        )
        decl_end = _find_token(
            tu, fileobj,
            scan_from, enclosing.extent.end.offset,
            ";", cur=cur, path=path, what="';' (terminating the member declaration)",
        )

        results.append(
            NestedStruct(
                kind=_cursor_kind_name(cur),
                name=name,
                def_start=cur.extent.start.offset,
                brace_open=brace_open,
                brace_close=brace_close,
                decl_end=decl_end,
                enclosing_line=enclosing.extent.start.line,
                line=cur.extent.start.line,
                column=cur.extent.start.column,
            )
        )
    return results


def nested_structs_scan(path: Path, text: str):
    """Yield :class:`Finding` objects for each nested struct in ``text``.

    Matches the ``ScanFn`` signature expected by ``tools/check/main.py``.
    """
    from check.finding import Finding

    for ns in _collect(path, text):
        yield Finding(
            path=str(path),
            line=ns.line,
            column=ns.column,
            message=_NESTED_MESSAGE,
            snippet=" ".join(text[ns.def_start : ns.decl_end + 1].split()),
        )


def nested_structs_fix(path: Path, text: str) -> tuple[str, int]:
    """Rewrite nested struct definitions to top-level references.

    Returns the rewritten text and the number of extractions performed.
    Matches the ``FixFn`` signature expected by ``tools/check/main.py``.
    """
    total = 0
    while total < _MAX_FIX_PASSES:
        nested = [ns for ns in _collect(path, text) if ns.name is not None]
        if not nested:
            break
        ns = nested[0]
        assert ns.name is not None  # selected because resolvable

        extracted = (
            f"{ns.kind} {ns.name} "
            + text[ns.brace_open : ns.brace_close + 1]
            + ";"
        )
        replacement = (
            f"{ns.kind} {ns.name}"
            + text[ns.brace_close + 1 : ns.decl_end + 1]
        )
        line_starts = _line_offsets(text)
        insert_at = line_starts[ns.enclosing_line - 1]
        ls = line_starts[ns.line - 1]
        prefix = text[ls : ns.def_start]
        text = (
            text[:insert_at]
            + extracted
            + "\n\n"
            + text[insert_at:ls]
            + prefix
            + replacement
            + text[ns.decl_end + 1 :]
        )
        total += 1
    return text, total


CHECK_NAME = "nested-structs"
CHECK_HELP = "struct/union definitions nested inside another struct/union body"
