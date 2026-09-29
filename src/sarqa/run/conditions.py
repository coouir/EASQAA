"""Condition table (SPEC §9) and the box provider of each input."""

from dataclasses import dataclass

from sarqa.boxes import BoxProvider, detected_provider, file_provider, label_provider
from sarqa.config import load_config
from sarqa.inject.build import file_paths


@dataclass(frozen=True)
class Condition:
    id: int
    method: str
    input: str
    repeat: int

    @property
    def kind(self) -> str | None:
        return self.input.split(":", 1)[1] if ":" in self.input else None


def load_conditions() -> dict[int, Condition]:
    cfg = load_config("conditions")
    return {c["id"]: Condition(c["id"], c["method"], c["input"], c["repeat"]) for c in cfg["conditions"]}


def priority_groups() -> list[list[int]]:
    return load_config("conditions")["priority_groups"]


def total_runs(split: str = "test") -> int:
    return len(load_config("conditions")["conditions"]) * load_config("conditions")["questions_per_split"][split]


def parse_selection(spec: str) -> list[int]:
    """`all` or a comma list such as `1,2,6`, in priority order."""
    known = load_conditions()
    if spec == "all":
        ids = list(known)
    else:
        ids = [int(x) for x in spec.split(",") if x.strip()]
        unknown = sorted(set(ids) - set(known))
        if unknown:
            raise ValueError(f"unknown condition(s) {unknown}; known: {sorted(known)}")
    order = [c for group in priority_groups() for c in group]
    return sorted(dict.fromkeys(ids), key=order.index)


class ProviderPool:
    """Box providers per (split, input), built once."""

    def __init__(self, split: str):
        self.split = split
        self._cache: dict[str, BoxProvider] = {}

    def get(self, cond: Condition) -> BoxProvider:
        if cond.input not in self._cache:
            if cond.input == "label":
                self._cache[cond.input] = label_provider()
            elif cond.input == "detected":
                self._cache[cond.input] = detected_provider(self.split)
            else:
                source, kind = cond.input.split(":")
                path = file_paths(self.split, kind)[source]
                if not path.exists():
                    raise FileNotFoundError(f"{path} is missing; run `sarqa inject build --split {self.split}`")
                self._cache[cond.input] = file_provider(source, path)
        return self._cache[cond.input]

