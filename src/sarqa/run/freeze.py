"""Guard for test-split runs (SPEC §10.1). A test run starts only if

1. the working tree is clean (`git status --porcelain` is empty),
2. no frozen file changed since the newest `freeze-v*` tag (frozen = `src/sarqa/` except `analysis/`,
   `configs/`, `pyproject.toml`, `PROTOCOL.md`), and
3. every data hash the protocol requires is written in PROTOCOL.md and equals the real file's SHA-256.

`check_freeze` returns the list of problems; an empty list means the run may start. The dev split
skips this guard.
"""

import hashlib
import re
import subprocess
from pathlib import Path

FROZEN_PATHS = ["src/sarqa", "configs", "pyproject.toml", "PROTOCOL.md", ":(exclude)src/sarqa/analysis"]


def required_files(split: str = "test") -> list[str]:
    """Files whose SHA-256 must be in PROTOCOL.md before a run of `split` (dev = the rehearsal set)."""
    if split not in ("dev", "test"):
        raise ValueError("split must be dev or test")
    return ["splits/scenes.json", "splits/splits.json", "outputs/detector/weights.pt",
            f"data/detections/{split}.json", f"data/questions/{split}.json",
            *[f"data/{d}/{split}_{k}.json" for d in ("injected", "corrected") for k in ("miss", "fp", "loc")]]


ROW = re.compile(r"`([^`\s]+)`[^\n]*?`([0-9a-f]{64})`")


def protocol_hashes(protocol: Path) -> dict[str, str]:
    """`{file: sha256}` for every table row of PROTOCOL.md that names a file and a 64-hex hash."""
    out = {}
    for line in Path(protocol).read_text(encoding="utf-8").splitlines():
        m = ROW.search(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


def latest_freeze_tag(root: Path) -> str | None:
    tags = _git(root, "tag", "-l", "freeze-v*").stdout.split()
    if not tags:
        return None
    return max(tags, key=lambda t: [int(x) for x in re.findall(r"\d+", t)])


def check_freeze(root: str | Path, required: list[str] | None = None) -> list[str]:
    root = Path(root)
    problems = []
    if _git(root, "status", "--porcelain").stdout.strip():
        problems.append("working tree is not clean (git status --porcelain is not empty)")
    tag = latest_freeze_tag(root)
    if tag is None:
        problems.append("no freeze-v* tag exists")
    else:
        changed = _git(root, "diff", "--name-only", tag, "HEAD", "--", *FROZEN_PATHS).stdout.split()
        if changed:
            problems.append(f"frozen files changed since {tag}: {changed[:8]}")
    protocol = root / "PROTOCOL.md"
    if not protocol.exists():
        return problems + ["PROTOCOL.md is missing"]
    hashes = protocol_hashes(protocol)
    for rel in required if required is not None else required_files('test'):
        if rel not in hashes:
            problems.append(f"PROTOCOL.md has no hash for {rel}")
            continue
        f = root / rel
        if not f.exists():
            problems.append(f"{rel} is missing")
        elif hashlib.sha256(f.read_bytes()).hexdigest() != hashes[rel]:
            problems.append(f"{rel} does not match its hash in PROTOCOL.md")
    return problems
