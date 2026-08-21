"""Allow `python -m agent_factory ...`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
