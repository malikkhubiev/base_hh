from __future__ import annotations

from app.utils.file_manager import FileManager


class PromptService:
    def __init__(self, txt_folder: str = "txt", output_folder: str = "logs"):
        self.fm = FileManager(txt_folder=txt_folder, output_folder=output_folder)

    def get_default_request_text(self) -> str:
        return self.fm.read_txt("request.txt")

    def get_system_prompt_text(self) -> str:
        return self.fm.read_txt("system_prompt.txt")

    def get_user_prompt_text(self) -> str:
        return self.fm.read_txt("user_prompt.txt")

