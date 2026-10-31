"""
PowerPoint (.pptx) 幻灯片解析器。
逐页提取幻灯片标题、文本框内容与演讲者备注。
"""

from __future__ import annotations

import io
from typing import Any, Optional

from .base import BaseParser, ParsedDocument

try:
    import pptx
except ImportError:
    pptx = None


class PPTXParser(BaseParser):
    """PPT 演示文稿解析器。"""

    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        lower = filename.lower()
        if lower.endswith(".pptx"):
            return True
        return file_bytes.startswith(b"PK\x03\x04") and ".pptx" in lower

    async def parse(
        self,
        filename: str,
        file_bytes: bytes,
        vlm_client: Optional[Any] = None,
        max_vlm_images: int = 3,
    ) -> ParsedDocument:
        if pptx is None:
            return ParsedDocument(
                filename=filename,
                format="pptx",
                text_content="[系统提示: 当前环境未安装 python-pptx 模块，无法解析 PPT 幻灯片]",
                warning_message="missing_dependency_pptx",
            )

        prs = pptx.Presentation(io.BytesIO(file_bytes))
        slides_text: list[str] = []

        for slide_idx, slide in enumerate(prs.slides):
            slide_num = slide_idx + 1
            lines = [f"--- 第 {slide_num} 页幻灯片 ---"]

            # 提取幻灯片内所有文本形状
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        text = paragraph.text.strip()
                        if text:
                            lines.append(text)

            # 提取演讲者备注
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    lines.append(f"[演讲者备注]: {notes}")

            slides_text.append("\n".join(lines))

        return ParsedDocument(
            filename=filename,
            format="pptx",
            text_content="\n\n".join(slides_text),
            page_count=len(prs.slides),
            metadata={"slide_count": len(prs.slides)},
        )
