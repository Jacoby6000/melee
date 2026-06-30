# Agent Notes

This is a Super Smash Bros. Melee decompilation project. Preserve matching
behavior when renaming symbols or improving readability.

## Commands

- Generate build files: `python3 configure.py`
- Build: `ninja`
- Show progress: `python3 configure.py progress`

## Conventions

- Address comments such as `/* 16BC74 */` identify original code addresses and
  should be kept when renaming functions.
- When renaming a global function, update its declaration and the matching
  entry in `config/GALE01/symbols.txt`.
- Follow `.github/CONTRIBUTING.md`: run `clang-format` on touched C/H files
  under `src`, keep larger struct fields offset-prefixed, and use explicit
  `NULL` checks.
