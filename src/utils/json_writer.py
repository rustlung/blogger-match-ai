from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AtomicJsonWriteError(RuntimeError):
    pass


def atomic_write_json(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f"{output_path.name}.tmp")

    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(
                payload,
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.write("\n")
        temp_path.replace(output_path)
    except Exception as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise AtomicJsonWriteError("Could not write JSON file.") from exc
