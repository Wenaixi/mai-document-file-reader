"""
Word (.docx) 原生结构解析器。
提取正文、层级标题，并将 Word 内嵌表格转换生成排版优美的 Markdown 表格。
"""

from __future__ import annotations

import io
from typing import Any, Optional

from .base import BaseParser, ParsedDocument

try:
    import docx
except ImportError:
    docx = None


class DocxParser(BaseParser):
    """Word 文档解析器。"""

    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        lower = filename.lower()
        if lower.endswith(".docx"):
            return True
        # docx 本质是 zip 压缩包，以 PK\x03\x04 开头
        return file_bytes.startswith(b"PK\x03\x04") and ".docx" in lower

    async def parse(
        self,
        filename: str,
        file_bytes: bytes,
        vlm_client: Optional[Any] = None,
        max_vlm_images: int = 3,
    ) -> ParsedDocument:
        if docx is None:
            return ParsedDocument(
                filename=filename,
                format="docx",
                text_content="[系统提示: 当前环境未安装 python-docx 模块，无法完整解析 Word 结构]",
                warning_message="missing_dependency_docx",
            )

        doc = docx.Document(io.BytesIO(file_bytes))
        sections_text: list[str] = []

        # 遍历段落与表格
        for element in doc.element.body:
            tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

            # 普通段落与标题
            if tag == "p":
                p = docx.text.paragraph.Paragraph(element, doc)
                text = p.text.strip()
                if not text:
                    continue
                # 处理标题样式
                style_name = str(p.style.name).lower() if p.style else ""
                if "heading 1" in style_name or "标题 1" in style_name:
                    sections_text.append(f"# {text}")
                elif "heading 2" in style_name or "标题 2" in style_name:
                    sections_text.append(f"## {text}")
                elif "heading 3" in style_name or "标题 3" in style_name:
                    sections_text.append(f"### {text}")
                else:
                    sections_text.append(text)

            # 表格元素转 Markdown 表格
            elif tag == "tbl":
                table = docx.table.Table(element, doc)
                if not table.rows:
                    continue
                tbl_lines = []
                for row_idx, row in enumerate(table.rows):
                    cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    tbl_lines.append("| " + " | ".join(cells) + " |")
                    if row_idx == 0:
                        # 插入表头分隔线
                        tbl_lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
                sections_text.append("\n".join(tbl_lines))

        full_content = "\n\n".join(sections_text)
        return ParsedDocument(
            filename=filename,
            format="docx",
            text_content=full_content,
            page_count=len(doc.sections),
            metadata={"paragraph_count": len(doc.paragraphs), "table_count": len(doc.tables)},
        )
