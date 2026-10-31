"""
多格式解析器与自适应截断单元测试套件。
"""

import asyncio
import io
import unittest

from parsers import default_registry
from parsers.docx_parser import DocxParser
from parsers.excel_parser import ExcelParser
from parsers.pdf_parser import PDFParser
from parsers.text_parser import TextParser
from utils.truncation import adaptive_truncate


class MockVLMClient:
    """用于测试的 Mock 视觉大模型客户端。"""

    def __init__(self, reply_text: str = "图表显示第三季度营收环比增长 24%"):
        self.reply_text = reply_text
        self.called_count = 0

    async def describe_image(self, img_bytes: bytes, prompt_hint: str = "") -> str:
        self.called_count += 1
        return self.reply_text


class TestMultiFormatParsers(unittest.TestCase):
    """测试多格式解析与自适应截断。"""

    def test_text_parser_basic(self):
        """测试纯文本与源码解析。"""
        parser = TextParser()
        content = "def hello():\n    print('Hello World')\n"
        data = content.encode("utf-8")
        self.assertTrue(parser.can_parse("script.py", data))

        doc = asyncio.run(parser.parse("script.py", data))
        self.assertEqual(doc.format, "py")
        self.assertIn("def hello():", doc.text_content)

    def test_text_parser_gbk_encoding(self):
        """测试 GBK 中文编码探测。"""
        parser = TextParser()
        raw = "这是一份用 GBK 编码保存的中文会议记录。".encode("gbk")
        doc = asyncio.run(parser.parse("notes.txt", raw))
        self.assertIn("中文会议记录", doc.text_content)

    def test_docx_parser(self):
        """测试 Word (.docx) 解析与表格转 Markdown。"""
        try:
            import docx
        except ImportError:
            self.skipTest("环境未安装 python-docx")

        doc = docx.Document()
        doc.add_heading("项目进展总览", level=1)
        doc.add_paragraph("这是第一个正文段落。")

        table = doc.add_table(rows=2, cols=2)
        table.rows[0].cells[0].text = "模块名称"
        table.rows[0].cells[1].text = "状态"
        table.rows[1].cells[0].text = "文件阅读引擎"
        table.rows[1].cells[1].text = "已就绪"

        buf = io.BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()

        parser = DocxParser()
        self.assertTrue(parser.can_parse("report.docx", docx_bytes))

        parsed = asyncio.run(parser.parse("report.docx", docx_bytes))
        self.assertEqual(parsed.format, "docx")
        self.assertIn("# 项目进展总览", parsed.text_content)
        self.assertIn("| 模块名称 | 状态 |", parsed.text_content)
        self.assertIn("| 文件阅读引擎 | 已就绪 |", parsed.text_content)

    def test_excel_and_csv_parser(self):
        """测试 Excel 表格与 CSV 表格转 Markdown。"""
        parser = ExcelParser()

        # 1. 测试 CSV
        csv_content = "日期,事项,金额\n2026-10-31,服务器运维,500\n2026-11-01,插件重构,300\n"
        csv_bytes = csv_content.encode("utf-8")
        self.assertTrue(parser.can_parse("finance.csv", csv_bytes))

        parsed_csv = asyncio.run(parser.parse("finance.csv", csv_bytes))
        self.assertEqual(parsed_csv.format, "csv")
        self.assertIn("| 日期 | 事项 | 金额 |", parsed_csv.text_content)
        self.assertIn("| 2026-10-31 | 服务器运维 | 500 |", parsed_csv.text_content)

        # 2. 测试 XLSX
        try:
            import openpyxl
        except ImportError:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "统计清单"
        ws.append(["部门", "人数", "考核结果"])
        ws.append(["生活部", 12, "优秀"])
        buf = io.BytesIO()
        wb.save(buf)
        xlsx_bytes = buf.getvalue()

        parsed_xlsx = asyncio.run(parser.parse("dept.xlsx", xlsx_bytes))
        self.assertEqual(parsed_xlsx.format, "xlsx")
        self.assertIn("统计清单", parsed_xlsx.text_content)
        self.assertIn("| 部门 | 人数 | 考核结果 |", parsed_xlsx.text_content)
        self.assertIn("| 生活部 | 12 | 优秀 |", parsed_xlsx.text_content)

    def test_pdf_parser_text(self):
        """测试 PDF 文本提取。"""
        try:
            import pypdf
        except ImportError:
            self.skipTest("环境未安装 pypdf")

        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buf = io.BytesIO()
        writer.write(buf)
        pdf_bytes = buf.getvalue()

        parser = PDFParser()
        self.assertTrue(parser.can_parse("paper.pdf", pdf_bytes))

        vlm = MockVLMClient()
        parsed = asyncio.run(parser.parse("paper.pdf", pdf_bytes, vlm_client=vlm))
        self.assertEqual(parsed.format, "pdf")
        self.assertIn("第 1/1 页", parsed.text_content)

    def test_adaptive_truncate(self):
        """测试自适应结构化截断器。"""
        # 短文本保持原样
        short_text = "这是一篇很短的文章。"
        res, is_trunc = adaptive_truncate(short_text, max_chars=100)
        self.assertFalse(is_trunc)
        self.assertEqual(res, short_text)

        # 超长文本自适应保留 70% 头 + 30% 尾
        head = "【开头章节】" + "A" * 1000
        mid = "【中间细节】" + "B" * 5000
        tail = "【结尾总结】" + "C" * 1000
        full_text = head + mid + tail

        truncated, is_trunc = adaptive_truncate(full_text, max_chars=1000)
        self.assertTrue(is_trunc)
        self.assertTrue(truncated.startswith("【开头章节】"))
        self.assertTrue(truncated.endswith("C"))
        self.assertIn("已自适应保留关键开头", truncated)
        self.assertIn("安全截断中间内容", truncated)

    def test_registry_selection(self):
        """测试解析器工厂分发准确度。"""
        p_pdf = default_registry.select_parser("doc.pdf", b"%PDF-1.4")
        self.assertIsInstance(p_pdf, PDFParser)

        p_docx = default_registry.select_parser("doc.docx", b"PK\x03\x04")
        self.assertIsInstance(p_docx, DocxParser)

        p_xlsx = default_registry.select_parser("data.xlsx", b"PK\x03\x04")
        self.assertIsInstance(p_xlsx, ExcelParser)

        p_txt = default_registry.select_parser("readme.md", b"# Title")
        self.assertIsInstance(p_txt, TextParser)


if __name__ == "__main__":
    unittest.main()
