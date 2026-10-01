"""Entry-point module for `python -m gfm_math_lint`."""

from __future__ import annotations

import sys

from gfm_math_lint.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
