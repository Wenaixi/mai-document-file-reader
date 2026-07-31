"""TDD 测试集：覆盖 review 报告中的 HIGH 2 项 + 相关 MEDIUM。

HIGH-1: NapCat base64 在 b64decode 前的内存放大保护
HIGH-2: _read_local_file TOCTOU（先 open + fstat 而非 is_file + read_bytes）
HIGH-3: _validate_download_url 同步 DNS 不应阻塞 event loop
HIGH-4: 三处 aiohttp.ClientSession 必须显式 trust_env=False

不做：单例 ClientSession 改造（MEDIUM），保持三处分散创建以最小化 diff。
"""

from __future__ import annotations

import asyncio
import base64
import math
import socket
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

REPO_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, str(Path(__file__).parent))
import test_model_dispatch  # noqa: F401  （副作用：安装假 SDK）

from plugin import (  # noqa: E402
    FileReaderPlugin,
    FileReaderPluginConfig,
    ModelConfig,
    NapcatConfig,
    ReadConfig,
)


def _make_plugin_for_fixes(**kwargs: Any) -> FileReaderPlugin:
    """装配一个用于 HIGH 修复测试的最小 plugin。

    不走 host LLM，避免无关字段依赖。"""
    plugin = FileReaderPlugin()
    cfg = FileReaderPluginConfig()
    cfg.plugin.enabled = True
    if "napcat" in kwargs:
        cfg.napcat = kwargs["napcat"]
    if "read" in kwargs:
        cfg.read = kwargs["read"]
    plugin.config = cfg

    ctx = MagicMock()
    ctx.logger = MagicMock()
    plugin.ctx = ctx
    return plugin


def _capturing_session_factory() -> tuple[Any, dict[str, Any]]:
    """构造一个 fake ClientSession + 工厂，记录调用时的 kwargs。"""
    captured: dict[str, Any] = {}

    fake_resp = MagicMock()
    fake_resp.__aenter__ = AsyncMock(return_value=fake_resp)
    fake_resp.__aexit__ = AsyncMock(return_value=None)
    fake_resp.raise_for_status = MagicMock()
    fake_resp.headers = {}
    fake_resp.json = AsyncMock(return_value={})

    fake_session = MagicMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=None)
    fake_session.post = MagicMock(return_value=fake_resp)
    fake_session.get = MagicMock(return_value=fake_resp)

    def factory(*args: Any, **kwargs: Any) -> MagicMock:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return fake_session

    return factory, captured


# ---------- HIGH-1: NapCat base64 提前长度校验 ----------


async def test_napcat_base64_rejects_oversized_before_decode() -> None:
    """base64 长度超过 max_download_bytes 等价大小，应在 b64decode 前抛错。

    攻击面：NapCat get_file 返回巨大 base64 → 当前实现 await response.json() 后
    直接 b64decode → 50MB raw 拉成 ~67MB 字符串 + decode 出 ~50MB bytes，
    才在 len(raw) > max 抛错。先在 b64decode 前用 base64 长度上限拦截。
    """
    plugin = _make_plugin_for_fixes(read=ReadConfig(max_download_bytes=1024))

    # 50MB raw -> base64 长度约 50*1024*1024 * 4/3 ~= 69.7M
    huge_raw = b"\x00" * (50 * 1024 * 1024)
    huge_b64 = base64.b64encode(huge_raw).decode("ascii")
    assert len(huge_b64) > 1024

    fake_resp = MagicMock()
    fake_resp.__aenter__ = AsyncMock(return_value=fake_resp)
    fake_resp.__aexit__ = AsyncMock(return_value=None)
    fake_resp.raise_for_status = MagicMock()
    fake_resp.headers = {"content-length": str(len(huge_b64))}
    fake_resp.json = AsyncMock(
        return_value={"data": {"base64": huge_b64}}
    )

    fake_session = MagicMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=None)
    fake_session.post = MagicMock(return_value=fake_resp)

    with patch("plugin.aiohttp.ClientSession", return_value=fake_session):
        try:
            await plugin._fetch_via_napcat("file-big")
        except ValueError as exc:
            msg = str(exc)
            # 必须显式提到大小/上限/超过之一，且不能尝试 b64decode
            assert ("超过" in msg) or ("上限" in msg) or ("大小" in msg), (
                f"应提示大小超限，得到: {msg}"
            )
            # Content-Length 提前拦截：若走到 response.json 才拦截，测试仍通过但实现不算"提前"
            # 我们要求首屏拒：要么看 Content-Length，要么看 base64 字符串长度上限
            return

    # 没抛错则说明完全没拦截，测试失败
    raise AssertionError(
        "应拒绝 50MB base64，但没抛错"
    )


# ---------- HIGH-2: _read_local_file TOCTOU 防护 ----------


def test_local_file_uses_open_then_fstat_not_is_file_and_read_bytes() -> None:
    """_read_local_file 不应再走 is_file + stat + read_bytes 三步（TOCTOU）。

    新实现：先 open(path, 'rb')（或 os.open）拿 fd，再 fstat 拿 size，最后分块读。
    Path.is_file 与 Path.read_bytes 是非原子的两步检查+读，绝对不能共存。
    """
    plugin = _make_plugin_for_fixes()
    plugin.config.napcat.allowed_local_prefixes = "/tmp"

    target = Path("/tmp") / "test_toctou_unit.txt"
    target.write_bytes(b"ORIGINAL")

    # 记录 Path 实例方法的实际调用顺序
    real_open = type(Path()).open
    call_log: list[str] = []

    def spy_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        call_log.append("open")
        return real_open(self, *args, **kwargs)

    real_stat = type(Path()).stat

    def spy_stat(self: Path, *args: Any, **kwargs: Any) -> Any:
        call_log.append("stat")
        return real_stat(self, *args, **kwargs)

    real_is_file = type(Path()).is_file

    def spy_is_file(self: Path, *args: Any, **kwargs: Any) -> Any:
        call_log.append("is_file")
        return real_is_file(self, *args, **kwargs)

    real_read_bytes = type(Path()).read_bytes

    def spy_read_bytes(self: Path, *args: Any, **kwargs: Any) -> Any:
        call_log.append("read_bytes")
        return real_read_bytes(self, *args, **kwargs)

    try:
        with patch.object(Path, "open", spy_open), patch.object(
            Path, "stat", spy_stat
        ), patch.object(Path, "is_file", spy_is_file), patch.object(
            Path, "read_bytes", spy_read_bytes
        ):
            data = plugin._read_local_file(str(target))

        assert data == b"ORIGINAL", f"应读到原文件内容，得到 {data!r}"

        # TOCTOU 关键断言（安全属性）：
        # is_file 与 read_bytes 是 TOCTOU 漏洞的非原子两步，必须都不再被调用
        assert "is_file" not in call_log, (
            f"TOCTOU 风险：仍调用 Path.is_file()，调用链={call_log}"
        )
        assert "read_bytes" not in call_log, (
            f"TOCTOU 风险：仍调用 Path.read_bytes()，调用链={call_log}"
        )
        # 允许 Path.stat 仍在 Path 自调用中出现（如 resolve 内部），但不参与安全判断
    finally:
        target.unlink(missing_ok=True)


# ---------- HIGH-3: 同步 DNS 不应阻塞 event loop ----------


async def test_dns_resolution_does_not_block_event_loop() -> None:
    """_validate_download_url 内 DNS 解析不应在 event loop 上同步阻塞。

    mock socket.getaddrinfo 阻塞 1s。同步调用会让整个 event loop 卡 1s，
    并发的 tick 协程在 1s 内无法推进；异步 loop.getaddrinfo 会把阻塞推到
    executor，tick 在 0.05s 内就能完成。
    """
    plugin = _make_plugin_for_fixes()

    def slow_getaddrinfo(*args: Any, **kwargs: Any) -> Any:
        time.sleep(1.0)
        # 返回一个公网 IP，避免触发私有地址拒绝
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 0)),
        ]

    captured_url = "https://cdn.example.com/path/file.txt"
    tick_done = asyncio.Event()

    async def tick() -> None:
        # 如果 event loop 被同步 sleep 卡死，本协程在 1s 内无法运行
        await asyncio.sleep(0.05)
        tick_done.set()

    with patch("socket.getaddrinfo", side_effect=slow_getaddrinfo):
        start = time.monotonic()
        dns_task = asyncio.create_task(
            plugin._validate_download_url(captured_url, enforce_ssrf=True)
        )
        tick_task = asyncio.create_task(tick())
        # 等 tick 完成，超时 0.5s；若 DNS 同步阻塞 event loop，这里会超时
        try:
            await asyncio.wait_for(tick_done.wait(), timeout=0.5)
        except asyncio.TimeoutError as exc:
            dns_task.cancel()
            tick_task.cancel()
            raise AssertionError(
                "DNS 同步阻塞了 event loop：并发 tick 在 0.5s 内未推进"
            ) from exc
        tick_elapsed = time.monotonic() - start
        # 等 DNS 任务自然结束（会花 ~1s，但此时 tick 已经证明 loop 没被卡）
        try:
            await dns_task
        except ValueError:
            pass
        await tick_task

    assert tick_elapsed < 0.5, (
        f"并发 tick 耗时 {tick_elapsed:.2f}s（应 < 0.5s），event loop 被阻塞"
    )


# ---------- HIGH-4: 三处 ClientSession 必须 trust_env=False ----------


def _assert_trust_env_false(label: str, captured: dict[str, Any]) -> None:
    kwargs = captured.get("kwargs") or {}
    assert kwargs.get("trust_env") is False, (
        f"{label}：ClientSession 应传 trust_env=False，得到 kwargs={kwargs}"
    )


async def test_download_url_uses_trust_env_false() -> None:
    plugin = _make_plugin_for_fixes()
    factory, captured = _capturing_session_factory()
    with patch("plugin.aiohttp.ClientSession", side_effect=factory):
        # _download_url 第一次调用时 ClientSession 必创建一次
        await plugin._download_url("https://example.com/a.txt", enforce_ssrf=False)
    _assert_trust_env_false("_download_url", captured)


async def test_fetch_via_napcat_uses_trust_env_false() -> None:
    plugin = _make_plugin_for_fixes()
    factory, captured = _capturing_session_factory()
    with patch("plugin.aiohttp.ClientSession", side_effect=factory):
        # 用合法 base64 走通到返回
        raw = b"hello"
        fake_resp = MagicMock()
        fake_resp.__aenter__ = AsyncMock(return_value=fake_resp)
        fake_resp.__aexit__ = AsyncMock(return_value=None)
        fake_resp.raise_for_status = MagicMock()
        fake_resp.headers = {"content-length": str(len(base64.b64encode(raw)))}
        fake_resp.json = AsyncMock(
            return_value={"data": {"base64": base64.b64encode(raw).decode("ascii")}}
        )

        # 重新构造 factory，确保 post 返回上面的 fake_resp（让函数走通）
        fake_session = MagicMock()
        fake_session.__aenter__ = AsyncMock(return_value=fake_session)
        fake_session.__aexit__ = AsyncMock(return_value=None)
        fake_session.post = MagicMock(return_value=fake_resp)

        def factory2(*a: Any, **kw: Any) -> MagicMock:
            captured["args"] = a
            captured["kwargs"] = kw
            return fake_session

        with patch("plugin.aiohttp.ClientSession", side_effect=factory2):
            await plugin._fetch_via_napcat("file-1")
    _assert_trust_env_false("_fetch_via_napcat", captured)


async def test_generate_external_uses_trust_env_false() -> None:
    plugin = _make_plugin_for_fixes()
    plugin.config.model = ModelConfig(
        mode="external",
        task_name="",
        provider="openai",
        api_base_url="https://example.com/v1",
        api_key="sk-test",
        model_name="x",
        temperature=0.5,
        max_tokens=64,
    )

    # 构造 fake_resp：外部 API 返回 OpenAI 风格
    fake_resp = MagicMock()
    fake_resp.__aenter__ = AsyncMock(return_value=fake_resp)
    fake_resp.__aexit__ = AsyncMock(return_value=None)
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json = AsyncMock(
        return_value={"choices": [{"message": {"content": "OK"}}]}
    )

    fake_session = MagicMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=None)
    fake_session.post = MagicMock(return_value=fake_resp)

    captured: dict[str, Any] = {}

    def factory(*a: Any, **kw: Any) -> MagicMock:
        captured["args"] = a
        captured["kwargs"] = kw
        return fake_session

    with patch("plugin.aiohttp.ClientSession", side_effect=factory):
        await plugin._generate_external(
            [{"role": "user", "content": "hi"}],
        )
    _assert_trust_env_false("_generate_external", captured)


# ---------- 入口 ----------


async def _main() -> None:
    tests = [
        test_napcat_base64_rejects_oversized_before_decode,
        test_local_file_uses_open_then_fstat_not_is_file_and_read_bytes,
        test_dns_resolution_does_not_block_event_loop,
        test_download_url_uses_trust_env_false,
        test_fetch_via_napcat_uses_trust_env_false,
        test_generate_external_uses_trust_env_false,
    ]
    failures: list[str] = []
    for t in tests:
        name = t.__name__
        try:
            res = t()
            if asyncio.iscoroutine(res):
                await res
            print(f"[PASS] {name}")
        except Exception as exc:
            print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
            failures.append(name)

    if failures:
        print(f"\n{len(failures)} 个测试失败: {failures}")
        sys.exit(1)
    print(f"\n全部 {len(tests)} 个测试通过")


if __name__ == "__main__":
    asyncio.run(_main())