"""Offline tests for the Windows-console UTF-8 stdio fix (RC-07)."""

from __future__ import annotations

import io
import sys
import unittest
from unittest import mock

from _helpers import SRC  # noqa: F401  (ensures the src tree is importable)

from agent_factory.cli import _force_utf8_stdio


class _RecordingStream:
    """Minimal stream that records a ``reconfigure`` call like TextIOWrapper."""

    def __init__(self, encoding: str = "cp1252"):
        self.encoding = encoding
        self.reconfigured_with = None

    def reconfigure(self, *, encoding=None):  # noqa: ARG002 (signature parity)
        self.encoding = encoding
        self.reconfigured_with = encoding


class TestForceUtf8Stdio(unittest.TestCase):
    def test_reconfigures_stdout_and_stderr_to_utf8(self):
        out, err = _RecordingStream(), _RecordingStream()
        with mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            _force_utf8_stdio()
        self.assertEqual(out.reconfigured_with, "utf-8")
        self.assertEqual(err.reconfigured_with, "utf-8")

    def test_noop_for_streams_without_reconfigure(self):
        # StringIO (test double) has no ``reconfigure`` — must not raise.
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            _force_utf8_stdio()

    def test_never_raises_on_reconfigure_failure(self):
        class _Broken:
            def reconfigure(self, **_kw):
                raise OSError("cannot reconfigure")

        with mock.patch.object(sys, "stdout", _Broken()), mock.patch.object(
            sys, "stderr", io.StringIO()
        ):
            _force_utf8_stdio()  # swallowed — no exception escapes


if __name__ == "__main__":
    unittest.main()
