# 文件读插件（file-reader-plugin）

## 官方上游与版本溯源
- 官方仓库（Upstream Repository）：https://github.com/xiexiaojia780/file_reader_plugin
- 官方作者（Author / Maintainer）：xiexiaojia780
- 功能定位：文件阅读与文档解析插件
- 本地演进定位：基于官方上游最新版本，融入本地生产环境兼容性定制与稳定性加固。
- 本地专属定制：本地完成 task_name 模型调度解耦与沙盒白名单目录放行。


源: GitHub `xiexiaojia780/file-reader-plugin`

## 主人改过的关键文件

- `config.toml`：
  - `[http] http_base_url = "http://napcat:9999"`（Docker 内网服务名，不能写 127.0.0.1）。
  - `[allowed_local_prefixes]` 加 `/MaiMBot/data`、`/app`（Docker 容器内可访问的路径前缀）。

## 配置要点

- 上游 `.gitignore` 完整；主人段追加作一致性（确认 `!config.toml`、`!data/` 已生效）。

## 接入 & 依赖

- 与 NapCat `napcat:9999` HTTP API 通信（发文件到 QQ）。

## 关键日志

- `文件读取插件已加载`

## 用法

- 群内回复"读 文件路径"，机器人读文件内容（远程文件需配置 http 服务）。

## 历史脚注

- 2026-07-28: 从服务器同步到本地仓库（baseline head=`159c7a0`）；补充 `.gitignore` 主人段与本 CLAUDE.md。
