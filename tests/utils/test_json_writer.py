from __future__ import annotations

import json

import pytest

from src.utils import json_writer
from src.utils.json_writer import AtomicJsonWriteError, atomic_write_json


def test_atomic_write_json_creates_parent_directory_and_utf8_json(tmp_path) -> None:
    output_path = tmp_path / "nested" / "result.json"

    atomic_write_json({"text": "Русский текст"}, output_path)

    raw_text = output_path.read_text(encoding="utf-8")
    assert json.loads(raw_text) == {"text": "Русский текст"}
    assert "Русский текст" in raw_text
    assert "\\u0420" not in raw_text


def test_atomic_write_json_replaces_existing_file(tmp_path) -> None:
    output_path = tmp_path / "result.json"

    atomic_write_json({"name": "old"}, output_path)
    atomic_write_json({"name": "new"}, output_path)

    raw_text = output_path.read_text(encoding="utf-8")
    assert json.loads(raw_text) == {"name": "new"}
    assert "old" not in raw_text


def test_atomic_write_json_removes_temp_file_and_preserves_target_on_write_error(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "result.json"
    atomic_write_json({"name": "stable"}, output_path)

    def fail_dump(*args, **kwargs) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(json_writer.json, "dump", fail_dump)

    with pytest.raises(AtomicJsonWriteError):
        atomic_write_json({"name": "broken"}, output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == {"name": "stable"}
    assert not output_path.with_name("result.json.tmp").exists()
