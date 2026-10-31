"""
文档解析抽象基类与数据结构定义。
所有具体的文档解析器（Text, Docx, PDF, Excel, PPTX）均继承自 BaseParser。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ExtractedImage:
    """从文档（如 PDF）中提取的关键图像元数据。"""

    image_bytes: bytes
    page_number: int
    image_index: int
    format: str = "png"
    description: Optional[str] = None  # 由 VLM 分析后填入的图表解析文本


@dataclass
class ParsedDocument:
    """解析后的结构化文档对象。"""

    filename: str
    format: str
    text_content: str
    page_count: int = 1
    images: list[ExtractedImage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_truncated: bool = False
    warning_message: Optional[str] = None


class BaseParser(ABC):
    """文档解析器统一抽象基类。"""

    @abstractmethod
    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        """根据文件名后缀或文件头魔数判断本解析器是否支持处理。"""
        ...

    @abstractmethod
    async def parse(
        self,
        filename: str,
        file_bytes: bytes,
        vlm_client: Optional[Any] = None,
        max_vlm_images: int = 3,
    ) -> ParsedDocument:
        """执行异步解析并返回统一的 ParsedDocument。"""
        ...
