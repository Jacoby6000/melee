#!/usr/bin/env python3
"""Tests for the nested-structs check. Run: python3 tools/check/tests/nested_structs.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from check.nested_structs import nested_structs_fix, nested_structs_scan  # noqa: E402


class NestedStructsScanTest(unittest.TestCase):
    def lines(self, source: str) -> list[int]:
        return [f.line for f in nested_structs_scan(Path("test.c"), source)]

    def test_flags_anonymous_nested_struct(self) -> None:
        source = (
            "struct Outer {\n"
            "    struct {\n"  # 2
            "        int x;\n"
            "    } inner;\n"
            "};\n"
        )
        self.assertEqual(self.lines(source), [2])

    def test_flags_tagged_nested_struct(self) -> None:
        source = (
            "struct Outer {\n"
            "    struct Foo {\n"  # 2
            "        int x;\n"
            "    } inner;\n"
            "};\n"
        )
        self.assertEqual(self.lines(source), [2])

    def test_flags_nested_union(self) -> None:
        source = (
            "struct Outer {\n"
            "    union Bar {\n"  # 2
            "        int x;\n"
            "        float y;\n"
            "    } u;\n"
            "};\n"
        )
        self.assertEqual(self.lines(source), [2])

    def test_flags_multiple_siblings(self) -> None:
        source = (
            "union V {\n"
            "    struct { int x; } common;\n"  # 2
            "    struct { int y; } walk;\n"  # 3
            "};\n"
        )
        self.assertEqual(self.lines(source), [2, 3])

    def test_flags_deeply_nested(self) -> None:
        source = (
            "struct A {\n"
            "    struct B {\n"  # 2
            "        struct C {\n"  # 3
            "            int z;\n"
            "        } deep;\n"
            "    } inner;\n"
            "};\n"
        )
        # libclang walks in source order (outermost first).
        self.assertEqual(self.lines(source), [2, 3])

    def test_ignores_top_level_struct(self) -> None:
        source = (
            "struct Foo {\n"
            "    int x;\n"
            "};\n"
            "struct Bar {\n"
            "    int y;\n"
            "};\n"
        )
        self.assertEqual(self.lines(source), [])

    def test_ignores_typedef_anon_struct(self) -> None:
        source = (
            "typedef struct {\n"
            "    int x;\n"
            "} Foo;\n"
        )
        self.assertEqual(self.lines(source), [])

    def test_ignores_struct_in_function_body(self) -> None:
        source = (
            "void f(void) {\n"
            "    struct Local {\n"  # not nested in a struct body
            "        int x;\n"
            "    } l;\n"
            "}\n"
        )
        self.assertEqual(self.lines(source), [])


class NestedStructsFixTest(unittest.TestCase):
    def fix(self, source: str) -> tuple[str, int]:
        return nested_structs_fix(Path("test.c"), source)

    def assertNoNested(self, source: str) -> None:
        self.assertEqual(
            [f.line for f in nested_structs_scan(Path("test.c"), source)], []
        )

    def test_tagged_uses_tag_name(self) -> None:
        source = (
            "struct Outer {\n"
            "    struct Foo {\n"
            "        int x;\n"
            "    } inner;\n"
            "};\n"
        )
        fixed, n = self.fix(source)
        self.assertEqual(n, 1)
        self.assertIn("struct Foo {\n        int x;\n    };", fixed)
        self.assertIn("struct Foo inner;", fixed)
        self.assertNoNested(fixed)

    def test_anonymous_uses_pascal_field_name(self) -> None:
        source = (
            "struct Outer {\n"
            "    struct {\n"
            "        int x;\n"
            "    } bar_field;\n"
            "};\n"
        )
        fixed, n = self.fix(source)
        self.assertEqual(n, 1)
        self.assertIn("struct BarField {", fixed)
        self.assertIn("struct BarField bar_field;", fixed)
        self.assertNoNested(fixed)

    def test_anonymous_multi_word_field(self) -> None:
        source = (
            "union V {\n"
            "    struct { int x; } some_name;\n"
            "};\n"
        )
        fixed, n = self.fix(source)
        self.assertEqual(n, 1)
        self.assertIn("struct SomeName {", fixed)
        self.assertIn("struct SomeName some_name;", fixed)
        self.assertNoNested(fixed)

    def test_multiple_siblings(self) -> None:
        source = (
            "union V {\n"
            "    struct { int x; } common;\n"
            "    struct { int y; } walk;\n"
            "};\n"
        )
        fixed, n = self.fix(source)
        self.assertEqual(n, 2)
        self.assertIn("struct Common { int x; };", fixed)
        self.assertIn("struct Walk { int y; };", fixed)
        self.assertIn("struct Common common;", fixed)
        self.assertIn("struct Walk walk;", fixed)
        self.assertNoNested(fixed)

    def test_deeply_nested_extracts_all(self) -> None:
        source = (
            "struct A {\n"
            "    struct B {\n"
            "        struct C {\n"
            "            int z;\n"
            "        } deep;\n"
            "    } inner;\n"
            "};\n"
        )
        fixed, n = self.fix(source)
        self.assertEqual(n, 2)
        self.assertIn("struct C {", fixed)
        self.assertIn("struct B {", fixed)
        self.assertIn("struct C deep;", fixed)
        self.assertIn("struct B inner;", fixed)
        self.assertNoNested(fixed)

    def test_multi_declarator(self) -> None:
        source = (
            "struct Outer {\n"
            "    struct { int x; } a, b;\n"
            "};\n"
        )
        fixed, n = self.fix(source)
        self.assertEqual(n, 1)
        self.assertIn("struct A { int x; };", fixed)
        self.assertIn("struct A a, b;", fixed)
        self.assertNoNested(fixed)

    def test_preserves_offset_comment(self) -> None:
        source = (
            "struct Outer {\n"
            "    /* +0 */ struct { int x; } inner;\n"
            "};\n"
        )
        fixed, n = self.fix(source)
        self.assertEqual(n, 1)
        self.assertIn("/* +0 */ struct Inner inner;", fixed)
        self.assertNoNested(fixed)

    def test_idempotent(self) -> None:
        source = (
            "struct Outer {\n"
            "    struct { int x; } inner;\n"
            "};\n"
        )
        once, _ = self.fix(source)
        twice, n = self.fix(once)
        self.assertEqual((twice, n), (once, 0))

    def test_flat_source_unchanged(self) -> None:
        source = (
            "struct Foo { int x; };\n"
            "struct Bar { int y; };\n"
        )
        fixed, n = self.fix(source)
        self.assertEqual((fixed, n), (source, 0))

    def test_skips_unnameable_anonymous(self) -> None:
        source = (
            "struct Outer {\n"
            "    union {\n"
            "        int x;\n"
            "        struct { int y; };\n"  # no field name -> cannot rename
            "    };\n"  # union has no field name either
            "};\n"
        )
        fixed, n = self.fix(source)
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
