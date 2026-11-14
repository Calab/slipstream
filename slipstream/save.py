"""Persistent settings and per-theme records (JSON in the user data dir)."""

import json
import os
import sys
from pathlib import Path


def user_data_dir():
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        p = base / "Slipstream"
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "Slipstream"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        p = base / "slipstream"
    p.mkdir(parents=True, exist_ok=True)
    return p


DEFAULTS = {"theme": "reef", "sound": True, "touch": None, "aim": True, "records": {}}


class SaveData:
    def __init__(self, path=None):
        self.path = Path(path) if path else user_data_dir() / "save.json"
        self.data = json.loads(json.dumps(DEFAULTS))
        try:
            self.data.update(json.loads(self.path.read_text()))
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2))
            tmp.replace(self.path)
        except OSError:
            pass

    def __getitem__(self, k):
        return self.data.get(k, DEFAULTS.get(k))

    def __setitem__(self, k, v):
        self.data[k] = v
        self.save()

    def record(self, theme_key):
        """Dict with best_time, best_distance, last_time, last_distance."""
        recs = self.data.setdefault("records", {})
        return recs.setdefault(theme_key, {"best_time": 0.0, "best_distance": 0.0,
                                           "last_time": 0.0, "last_distance": 0.0})

    def finish_run(self, theme_key, time_s, distance):
        r = self.record(theme_key)
        new_best = time_s > r["best_time"]
        if new_best:
            r["best_time"], r["best_distance"] = time_s, distance
        r["last_time"], r["last_distance"] = time_s, distance
        self.save()
        return new_best

    def reset_best(self, theme_key):
        r = self.record(theme_key)
        r["best_time"] = r["best_distance"] = 0.0
        self.save()
