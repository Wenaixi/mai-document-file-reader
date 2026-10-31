# 麦麦智能多格式文档阅读引擎 (wenaixi_mai_document_file_reader)

> 本插件由 [Wenaixi](https://github.com/Wenaixi) 维护，是专为生产环境深度调优的高可用多模态阅读分支。

## 简介与定位

支持对群聊、私聊中发送或引用的各类文档执行深度阅读与提炼分析。已彻底打破传统单文件纯文本限制，全面支持 Word、PDF、Excel、PPT、各类代码源文件与数据表格，并具备 PDF 扫描页/图表 VLM 视觉大模型深度识别与全格式自适应截断保护。

- **插件目录**：`wenaixi_mai_document_file_reader`
- **生效版本**：`v1.0.0`
- **开源许可证**：`GPL-3.0-or-later`
- **托管仓库**：[`Wenaixi/mai-document-file-reader`](https://github.com/Wenaixi/mai-document-file-reader)

---

## 核心特性与架构升级

1. **全格式文档解析引擎**：
   - **Word 文档 (`.docx`)**：提取正文、多级标题，并将 Word 原生表格提取转换为排版优美的 Markdown 表格；
   - **PDF 文档 (`.pdf`)**：逐页解析文本结构，自动判定扫描页与图表；
   - **Excel/CSV 表格 (`.xlsx`, `.csv`)**：自动将多工作表转为 Markdown 表格，并具备行列边界安全保护；
   - **PPT 幻灯片 (`.pptx`)**：逐页提取幻灯片大纲、文本块与演讲者备忘录；
   - **代码与纯文本**：支持 UTF-8、GBK、GB18030 工业级四级容错解码，覆盖全语言源码与日志。
2. **VLM 视觉多模态图表联动**：
   - 当检测到 PDF 页面为图片扫描页（文字 < 50 字符）或包含关键复杂架构图/图表时，自动提取图片调用宿主 `vlm` 任务（`vision` 视觉模型）生成图表解读并无缝嵌入文档正文；
   - 单文档设定最大 `max_images_per_file`（默认 3 张）调用保护，杜绝 Token 账单被刷爆。
3. **全格式自适应结构化截断器**：
   - 超过 `max_chars`（默认 20,000 字）时，自适应保留文档开头目录与架构（前 70%）及结尾总结结论（后 30%），绝不暴力截断。
4. **双轨驱动（命令 + 大模型自主 Agent 工具）**：
   - 支持传统指令：`/读文件 [要求]`；
   - 新增导出大模型工具：`@Tool("read_document")`，允许麦麦 Planner 在群聊中遇到用户说“帮我看下这份文件”时自主提取 `file_id` 并分析回答。

---

## 指令与工具速查

### 常用指令 (Command)
- `/读文件 [要求]` - 读取当前消息附带的文件或回复/引用的文件（别名 `/readfile`）
- `/读文件 <文件ID/URL> [要求]` - 通过指定文件 ID 或直链进行阅读

### 大模型工具 (Tool)
- `@Tool("read_document")` - 供麦麦大脑自主调用的深度文档阅读与分析工具

---

## 快速配置

配置文件统一定位于插件根目录下的 `config.toml`。修改后热重载或重启容器即可生效。

```toml
[vlm]
enabled = true             # 是否开启图表/扫描页 VLM 视觉分析
task_name = "vlm"          # 宿主视觉模型任务名
max_images_per_file = 3    # 单文档最多分析图表数

[formats]
enable_pdf = true          # 启用 PDF
enable_docx = true         # 启用 Word
enable_excel = true        # 启用 Excel/CSV
enable_pptx = true         # 启用 PPT

[read]
max_chars = 20000          # 自适应截断上限字符数
max_download_bytes = 15728640 # 最大允许下载体积 (15MB)
```

---

## 上游项目与开源溯源

- **原作者 / 组织**：`xiexiaojia780`
- **官方原版开源仓库**：[https://github.com/xiexiaojia780/file_reader_plugin](https://github.com/xiexiaojia780/file_reader_plugin)
- **开源协议**：`GPL-3.0-or-later`
- **声明**：本项目遵循开源协议，特此致敬原作者的杰出贡献。本分支针对生产环境的高并发网络、个性化社交和多格式阅读需求进行了深度重构与定制化演进。
