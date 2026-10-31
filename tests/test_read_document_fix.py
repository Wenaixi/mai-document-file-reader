
import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import tomllib
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_DIR))
import test_model_dispatch

class TestReadDocumentFix(unittest.TestCase):
    def test_read_document_accepts_stream_id_and_kwargs(self):
        # 验证 plugin.py 中 read_document 签名与防御性入参
        from plugin import FileReaderPlugin, FileReaderPluginConfig
        
        plugin = FileReaderPlugin()
        plugin.config = FileReaderPluginConfig()
        plugin.config.plugin.enabled = True
        
        # mock _fetch_file_bytes 与 _decode_document 以及 LLM
        plugin._fetch_file_bytes = AsyncMock(return_value=(b"sample text", "test_source"))
        plugin._decode_document = AsyncMock(return_value=("Extracted file content", False, "text"))
        plugin._generate_external = AsyncMock(return_value={"success": True, "response": "Summary OK"})
        plugin.ctx = MagicMock()
        plugin.ctx.llm = MagicMock()
        plugin.ctx.llm.generate = AsyncMock(return_value={"success": True, "response": "Summary OK"})
        plugin.ctx.llm.generate_with_tools = AsyncMock(return_value={"success": True, "response": "Summary OK"})

        # 重点：模拟 MaiBot 宿主传入主参数 file_id、stream_id 及额外上下文参数
        res = asyncio.run(
            plugin.read_document(
                file_id="test.txt",
                user_query="概括一下",
                stream_id="stream_abc_123",
                chat_id="chat_456",
                bot_name="麦麦",
                extra_unknown_arg="should_not_crash"
            )
        )
        self.assertIn("Summary OK", res)

    def test_read_document_supports_alias_parameters(self):
        from plugin import FileReaderPlugin, FileReaderPluginConfig
        
        plugin = FileReaderPlugin()
        plugin.config = FileReaderPluginConfig()
        plugin.config.plugin.enabled = True
        
        plugin._fetch_file_bytes = AsyncMock(return_value=(b"alias text", "test_source"))
        plugin._decode_document = AsyncMock(return_value=("Alias content", False, "text"))
        plugin.ctx = MagicMock()
        plugin.ctx.llm = MagicMock()
        plugin.ctx.llm.generate_with_tools = AsyncMock(return_value={"success": True, "response": "Alias OK"})

        # 模型未传 file_reference 而是传入了别名 file_id
        res = asyncio.run(
            plugin.read_document(
                file_id="FID_9999",
                user_query="总结",
                stream_id="s1"
            )
        )
        self.assertIn("Alias OK", res)
        plugin._fetch_file_bytes.assert_awaited_once_with("FID_9999")

    def test_config_token_matches_http_port_3000(self):
        config_path = PLUGIN_DIR / "config.toml"
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        
        token = data.get("napcat", {}).get("access_token", "")
        # 必须匹配 Snowluma HTTP 3000 端口在 onebot.json 中设定的真实 token
        self.assertEqual(token, "4CRC3EUGqk6Kq2H10XpNDyFrdJgaLua8ugi0IEa--Xs")

    def test_resolve_file_from_db_returns_url_and_file_id(self):
        from plugin import FileReaderPlugin, FileReaderPluginConfig
        import sqlite3
        import msgpack

        plugin = FileReaderPlugin()
        plugin.config = FileReaderPluginConfig()

        # 创建一个临时测试 SQLite 库
        test_db = PLUGIN_DIR / "tests" / "_test_temp_msg.db"
        conn = sqlite3.connect(str(test_db))
        cur = conn.cursor()
        cur.execute("CREATE TABLE mai_messages (id INTEGER PRIMARY KEY, processed_plain_text TEXT, raw_content BLOB)")
        
        # 写入一条包含 xlsx 文件的 raw_content
        sample_seg = [{
            "type": "file",
            "data": {
                "name": "测试名单.xlsx",
                "file_id": "FID_TEST_123",
                "url": "https://example.com/download/test.xlsx"
            }
        }]
        packed = msgpack.packb(sample_seg)
        cur.execute("INSERT INTO mai_messages VALUES (1, '[文件] 测试名单.xlsx', ?)", (packed,))
        conn.commit()
        conn.close()

        with patch("pathlib.Path.exists", return_value=True), patch("sqlite3.connect", return_value=sqlite3.connect(str(test_db))):
            url, fid = plugin._resolve_file_from_db("测试名单.xlsx")
            self.assertEqual(url, "https://example.com/download/test.xlsx")
            self.assertEqual(fid, "FID_TEST_123")

        test_db.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
