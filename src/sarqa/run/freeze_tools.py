"""Helpers for the freeze procedure (SPEC §14 M5): the SHA-256 rows of PROTOCOL.md and a check by split.

    sarqa freeze hashes --split test [--write]   # print (or write) the table rows of PROTOCOL.md §1
    sarqa freeze check  --split test             # the guard of the test run, nothing is executed

`--split dev` is the rehearsal set (`scripts/freeze_rehearsal.sh`): the same steps with the dev files.
"""

import hashlib
import re
from pathlib import Path

from sarqa.run.freeze import check_freeze, required_files

STATUS = {"test": "확정 (M5)", "dev": "리허설(dev)"}
OBSOLETE_ROW_MARKERS = ("data/injected/*.json", "test 문항 파일")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_rows(root: Path, split: str) -> tuple[dict[str, str], list[str]]:
    """`({file: sha256}, [missing files])` for the files the guard requires for `split`."""
    rows, missing = {}, []
    for rel in required_files(split):
        f = Path(root) / rel
        if f.exists():
            rows[rel] = sha256_of(f)
        else:
            missing.append(rel)
    return rows, missing


def format_row(rel: str, digest: str, status: str) -> str:
    return f"| `{rel}` | {status} | `{digest}` |"


def update_protocol(text: str, rows: dict[str, str], status: str) -> str:
    """Put the rows into the first table of PROTOCOL.md that already holds hash rows: an existing row of the
    same file is replaced, a new one is added after the last hash row, and the placeholder rows that said
    "미정" for the injected/corrected/test files are removed."""
    lines = text.splitlines()
    kept = [ln for ln in lines if not (ln.startswith("|") and any(m in ln for m in OBSOLETE_ROW_MARKERS)
                                       and "미정" in ln)]
    row_re = re.compile(r"^\| `([^`]+)`")
    last = max((i for i, ln in enumerate(kept) if row_re.match(ln) and re.search(r"`[0-9a-f]{64}`", ln)), default=None)
    if last is None:
        raise ValueError("PROTOCOL.md has no hash table to extend")
    out, done = list(kept), set()
    for i, ln in enumerate(out):
        m = row_re.match(ln)
        if m and m.group(1) in rows:
            out[i] = format_row(m.group(1), rows[m.group(1)], status)
            done.add(m.group(1))
    last = max(i for i, ln in enumerate(out) if row_re.match(ln) and re.search(r"`[0-9a-f]{64}`", ln))
    new = [format_row(rel, d, status) for rel, d in rows.items() if rel not in done]
    out[last + 1:last + 1] = new
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def freeze_check(root: Path, split: str) -> list[str]:
    return check_freeze(root, required_files(split))
