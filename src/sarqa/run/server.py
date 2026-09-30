"""Which Ollama server process answered a run (SPEC §7.1: reproducibility only holds inside one server process).

Ollama has no API for its start time, so the process that listens on the server's port is looked up in
/proc (same machine, Linux): pid from the listening socket's inode, start time from /proc/<pid>/stat.
`ServerWatch.identity()` is cheap (it re-reads only /proc/<pid>/stat once the pid is known). A change of
identity between two runs is reported once in the log and recorded; the run then continues (no automatic
restart, SPEC §0-6).
"""

import datetime as dt
import os
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

PROC = Path("/proc")


@dataclass(frozen=True)
class ServerIdentity:
    pid: int
    started_at: str      # ISO 8601 UTC, from the process start time

    def as_dict(self) -> dict:
        return {"pid": self.pid, "started_at": self.started_at}


def port_of(host: str) -> int | None:
    parsed = urllib.parse.urlparse(host if "//" in host else f"//{host}")
    return parsed.port


def _listening_inodes(port: int, proc: Path) -> set[str]:
    """Socket inodes in LISTEN state (st 0A) on `port`, from /proc/net/tcp and tcp6."""
    inodes = set()
    for name in ("tcp", "tcp6"):
        f = proc / "net" / name
        if not f.exists():
            continue
        for line in f.read_text().splitlines()[1:]:
            cols = line.split()
            if len(cols) > 9 and cols[3] == "0A" and int(cols[1].rsplit(":", 1)[1], 16) == port:
                inodes.add(cols[9])
    return inodes


def find_pid(port: int, proc: Path = PROC) -> int | None:
    inodes = _listening_inodes(port, proc)
    if not inodes:
        return None
    wanted = {f"socket:[{i}]" for i in inodes}
    for d in proc.iterdir():
        if not d.name.isdigit():
            continue
        try:
            for fd in (d / "fd").iterdir():
                if os.readlink(fd) in wanted:
                    return int(d.name)
        except OSError:
            continue
    return None


def start_time(pid: int, proc: Path = PROC) -> str | None:
    """ISO UTC start time: boot time + starttime ticks of /proc/<pid>/stat (field 22)."""
    try:
        stat = (proc / str(pid) / "stat").read_text()
        ticks = int(stat.rsplit(")", 1)[1].split()[19])
        btime = next(int(x.split()[1]) for x in (proc / "stat").read_text().splitlines() if x.startswith("btime"))
    except (OSError, ValueError, StopIteration, IndexError):
        return None
    hz = os.sysconf("SC_CLK_TCK")
    return dt.datetime.fromtimestamp(btime + ticks / hz, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ServerWatch:
    """Identity of the server behind `host`; `None` when it cannot be determined (remote host, no /proc)."""

    def __init__(self, host: str, proc: Path = PROC):
        self.port, self.proc = port_of(host), proc
        self._cached: ServerIdentity | None = None
        self._local = host.split("//")[-1].split(":")[0] in ("localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0")

    def _lookup(self) -> ServerIdentity | None:
        if not (self._local and self.port):
            return None
        pid = find_pid(self.port, self.proc)
        started = start_time(pid, self.proc) if pid else None
        return ServerIdentity(pid, started) if pid and started else None

    def identity(self) -> ServerIdentity | None:
        if self._cached is not None and start_time(self._cached.pid, self.proc) == self._cached.started_at:
            return self._cached                      # same process still running: no socket scan needed
        self._cached = self._lookup()
        return self._cached
