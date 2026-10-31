"""
文档解析器工厂与统一分发注册表。
"""

from __future__ import annotations

from typing import Any, Optional

from .base import BaseParser, ParsedDocument
from .docx_parser import DocxParser
from .excel_parser import ExcelParser
from .pdf_parser import PDFParser
from .pptx_parser import PPTXParser
from .text_parser import TextParser


class ParserRegistry:
    """多格式解析器注册管理工厂。"""

    def __init__(self) -> None:
        # 按优先级注册特定二进制解析器，文本解析器最后兜底
        self._parsers: list[BaseParser] = [
            PDFParser(),
            DocxParser(),
            ExcelParser(),
            PPTXParser(),
            TextParser(),
        ]

    def select_parser(self, filename: str, file_bytes: bytes) -> BaseParser:
        """根据文件名与文件二进制内容选取首个命中的解析器。"""
        for p in self._parsers:
            if p.can_parse(filename, file_bytes):
                return p
        return self._parsers[-1]

    async def parse(
        self,
        filename: str,
        file_bytes: bytes,
        vlm_client: Optional[Any] = None,
        max_vlm_images: int = 3,
    ) -> ParsedDocument:
        """分发执行解析。"""
        parser = self.select_parser(filename, file_bytes)
        return await parser.parse(
            filename=filename,
            file_bytes=file_bytes,
            vlm_client=vlm_client,
            max_vlm_images=max_vlm_images,
        )


default_registry = ParserRegistry()
