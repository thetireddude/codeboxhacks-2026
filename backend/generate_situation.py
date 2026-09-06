"""Compatibility entry point for generating one Gemini improv situation.

The canonical script is ``generate_scenario.py``.  This alias supports the
project's equally common "situation" terminology in shell usage.
"""

from generate_scenario import main


if __name__ == "__main__":
    raise SystemExit(main())
