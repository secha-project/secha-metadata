"""Append SHA-256 seals to SEALS.md: a record that files existed with these exact bytes.

A seal is how the held-out test shows its order of events. The protocol and inputs are
sealed before any model runs, the proposals are sealed the moment they are written, and
score.py refuses to score a proposal whose bytes differ from its seal. SEALS.md is only
ever appended to.

Usage (from the repository root):
    python experiments/kempower_heldout/seal.py --label "pre-run: protocol and inputs" PATH...

Directories are expanded to the files inside them, sorted. Paths are recorded relative to
the repository root, so a file outside it (the partner catalog) shows as ../...
"""

import argparse
import hashlib
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SEALS = Path(__file__).resolve().parent / "SEALS.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def expand(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw).resolve()
        if path.is_dir():
            files += sorted(p for p in path.rglob("*") if p.is_file())
        elif path.is_file():
            files.append(path)
        else:
            raise SystemExit(f"nothing to seal at {raw}")
    return files


def relative(path: Path) -> str:
    return Path(os.path.relpath(path, REPO)).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--label", required=True, help="what this seal records, in words")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()

    lines = [f"{sha256(p)}  {relative(p)}" for p in expand(args.paths)]
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    block = f"\n## {args.label} ({stamp})\n\n```text\n" + "\n".join(lines) + "\n```\n"

    if not SEALS.exists():
        SEALS.write_bytes(
            b"# Seals: Kempower held-out test\n\n"
            b"Append-only. Each block lists SHA-256 digests of files as they were at the time\n"
            b"shown. Written by seal.py; never edit a block by hand.\n"
        )
    with SEALS.open("ab") as handle:
        handle.write(block.encode("utf-8"))
    print(f"sealed {len(lines)} file(s) under '{args.label}' at {stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
