# CLAUDE.md - 文件阅读插件 (github_xiexiaojia780_file-reader-plugin)

## 1. 模块定位与系统职责
- **插件标识符**：`github_xiexiaojia780_file-reader-plugin`
- **当前生效版本**：`v1.2.9`
- **托管仓库**：[`Wenaixi/file_reader_plugin`](https://github.com/Wenaixi/file_reader_plugin)
- **核心定位**：读取群聊中的纯文本文件交给 LLM 分析概括或提取要点。

## 2. 关键工程规范与配置说明
- **配置路径**：`config.toml`（所有业务调优与鉴权参数收敛于此）；
- **数据持久化**：优先遵循 MaiBot SDK 标准持久化规范，不直接向源码目录写入易失数据；
- **编码与日志规范**：严格遵循 PEP 8 风格，文档与代码注释杜绝 emoji，避免虚假套话。

## 3. 本地深度定制与稳定性修复
全面对齐 SnowLuma 3000 HTTP 接口与 Token；增加超大文本 20,000 字自适应安全截断保护，防止大文档炸爆大模型显存。

---

## 上游项目与开源溯源
- **原作者 / 组织**：`xiexiaojia780`
- **官方上游仓库**：[https://github.com/xiexiaojia780/file-reader-plugin](https://github.com/xiexiaojia780/file-reader-plugin)
- **开源许可证**：`MIT`
- **分支演进模式**：本仓库作为主人的深度定制与生产维护分支（`Wenaixi/file_reader_plugin`）。在保持与官方上游架构演进对齐的同时，锁死并持续维护针对本服务器生产环境的稳定性补丁与核心特性。
