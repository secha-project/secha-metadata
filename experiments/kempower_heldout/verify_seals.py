"""Verify every seal in SEALS.md, the way an examiner with a fresh clone would.

A sealed file under version control is checked against the repository's history: some
commit must hold the sealed bytes. Git stores text with LF line endings, and some files
were sealed from a Windows working copy with CRLF, so a commit also counts when its CRLF
rendering matches; the report says which. A file outside version control (drafts, cached
model replies, the partner catalog) is checked as it is on disk. One that is absent is
reported as absent rather than failed, because drafts and replies stay local by design
(PROTOCOL.md, Blinding).

Usage (from the repository root):
    python experiments/kempower_heldout/verify_seals.py

Exits non-zero if any seal matches neither history nor the file on disk.
"""

import hashlib
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SEALS = Path(__file__).resolve().parent / "SEALS.md"
_BLOCK = re.compile(r"^## (.+) \((\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\)$")
_LINE = re.compile(r"^([0-9a-f]{64})  (.+)$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, check=False).stdout


def parse(text: str) -> list[tuple[str, str, str]]:
    """(block label, digest, path) for every sealed file, in the order sealed."""
    seals: list[tuple[str, str, str]] = []
    label = ""
    for line in text.splitlines():
        block = _BLOCK.match(line)
        if block:
            label = f"{block.group(1)} ({block.group(2)})"
        entry = _LINE.match(line.strip())
        if entry:
            seals.append((label, entry.group(1), entry.group(2)))
    return seals


def in_history(path: str, digest: str) -> str | None:
    """The commit holding these bytes, and in which line-ending form, if any does."""
    for commit in git("log", "--format=%H", "--", path).decode().split():
        blob = git("show", f"{commit}:{path}")
        if sha256(blob) == digest:
            return f"history {commit[:7]}"
        crlf = blob.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        if sha256(crlf) == digest:
            return f"history {commit[:7]} (CRLF working copy)"
    return None


def main() -> int:
    tracked = set(git("ls-files").decode().split())
    seals = parse(SEALS.read_text(encoding="utf-8"))
    latest = {path: digest for _, digest, path in seals}
    outcomes: dict[str, Counter[str]] = {}
    failures: list[str] = []

    for label, digest, path in seals:
        tally = outcomes.setdefault(label, Counter())
        if path in tracked:
            found = in_history(path, digest)
            file = REPO / path
            if found is None and file.is_file() and sha256(file.read_bytes()) == digest:
                found = "working copy, not yet committed"
            kind = "verified" if found else "FAILED"
        else:
            file = (REPO / path).resolve()
            if not file.is_file():
                kind = "absent (local only)"
            elif sha256(file.read_bytes()) == digest:
                kind = "verified"
            elif latest[path] != digest:
                kind = "superseded by a later seal"
            else:
                kind = "FAILED"
        tally[kind] += 1
        if kind == "FAILED":
            failures.append(f"{path} ({label})")

    for label, tally in outcomes.items():
        summary = ", ".join(f"{n} {kind}" for kind, n in sorted(tally.items()))
        print(f"{label}: {summary}")
    if failures:
        print("\nSeals that match neither history nor the file on disk:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(f"\nAll {len(seals)} seals accounted for.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
