"""
视觉大模型 (VLM) 异步交互客户端。
支持单张图片压缩编码、调用宿主 vlm 任务、带指数退避的多轮重试。
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from PIL import Image
except ImportError:
    Image = None


class VLMClient:
    """视觉大模型封装客户端。"""

    def __init__(self, ctx: Any, task_name: str = "vlm") -> None:
        self.ctx = ctx
        self.task_name = task_name

    @staticmethod
    def _prepare_image_base64(img_bytes: bytes, max_side: int = 1024) -> str:
        """检查并压缩图片尺寸，转换为 base64 字符串。"""
        if Image is None:
            return base64.b64encode(img_bytes).decode("ascii")

        try:
            with Image.open(io.BytesIO(img_bytes)) as img:
                img = img.convert("RGB")
                w, h = img.size
                if max(w, h) > max_side:
                    scale = max_side / max(w, h)
                    new_size = (int(w * scale), int(h * scale))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)

                out = io.BytesIO()
                img.save(out, format="JPEG", quality=85)
                return base64.b64encode(out.getvalue()).decode("ascii")
        except Exception as e:
            logger.debug(f"PIL 图像预处理异常，降级直传: {e}")
            return base64.b64encode(img_bytes).decode("ascii")

    async def describe_image(self, img_bytes: bytes, prompt_hint: str = "详细描述该图表或图片中的核心数据与内容：") -> str:
        """异步调用视觉大模型提炼图表或扫描页含义。"""
        b64_data = self._prepare_image_base64(img_bytes)
        data_url = f"data:image/jpeg;base64,{b64_data}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_hint},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]

        # 指数退避重试 2 次
        last_exc: Optional[Exception] = None
        for attempt in range(2):
            try:
                # 优先走 SDK 标准生成接口
                if hasattr(self.ctx, "llm") and hasattr(self.ctx.llm, "generate"):
                    resp = await self.ctx.llm.generate(
                        messages=messages,
                        task_name=self.task_name,
                        temperature=0.2,
                        max_tokens=1024,
                    )
                    text = str(resp.content if hasattr(resp, "content") else resp).strip()
                    if text:
                        return text
                return ""
            except Exception as exc:
                last_exc = exc
                logger.warning(f"VLM 请求失败 (第 {attempt + 1} 次): {exc}")
                await asyncio.sleep(1.5 * (attempt + 1))

        if last_exc:
            logger.error(f"VLM 多次重试均失败: {last_exc}")
        return ""
