"""Tests de path jail y nombres de archivo."""

from __future__ import annotations

from pathlib import Path

import pytest

from security.filenames import UnsafeFilenameError, sanitize_filename
from security.paths import PathJailError, resolve_under


def test_resolve_under_ok(tmp_path: Path):
    child = resolve_under(tmp_path, "a", "b.txt")
    assert child.parent == (tmp_path / "a").resolve() or child.parent.name == "a"


def test_resolve_under_rejects_dotdot(tmp_path: Path):
    with pytest.raises(PathJailError):
        resolve_under(tmp_path, "..", "etc")


def test_resolve_under_rejects_slash_in_part(tmp_path: Path):
    with pytest.raises(PathJailError):
        resolve_under(tmp_path, "a/b")


def test_sanitize_filename_ok():
    assert sanitize_filename("nota.txt", {".txt", ".md"}) == "nota.txt"
    assert sanitize_filename("Doc.MD", {".txt", ".md"}).endswith(".md")


def test_sanitize_rejects_py():
    with pytest.raises(UnsafeFilenameError):
        sanitize_filename("evil.py", {".txt", ".md"})


def test_sanitize_rejects_exe():
    with pytest.raises(UnsafeFilenameError):
        sanitize_filename("x.exe", {".txt", ".md"})


def test_sanitize_rejects_traversal():
    with pytest.raises(UnsafeFilenameError):
        sanitize_filename("../etc/passwd.txt", {".txt", ".md"})
