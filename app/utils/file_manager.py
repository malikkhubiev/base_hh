from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class FileManager:
    """Read/write helper for prompt and log files."""

    def __init__(self, txt_folder: str = "txt", output_folder: str = "logs") -> None:
        self.txt_folder = Path(txt_folder)
        self.output_folder = Path(output_folder)
        self.txt_folder.mkdir(parents=True, exist_ok=True)
        self.output_folder.mkdir(parents=True, exist_ok=True)

    def read_txt(self, filename: str) -> str:
        """Read UTF-8 text file from prompts folder."""
        filepath = self.txt_folder / filename
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        return filepath.read_text(encoding="utf-8").strip()

    def save_json(self, filename: str, data: Any) -> str:
        """Save JSON object to logs folder."""
        filepath = self.output_folder / filename
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(filepath)

    def save_txt(self, filename: str, content: str) -> str:
        """Save plain text to logs folder."""
        filepath = self.output_folder / filename
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def generate_filename(self, prefix: str, iteration: int | None = None, extension: str = "json") -> str:
        """Generate filename with current timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if iteration:
            return f"{prefix}_iter{iteration}_{timestamp}.{extension}"
        return f"{prefix}_{timestamp}.{extension}"

