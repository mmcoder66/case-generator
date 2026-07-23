# 需求文档目录

## 目录结构

```text
requirements/
├── raw_docs/           # 原始 Word 文档（.docx）
│   └── <TODO: 当前 PRD 文件名>.docx
└── archive/            # 历史原始 PRD（按需手动归档）
```

## 使用规则

- `raw_docs/` 存放当前使用的原始需求文档。
- Word `.docx` 是默认事实源；生成用例时直接从 `.docx` 提取用户指定章节。
- PDF 等其他格式仅作归档；如需使用，应先转为 `.docx` 或由用户提供文本内容。
- UI 设计图不放在本目录，按章节名放在 `inputs/<project>/ui_design/<章节名>/` 下。
- 本目录文件不会被脚本自动扫描，只有用户在对话中指定文件和章节时才读取。

示例：

```text
根据 inputs/<project>/requirements/raw_docs/<文件名>.docx 的"<章节名>"章节生成测试用例
```

## 可选操作

不确定章节名时，可以先列出 Word 章节：

```bash
python scripts/extract_docx.py inputs/<project>/requirements/raw_docs/<文件名>.docx --list-sections
```

不确定当前有哪些可用 Word 文档时，可以先查找：

```bash
python scripts/extract_docx.py --find-docs
```

需要查看章节原文时，可以直接提取指定章节：

```bash
python scripts/extract_docx.py inputs/<project>/requirements/raw_docs/<文件名>.docx --section "<章节名>" --print
```

提取时图片会被忽略，文字和表格尽量保留为可读文本。UI 设计图不放在需求目录，按章节名放在 `inputs/<project>/ui_design/<章节名>/` 下。

## 归档规则

- `archive/` 用于保存已经处理过或暂时不用的历史 PRD。
- 更换 PRD 前，可按需把旧 Word 文件移动或复制到 `archive/` 归档。
- 归档文件只作追溯，不作为默认生成入口；如需基于归档文件生成，应在对话中显式指定文件路径。

## 阅读重点

读取需求文档时，重点提取：

- 需求背景与功能入口
- 涉及用户角色、权限范围和数据隔离范围
- 菜单权限和按钮权限
- 主流程、分支流程、状态流转规则
- 字段校验规则、异常处理规则
- 审批流和签名规则
- 操作日志与追溯要求
- 数据来源、数据处理规则
- 页面跳转规则和跨模块联动关系
- 异步任务、导入导出、结果推送和失败重试规则
- 数据隔离、版本管理和历史记录要求
- 验收标准
