"""Typed, zero-dependency logfmt codec: parse and serialize key=value log lines."""

from __future__ import annotations

from ._codec import parse, serialize

__version__ = "0.1.0"

__all__ = ["parse", "serialize"]
