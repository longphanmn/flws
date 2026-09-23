"""Admin CLI for the god passkey — server-side recovery, never a web route.

Lost or forgotten passkeys are reset from the machine that owns the database:

    ./godkey reset <new-passkey>                      # from repo root (wrapper, works anywhere)
    cd backend && uv run python -m app.godkey reset <new-passkey>
    uv run --project backend python -m app.godkey reset <new-passkey>
    backend/.venv/bin/python -m app.godkey reset <new-passkey>

Direct `python3 -m app.godkey` from the repo root also works via the
`app -> backend/app` symlink, but must use the venv python (or `uv run`)
so `fastapi` is available — system `python3` without the venv will fail.

If you see `ModuleNotFoundError: No module named 'app'` or `fastapi`,
use the wrapper: `./godkey reset <key>` or `cd backend && uv run ...`.

Honours FLATWORLD_DB; defaults to backend/flatworld.db like the app.
"""

import argparse
import os
import sys
from pathlib import Path

# Friendly hint when invoked as `python3 -m app.godkey` from the repo root
# with the system interpreter that lacks the venv's site-packages.
try:
    from .auth import PasskeyAuth
    from .db import Database
except ModuleNotFoundError as _e:
    # Re-raise with a helpful hint for the common `python3 -m app.godkey` mistake
    if "fastapi" in str(_e) or "app" in str(_e):
        print(
            f"error: {_e}\n"
            "hint: use the wrapper from the repo root:\n"
            "  ./godkey reset <new-passkey>\n"
            "or from backend:\n"
            "  cd backend && uv run python -m app.godkey reset <new-passkey>\n"
            "  cd backend && .venv/bin/python -m app.godkey reset <new-passkey>",
            file=sys.stderr,
        )
        raise SystemExit(2) from _e
    raise


def default_db_path() -> str:
    return str(Path(__file__).resolve().parent.parent / "flatworld.db")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.godkey",
        description="Manage the god passkey (admin CLI — no HTTP endpoint exists for this).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_reset = sub.add_parser("reset", help="set a new passkey (overwrites any existing one)")
    p_reset.add_argument("passkey")
    sub.add_parser("clear", help="remove the passkey; the web UI will ask to create one again")
    args = parser.parse_args(argv)

    db = Database(os.environ.get("FLATWORLD_DB", default_db_path()))
    auth = PasskeyAuth(db)
    was_configured = auth.configured()

    if args.command == "reset":
        try:
            (auth.reset if was_configured else auth.setup)(args.passkey)
        except (ValueError, PermissionError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        verb = "reset" if was_configured else "created"
        print(f"god passkey {verb}. Use it as X-God-Key (or in the web prompt).")
        return 0

    if not was_configured:
        print("no god passkey exists — nothing to clear.")
        return 0
    try:
        auth.clear()
    except PermissionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("god passkey cleared. The web UI will ask to create a new one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
