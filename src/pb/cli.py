"""Entry point for Makefile targets. See CLAUDE.md 'Commands'."""
from __future__ import annotations

import argparse
import sys

COMMANDS = (
    "trace",
    "traces-live",
    "oracle",
    "budget",
    "labellers",
    "baselines",
    "headline",
    "test-final",
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pb")
    parser.add_argument("command", choices=COMMANDS)
    args = parser.parse_args(argv)
    raise NotImplementedError(f"pb {args.command}: not implemented yet")


if __name__ == "__main__":
    main(sys.argv[1:])
