"""
纯文本与源码通用解析器。
支持 .txt, .md, .json, .yaml, .yml, .log, .py, .ts, .js, .html, .xml, .sql, .sh 等。
"""

from __future__ import annotations

from typing import Any, Optional

try:
    from charset_normalizer import from_bytes
except ImportError:
    from_bytes = None

from .base import BaseParser, ParsedDocument

_TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".json", ".yaml", ".yml", ".log",
    ".py", ".ts", ".js", ".jsx", ".tsx", ".html", ".htm", ".xml",
    ".sql", ".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1",
    ".ini", ".conf", ".cfg", ".toml", ".env", ".properties",
    ".css", ".scss", ".sass", ".less", ".c", ".cpp", ".h", ".hpp",
    ".java", ".rs", ".go", ".php", ".rb", ".kt", ".swift", ".lua",
}


class TextParser(BaseParser):
    """纯文本与代码解析器。"""

    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        lower = filename.lower()
        if any(lower.endswith(ext) for ext in _TEXT_EXTENSIONS):
            return True
        sample = file_bytes[:1024]
        return b"\x00" not in sample

    async def parse(
        self,
        filename: str,
        file_bytes: bytes,
        vlm_client: Optional[Any] = None,
        max_vlm_images: int = 3,
    ) -> ParsedDocument:
        text = ""

        # 1. UTF-8 优先解码
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            pass

        # 2. GB18030 / GBK 备选解码 (覆盖中文 Windows ANSI 记事本)
        if not text:
            try:
                text = file_bytes.decode("gb18030")
            except UnicodeDecodeError:
                pass

        # 3. 智能字符集推断
        if not text and from_bytes is not None:
            match = from_bytes(file_bytes).best()
            if match is not None:
                text = str(match)

        # 4. 终极容错
        if not text:
            text = file_bytes.decode("utf-8", errors="replace")

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
        return ParsedDocument(
            filename=filename,
            format=ext,
            text_content=text,
            page_count=1,
            metadata={"size_bytes": len(file_bytes)},
        )
