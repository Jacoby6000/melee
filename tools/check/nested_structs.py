#!/usr/bin/env python3
"""Nested-struct check backed by the clang AST (libclang).

CONTRIBUTING.md (``#structs``) forbids struct/union *definitions* that appear
inside another struct/union body. This check detects them via
``cursor.lexical_parent`` — the decisive signal is a struct/union declaration
whose lexical parent is itself a struct/union.

The rewriter extracts the nested definition to file scope, renames it, and
replaces the inline definition with a named reference.

Naming:
- If the nested struct has a tag, use it directly (clang enforces tag
  uniqueness within a scope).
- Otherwise (anonymous), use ``<enclosing>_<field>`` where ``<field>`` is the
  wrapping field's declarator name and ``<enclosing>`` is the enclosing
  struct's tag, or the wrapping typedef name if the enclosing struct is itself
  anonymous (e.g. ``typedef struct { struct { ... } field; } Name;``).
- If no enclosing name is available, fall back to the PascalCased field name.
- If none of the above yield a name, return None (left for manual review).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clang.cindex import (
    Cursor,
    CursorKind,
    File,
    Index,
    TranslationUnit,
)

CHECK_NAME = "nested-structs"
CHECK_HELP = "struct/union definitions nested inside another struct/union body"

def nested_structs_scan(path: Path, text: str):
    """Yield :class:`Finding` objects for each nested struct in ``text``.

    Matches the ``ScanFn`` signature expected by ``tools/check/main.py``.
    """
    from check.finding import Finding

    data = text.encode("utf-8")
    for ns in _collect(path, text):
        snippet = b" ".join(data[ns.def_start : ns.decl_end + 1].split())
        yield Finding(
            path=str(path),
            line=ns.line,
            column=ns.column,
            message=_NESTED_MESSAGE,
            snippet=snippet.decode("utf-8"),
        )

def nested_structs_fix(path: Path, text: str) -> tuple[str, int]:
    """Rewrite nested struct definitions to top-level references.

    Edits are applied innermost-first (by nesting depth, then source order) so
    that when a containing struct's body is hoisted, its inner structs have
    already been replaced with named references.

    Returns the rewritten text and the number of extractions performed.
    """
    data = text.encode("utf-8")
    nested = [ns for ns in _collect(path, text) if ns.name is not None]

    nested.sort(key=lambda n: (-n.depth, n.def_start))

    applied: list[tuple[int, int]] = []

    def adj(o: int) -> int:
        shift = 0
        for de, d in applied:
            if o >= de:
                shift += d
        return o - shift

    by_insert: dict[int, list[bytes]] = {}
    total = 0
    for ns in nested:
        def_start = adj(ns.def_start)
        brace_open = adj(ns.brace_open)
        brace_close = adj(ns.brace_close)
        decl_end = adj(ns.decl_end)

        name_b = ns.name.encode("utf-8")
        kind_b = ns.kind.encode("ascii")

        ls = data.rfind(b"\n", 0, def_start) + 1
        prefix = data[ls:def_start]
        base_col = len(prefix) - len(prefix.lstrip(b" "))

        body = _deindent(data[brace_open : brace_close + 1], base_col)
        extracted = kind_b + b" " + name_b + b" " + body + b";"
        if ns.needs_pack:
            extracted = _wrap_pack(extracted, ns.pack_expr)

        by_insert.setdefault(ns.insert_at, []).append(extracted)

        replacement = _deindent(kind_b + b" " + name_b + data[brace_close + 1 : decl_end + 1], base_col)
        splice_end = decl_end + 1
        data = data[:ls] + prefix + replacement + data[splice_end:]
        removed = splice_end - ls - len(prefix + replacement)
        applied.append((ns.decl_end + 1, removed))
        total += 1

    for orig_insert in sorted(by_insert, reverse=True):
        insert_at = adj(orig_insert)
        block = b"\n\n".join(by_insert[orig_insert]) + b"\n\n"
        data = data[:insert_at] + block + data[insert_at:]

    return data.decode("utf-8"), total

_NESTED_MESSAGE = (
    "Nested struct definition: move it out of the parent and reference it "
    "by name (CONTRIBUTING.md #structs)"
)

_CONTAINER_KINDS = frozenset({CursorKind.STRUCT_DECL, CursorKind.UNION_DECL})

_INDEX: Index | None = None

class _NestedStructError(RuntimeError):
    """Raised when the AST-based rewriter cannot proceed on a given nested struct.

    The message always carries the source path, the 1-based line/column of the
    offending cursor, the cursor's tag (or ``<anonymous>``), and the specific
    step that failed. This makes a crash on one file actionable.
    """


@dataclass(frozen=True)
class _NestedStruct:
    """A struct/union definition declared inside another struct/union.

    All offsets are byte offsets into the UTF-8 encoding of the source text
    passed to ``scan``/``fix`` — the same bytes libclang parsed, so they line
    up with the rewriter's byte slicing.
    """

    kind: str  # "struct" or "union"
    name: str | None  # resolved name (tag, enclosing_field, PascalCase), or None
    def_start: int  # byte offset of the 'struct'/'union' keyword
    brace_open: int  # byte offset of '{'
    brace_close: int  # byte offset of '}'
    decl_end: int  # byte offset of ';' terminating the member declaration
    insert_at: int  # byte offset before which to insert the extracted definition
    depth: int  # nesting depth (0 = file scope); used to order extractions
    line: int  # 1-based line of the definition keyword
    column: int  # 1-based column of the definition keyword
    needs_pack: bool  # True if inside a #pragma pack region; wrap with it
    pack_expr: str  # pack argument (e.g. "1", "2", "") for the wrapper



@dataclass(frozen=True)
class _Extent:
    start_offset: int
    end_offset: int




def _index() -> Index:
    global _INDEX
    if _INDEX is None:
        _INDEX = Index.create()
    return _INDEX


def _strip_directives(text: str) -> str:
    """Blank every ``#``-directive line (with continuations), preserving
    offsets, avoiding unnecessary parsing of #included files.
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
    """Parse ``text`` as C using libclang (directives stripped, errors
    tolerated).
    """
    idx = _index()
    name = str(path)
    stripped = _strip_directives(text)
    encoded = stripped.encode("utf-8")
    tu = idx.parse(
        name,
        args=["-x", "c"],
        unsaved_files=[(name, encoded)],
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
    tag = "<anonymous>" if cur.is_anonymous() else (cur.spelling or "<anonymous>")
    kind = _cursor_kind_name(cur)
    loc = cur.extent.start
    return f"{loc.file}:{loc.line}:{loc.column} '{kind} {tag}'"


def _open_brace_offset(cur: Cursor, path: Path) -> int:
    for tok in cur.get_tokens():
        if tok.spelling == "{":
            return tok.extent.start.offset
    raise _NestedStructError(
        f"{path}: '{{' (open brace) not found in cursor {_describe(cur)}"
    )


def _to_pascal(name: str) -> str:
    parts = [p for p in name.split("_") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


def _deindent(data: bytes, max_spaces_to_remove: int) -> bytes:
    """Remove ``max_spaces_to_remove`` leading spaces from each line of ``data``.
    """
    if max_spaces_to_remove <= 0:
        return data
    out: list[bytes] = []
    for line in data.split(b"\n"):
        stripped = line.lstrip(b" ")
        removed_spaces_count = len(line) - len(stripped)
        if  removed_spaces_count >= max_spaces_to_remove:
            out.append(line[max_spaces_to_remove:])
        else:
            out.append(line)
    return b"\n".join(out)


def _iter_nested(tu: TranslationUnit, fileobj: File) -> list[Cursor]:
    """Deduplicated struct/union definitions whose lexical parent is a struct/union.

    Only cursors whose source location is in ``fileobj`` are returned.
    Only definitions (cursors with a body) are returned.
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
    return [
        c
        for c in struct_cur.get_children()
        if c.kind == CursorKind.FIELD_DECL
    ]


def _enclosing_name(enclosing: Cursor, tu: TranslationUnit) -> str | None:
    """A usable name for the enclosing struct, for collision-free naming.

    Prefers the enclosing struct's own name.

    If the enclosing struct is anonymous, falls back to the name of a wrapping
    ``typedef``.

    If the enclosing struct is anonymous and nested inside another struct/union,
    walks up via the wrapping field to build ``<ancestor>_<field>``

    Returns ``None`` if none available.
    """
    # Not anonymous
    if not enclosing.is_anonymous():
        tag = enclosing.spelling
        if tag:
            return tag

    # Anonymous enclosing struct: look for a typedef whose extent wraps it.
    for c in tu.cursor.get_children():
        if c.kind != CursorKind.TYPEDEF_DECL:
            continue
        if (c.extent.start.offset <= enclosing.extent.start.offset
                and c.extent.end.offset >= enclosing.extent.end.offset):
            if c.spelling:
                return c.spelling

    # Anonymous, no typedef
    parent = enclosing.lexical_parent
    if parent is not None and parent.kind in _CONTAINER_KINDS:
        wrapping = _wrapping_field(enclosing, parent)
        if wrapping is not None and wrapping.spelling:
            ancestor = _enclosing_name(parent, tu)
            if ancestor:
                return f"{ancestor}_{wrapping.spelling}"
    return None


def _wrapping_field(
    struct_cur: Cursor, enclosing: Cursor
) -> Cursor | None:
    """The last FIELD_DECL member whose declarator wraps ``struct_cur``.

    A nested definition may have several declarators (``struct { ... } a, b;``)
    or a compound one (``struct { ... } (*fp)(void);``); the last such field's
    extent ends at the terminating ``;``.
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


def _resolve_name(
    struct_cur: Cursor, enclosing: Cursor, tu: TranslationUnit
) -> str | None:
    """Resolve a collision-free name for the extracted struct/union.

    1. If the nested struct has a tag, use it directly (clang enforces tag
       uniqueness within a scope).
    2. Otherwise (anonymous), use ``<enclosing>_<field>`` where ``<field>`` is
       the wrapping field's declarator name and ``<enclosing>`` is the
       enclosing struct's tag or wrapping typedef name. This avoids generic
       names (``U``, ``Data``) that collide when multiple anonymous structs
       are extracted in the same file.
    3. If no enclosing name is available, fall back to PascalCased field name.
    4. If none yield a name, return ``None`` (left for manual review).
    """
    if not struct_cur.is_anonymous():
        tag = struct_cur.spelling
        if tag:
            return tag
    field = _wrapping_field(struct_cur, enclosing)
    field_name = field.spelling if field else None
    enclosing_name = _enclosing_name(enclosing, tu)
    if enclosing_name and field_name:
        return f"{enclosing_name}_{field_name}"
    if field_name:
        pascal = _to_pascal(field_name)
        if pascal:
            return pascal
    return None


def _outermost_enclosing(cur: Cursor) -> Cursor:
    """Walk up lexical parents to the topmost struct/union (the file-scope one).

    The extracted definition should be inserted before the outermost enclosing
    struct — not before an intermediate anonymous union that is itself nested.
    """
    enclosing = cur.lexical_parent
    while enclosing is not None and enclosing.kind in _CONTAINER_KINDS:
        parent = enclosing.lexical_parent
        if parent is None or parent.kind not in _CONTAINER_KINDS:
            break
        enclosing = parent
    assert enclosing is not None
    return enclosing


def _nest_depth(cur: Cursor) -> int:
    """Number of struct/union lexical parents above ``cur`` (0 at file scope)."""
    depth = 0
    parent = cur.lexical_parent
    while parent is not None and parent.kind in _CONTAINER_KINDS:
        depth += 1
        parent = parent.lexical_parent
    return depth


def _pragma_pack_ranges(
    text: str,
) -> list[tuple[int, int, str]]:
    """Ranges of ``#pragma pack`` regions and the directive that sets them.

    Returns ``(start_offset, end_offset, pack_expr)`` tuples where ``pack_expr``

    Handles both push/pop and bare-set forms:
    - ``#pragma pack(push, N)`` ... ``#pragma pack(pop)``
    - ``#pragma pack(push)`` ... ``#pragma pack(pop)``
    - ``#pragma pack(N)`` ... ``#pragma pack()`` / ``#pragma pack``
    """
    lines = text.split("\n")
    ranges: list[tuple[int, int, str]] = []
    stack: list[tuple[int, str]] = []
    pos = 0
    for line in lines:
        line_start = pos
        stripped = line.lstrip()
        if stripped.startswith("#"):
            body = stripped.lstrip("#").strip()
            if body.startswith("pragma") and "pack" in body:
                if "push" in body:
                    # #pragma pack(push, 4) -> expr = "4"
                    # #pragma pack(push) -> expr = "" (inherits current)
                    inner = body[body.find("(", 4) + 1 : body.rfind(")")] if "(" in body else ""
                    parts = [p.strip() for p in inner.split(",")]
                    expr = parts[1] if len(parts) > 1 else ""
                    stack.append((line_start, expr))
                elif "pop" in body:
                    if stack:
                        push_start, expr = stack.pop()
                        ranges.append((push_start, line_start + len(line) + 1, expr))
                else:
                    # #pragma pack(N) or #pragma pack() — bare set
                    inner = body[body.find("(") + 1 : body.rfind(")")] if "(" in body else ""
                    expr = inner.strip()
                    if expr:
                        stack.append((line_start, expr))
                    else:
                        # #pragma pack() resets to default — closes any bare
                        # set, carrying the *pushed* N (not the empty closer).
                        if stack:
                            push_start, pushed_expr = stack.pop()
                            ranges.append((push_start, line_start + len(line) + 1, pushed_expr))
        pos += len(line) + 1
    return ranges


def _collect(path: Path, text: str) -> list[_NestedStruct]:
    """Collect every nested struct/union in one libclang pass."""
    tu, fileobj = _parse(path, text)
    pack_ranges = _pragma_pack_ranges(text)
    data = text.encode("utf-8")
    results: list[_NestedStruct] = []
    for cur in _iter_nested(tu, fileobj):
        enclosing = cur.lexical_parent
        assert enclosing is not None

        name = _resolve_name(cur, enclosing, tu)

        # Insert before the start of the line containing the outermost
        # enclosing struct's keyword — ``typedef `` or other decl specifiers
        # may precede it on the same line, and the extracted definitions
        # must go before the entire declaration, not split the prefix off.
        raw_start = _outermost_enclosing(cur).extent.start.offset
        nl = data.rfind(b"\n", 0, raw_start)
        insert_at = nl + 1 if nl >= 0 else 0

        cur_offset = cur.extent.start.offset
        pack_expr = ""
        needs_pack = False
        for pin_s, pin_e, expr in pack_ranges:
            if pin_s <= cur_offset < pin_e:
                pack_expr = expr
                # Only wrap if the insertion point is outside the same pack
                # region — when it's inside, the extracted definition inherits
                # the correct packing from the surrounding pragma.
                if not (pin_s <= insert_at < pin_e):
                    needs_pack = True
                break

        # ``extent.end`` is half-open: it points one past ``}``; ``{`` is the
        # only position not recoverable from ``extent`` (the keyword/tag
        # precede it) so it needs a token lookup. The wrapping FIELD_DECL's
        # extent is also half-open and ends exactly at the ``;`` (verified
        # for tagged, multi-declarator, and function-pointer declarators).
        brace_open = _open_brace_offset(cur, path)
        brace_close = cur.extent.end.offset - 1

        wrapping = _wrapping_field(cur, enclosing)
        if wrapping is not None:
            decl_end = wrapping.extent.end.offset
        else:
            decl_end = cur.extent.end.offset

        results.append(
            _NestedStruct(
                kind=_cursor_kind_name(cur),
                name=name,
                def_start=cur.extent.start.offset,
                brace_open=brace_open,
                brace_close=brace_close,
                decl_end=decl_end,
                insert_at=insert_at,
                depth=_nest_depth(cur),
                line=cur.extent.start.line,
                column=cur.extent.start.column,
                needs_pack=needs_pack,
                pack_expr=pack_expr,
            )
        )
    return results



def _wrap_pack(extracted: bytes, pack_expr: str) -> bytes:
    """Wrap an extracted definition in a ``#pragma pack(push, N)``/``pop`` pair.

    ``pack_expr`` is the argument captured by :func:`_pragma_pack_ranges`
    (e.g. ``"1"``, ``""`` for an inherited/default push). An empty argument
    yields a bare ``#pragma pack(push)``.
    """
    arg = f", {pack_expr}" if pack_expr else ""
    header = f"#pragma pack(push{arg})".encode("ascii")
    return header + b"\n" + extracted + b"\n#pragma pack(pop)"


