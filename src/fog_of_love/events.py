"""events.jsonl: one JSON object per line, `t` sequential, exactly the schema in BUILD_SPEC.md."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

PHASES = ("setup", "morning", "market", "app", "date", "visit", "night")


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.path, "w", encoding="utf-8")
        self._t = 0
        self._lock = threading.Lock()
        self.events: list[dict[str, Any]] = []

    def emit(self, phase: str, type_: str, day: int, **fields: Any) -> dict[str, Any]:
        assert phase in PHASES, phase
        with self._lock:
            self._t += 1
            ev = {"t": self._t, "day": int(day), "phase": phase, "type": type_, **fields}
            self._f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            self._f.flush()
            self.events.append(ev)
        return ev

    def close(self) -> None:
        self._f.close()


def read_events(path: Path | str) -> list[dict[str, Any]]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
