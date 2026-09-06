"""Run the TUI: `uv run -m tui` (env FLATWORLD_WS, default ws://localhost:8000/ws)."""

import os
import sys

from .app import FlatlandApp


def main() -> None:
    ws_url = (
        sys.argv[1]
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-")
        else os.environ.get("FLATWORLD_WS", "ws://localhost:8000/ws")
    )
    if len(sys.argv) > 2 and not sys.argv[2].startswith("-"):
        os.environ["FLATWORLD_GOD_KEY"] = sys.argv[2]
    FlatlandApp(ws_url=ws_url).run()


if __name__ == "__main__":
    main()
