"""Shared types for style checks, kept dependency-free to avoid circular imports."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    column: int
    message: str
    snippet: str
