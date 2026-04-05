from __future__ import annotations

from app.utils.file_manager import FileManager


def test_read_txt(tmp_path) -> None:
    d = tmp_path / "t"
    d.mkdir()
    (d / "a.txt").write_text("hello", encoding="utf-8")
    fm = FileManager(txt_folder=str(d), output_folder=str(tmp_path / "out"))
    assert fm.read_txt("a.txt") == "hello"


def test_save_json_roundtrip(tmp_path) -> None:
    out = tmp_path / "logs"
    out.mkdir()
    fm = FileManager(txt_folder=str(tmp_path / "t"), output_folder=str(out), create_txt_folder=True)
    path = fm.save_json("x.json", {"a": 1})
    assert "x.json" in path
    assert (out / "x.json").read_text(encoding="utf-8").strip().startswith("{")
