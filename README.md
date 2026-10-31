# 文件阅读插件

> 本插件由 [Wenaixi](https://github.com/Wenaixi) 维护，是专为生产环境深度调优的高可用分支。

## 简介与定位

读取群聊中的纯文本文件交给 LLM 分析概括或提取要点。

- **插件目录**：`github_xiexiaojia780_file-reader-plugin`
- **生效版本**：`v1.2.9`
- **开源许可证**：`MIT`

---

## 核心特性与本地深度调优

- 全面转接至 SnowLuma 3000 端口与 Token
- 注入 20,000 字超大文本安全截断保护，杜绝模型显存撑爆崩溃

---

## 指令与工具速查

### 常用指令 (Command)
- `/读文件 [要求] - 读取引用或指定的文件`

### 大模型工具 (Tool)
- `(指令与引用消息触发型插件)`

---

## 快速配置

配置文件统一定位于插件根目录下的 `config.toml`。修改后重启或通过 WebUI 热重载即可生效。

---

## 上游项目与开源溯源

- **原作者 / 组织**：`xiexiaojia780`
- **官方原版开源仓库**：[https://github.com/xiexiaojia780/file-reader-plugin](https://github.com/xiexiaojia780/file-reader-plugin)
- **开源协议**：`MIT`
- **声明**：本项目遵循开源协议，特此致敬原作者的杰出贡献。本分支针对生产环境的高并发网络、个性化社交和抗风控需求进行了深度稳定性修复与定制化演进。
