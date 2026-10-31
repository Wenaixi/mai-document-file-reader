"""
Excel 表格 (.xlsx, .xls, .csv) 原生解析器。
支持将 Excel 工作簿与 CSV 格式化生成整洁的 Markdown 表格输出。
"""

from __future__ import annotations

import csv
import io
from typing import Any, Optional

from .base import BaseParser, ParsedDocument

try:
    import openpyxl
except ImportError:
    openpyxl = None


class ExcelParser(BaseParser):
    """Excel 与 CSV 表格解析器。"""

    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        lower = filename.lower()
        if any(lower.endswith(ext) for ext in [".xlsx", ".xlsm", ".xltx", ".csv", ".tsv"]):
            return True
        return file_bytes.startswith(b"PK\x03\x04") and (".xlsx" in lower or ".xlsm" in lower)

    async def parse(
        self,
        filename: str,
        file_bytes: bytes,
        vlm_client: Optional[Any] = None,
        max_vlm_images: int = 3,
    ) -> ParsedDocument:
        lower = filename.lower()
        if lower.endswith(".csv") or lower.endswith(".tsv"):
            return self._parse_csv(filename, file_bytes, delimiter="\t" if lower.endswith(".tsv") else ",")

        if openpyxl is None:
            return ParsedDocument(
                filename=filename,
                format="xlsx",
                text_content="[系统提示: 当前环境未安装 openpyxl 模块，无法完整解析 Excel 表格]",
                warning_message="missing_dependency_openpyxl",
            )

        try:
            # 避免 read_only=True 导致腾讯文档/WPS 等 XML 维度标签残缺文件被错误截断为仅首格
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        except Exception as e:
            return ParsedDocument(
                filename=filename,
                format="xlsx",
                text_content=f"[Excel 表格读取失败: ({e})]",
                warning_message=str(e),
            )

        sheets_output: list[str] = []
        for sheet_name in wb.sheetnames[:5]:  # 最多解析前 5 个工作表，防过载
            ws = wb[sheet_name]
            sheet_lines = [f"### 工作表: {sheet_name}"]
            rows_data = []

            max_rows = 60  # 单表最大行数
            for r_idx, row in enumerate(ws.iter_rows(values_only=True)):
                if r_idx >= max_rows:
                    sheet_lines.append(f"...[工作表数据过大，已截取前 {max_rows} 行]...")
                    break
                row_str = [str(val if val is not None else "").strip().replace("\n", " ") for val in row[:15]]
                if any(row_str):
                    rows_data.append(row_str)

            if rows_data:
                # 构建 Markdown 表格
                max_cols = max(len(r) for r in rows_data)
                header = rows_data[0] + [""] * (max_cols - len(rows_data[0]))
                sheet_lines.append("| " + " | ".join(header) + " |")
                sheet_lines.append("| " + " | ".join(["---"] * max_cols) + " |")
                for r in rows_data[1:]:
                    padded = r + [""] * (max_cols - len(r))
                    sheet_lines.append("| " + " | ".join(padded) + " |")
            else:
                sheet_lines.append("[该工作表为空]")

            sheets_output.append("\n".join(sheet_lines))

        return ParsedDocument(
            filename=filename,
            format="xlsx",
            text_content="\n\n".join(sheets_output),
            page_count=len(wb.sheetnames),
            metadata={"sheets": wb.sheetnames},
        )

    def _parse_csv(self, filename: str, file_bytes: bytes, delimiter: str = ",") -> ParsedDocument:
        text = file_bytes.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            return ParsedDocument(filename=filename, format="csv", text_content="[CSV 表格为空]")

        lines = [f"### CSV 数据表格 ({len(rows)} 行):"]
        max_cols = max(len(r) for r in rows[:60])
        header = rows[0][:max_cols] + [""] * (max_cols - len(rows[0][:max_cols]))
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        for r in rows[1:60]:
            clean_r = [c.replace("\n", " ").strip() for c in r[:max_cols]]
            padded = clean_r + [""] * (max_cols - len(clean_r))
            lines.append("| " + " | ".join(padded) + " |")

        if len(rows) > 60:
            lines.append(f"...[CSV 过大，已展示前 60 行，共 {len(rows)} 行]...")

        return ParsedDocument(
            filename=filename,
            format="csv",
            text_content="\n".join(lines),
            page_count=1,
            metadata={"row_count": len(rows)},
        )
