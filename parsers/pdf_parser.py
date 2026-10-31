"""
PDF 文档结构与多模态视觉解析器。
支持逐页文本抽取、扫描页探测、内嵌图表提取以及 VLM 视觉大模型增强分析。
"""

from __future__ import annotations

import io
import logging
from typing import Any, Optional

from .base import BaseParser, ExtractedImage, ParsedDocument

try:
    import pypdf
except ImportError:
    pypdf = None

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """PDF 图文与视觉多模态解析器。"""

    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        lower = filename.lower()
        if lower.endswith(".pdf"):
            return True
        # PDF 文件头魔数为 %PDF
        return file_bytes.startswith(b"%PDF")

    async def parse(
        self,
        filename: str,
        file_bytes: bytes,
        vlm_client: Optional[Any] = None,
        max_vlm_images: int = 3,
    ) -> ParsedDocument:
        if pypdf is None:
            return ParsedDocument(
                filename=filename,
                format="pdf",
                text_content="[系统提示: 当前环境未安装 pypdf 模块，无法解析 PDF 文档]",
                warning_message="missing_dependency_pypdf",
            )

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        except Exception as e:
            return ParsedDocument(
                filename=filename,
                format="pdf",
                text_content=f"[PDF 读取失败: 文档损坏或格式异常 ({e})]",
                warning_message=str(e),
            )

        if reader.is_encrypted:
            return ParsedDocument(
                filename=filename,
                format="pdf",
                text_content="[该 PDF 已被密码加密保护，麦麦无法直接阅读，请解密后重试]",
                warning_message="encrypted_pdf",
            )

        total_pages = len(reader.pages)
        pages_text: list[str] = []
        extracted_images: list[ExtractedImage] = []
        vlm_call_count = 0

        # 遍历每一页进行图文混合提取
        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            raw_page_text = (page.extract_text() or "").strip()
            page_lines = [f"--- 第 {page_num}/{total_pages} 页 ---"]

            # 提取该页包含的图片
            page_images_data: list[bytes] = []
            try:
                for img_obj in page.images:
                    page_images_data.append(img_obj.data)
            except Exception as img_err:
                logger.debug(f"第 {page_num} 页提取图片异常: {img_err}")

            # 扫描页判定：文字过少（<50字）且含有图片，视为扫描页
            is_scanned_page = len(raw_page_text) < 50 and len(page_images_data) > 0

            if raw_page_text:
                page_lines.append(raw_page_text)
            elif not is_scanned_page:
                page_lines.append("[本页无文字内容]")

            # 若满足 VLM 视觉调用条件（存在扫描页或关键插图，且未超出单文档最大识图上限）
            if vlm_client is not None and vlm_call_count < max_vlm_images and page_images_data:
                target_img_bytes = page_images_data[0]
                img_record = ExtractedImage(
                    image_bytes=target_img_bytes,
                    page_number=page_num,
                    image_index=1,
                    format="jpeg",
                )

                prompt_hint = "解读该扫描页的全部文字与表格：" if is_scanned_page else "简要提炼并分析图表中的关键数据与含义："
                try:
                    desc = await vlm_client.describe_image(target_img_bytes, prompt_hint=prompt_hint)
                    if desc:
                        img_record.description = desc
                        tag = "扫描页视觉解析" if is_scanned_page else "图表视觉解析"
                        page_lines.append(f"\n[【{tag}】: {desc}]")
                        vlm_call_count += 1
                        extracted_images.append(img_record)
                except Exception as vlm_err:
                    logger.warning(f"调用 VLM 解析第 {page_num} 页图表失败: {vlm_err}")
                    page_lines.append(f"\n[第 {page_num} 页含图表，视觉模型暂不可用]")

            pages_text.append("\n".join(page_lines))

        return ParsedDocument(
            filename=filename,
            format="pdf",
            text_content="\n\n".join(pages_text),
            page_count=total_pages,
            images=extracted_images,
            metadata={
                "total_pages": total_pages,
                "vlm_analyzed_images": vlm_call_count,
            },
        )
