"""Worker process used by the GUI and bundled executable."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


MODES = {
    "surface": "Fuzzyficator.py",
    "paint": "Fuzzyficator_paintOn.py",
    "pattern": "Fuzzyficator_pattern.py",
}


def resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in MODES:
        modes = ", ".join(sorted(MODES))
        print(f"Usage: FuzzyficatorWorker <{modes}> <processor arguments>")
        return 2

    mode = args.pop(0)
    script_path = resource_dir() / MODES[mode]
    if not script_path.exists():
        print(f"Missing bundled processor script: {script_path}")
        return 2

    previous_argv = sys.argv[:]
    try:
        sys.argv = [str(script_path), *args]
        runpy.run_path(str(script_path), run_name="__main__")
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        print(exc.code)
        return 1
    finally:
        sys.argv = previous_argv

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
