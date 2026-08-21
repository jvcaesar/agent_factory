"""Ensure the `src` tree is importable when running stdlib unittest."""

import pathlib
import sys

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
