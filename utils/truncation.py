"""
全格式自适应结构化文本截断工具。
在不超过字符上限的前提下，自适应保留文档关键首部（目录/前言/开头，占 70%）与关键尾部（总结/结论，占 30%）。
"""

from __future__ import annotations


def adaptive_truncate(text: str, max_chars: int = 20000) -> tuple[str, bool]:
    """对超长文档执行自适应结构化截断。

    返回 (截断后文本, 是否发生了截断)。
    """
    clean_text = str(text or "")
    total_len = len(clean_text)

    if total_len <= max_chars:
        return clean_text, False

    # 保留开头 70% 额度，保留结尾 30% 额度
    head_len = int(max_chars * 0.7)
    tail_len = int(max_chars * 0.3)

    head_part = clean_text[:head_len]
    tail_part = clean_text[-tail_len:] if tail_len > 0 else ""

    notice = (
        f"\n\n...[文件内容过长（共 {total_len:,} 字），"
        f"已自适应保留关键开头前 {head_len:,} 字与结尾后 {tail_len:,} 字，"
        f"安全截断中间内容以保护大模型上下文]...\n\n"
    )

    return head_part + notice + tail_part, True
