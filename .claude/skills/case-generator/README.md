# 测试用例生成器（多项目）

## 项目是什么

这是一个**基于 Claude Code 的 AI 测试用例生成工具**，以 Skill（技能插件）形式封装，服务于 **QRS（质量回顾系统）** 和 **CPV（持续工艺确认系统）** 等多个业务系统的功能测试工作。

核心价值：把需求文档（PRD）、界面设计图等输入，自动转化为结构化、可执行、可导出的测试用例，代替测试人员手工编写用例的重复劳动，并通过规则和脚本保证用例质量。

通过 `--project` 参数切换项目，各项目的业务常量、难度关键字、知识库、模板独立维护，通用脚本和规则共享。

## 项目结构

```
case-generator/
├── scripts/                          # 通用脚本（共享）
│   ├── business_constants.py         #   自动加载器（按 --project 切换配置）
│   ├── project_loader.py             #   项目配置加载入口
│   ├── case_utils.py                 #   核心工具（解析、难度推断、路径安全）
│   ├── validate_cases.py             #   校验器（通用校验 + 业务规则注册表）
│   ├── export_testcases.py           #   Excel 导出
│   ├── extract_docx.py               #   Word 提取
│   └── tests/                        #   单元测试
├── generation_rules/                 # 通用规则（共享框架）
│   ├── workflow_rules.md             #   工作流
│   ├── testcase_writing_guidelines.md #   编写规范
│   ├── coverage_dimension_rules.md   #   覆盖维度
│   ├── priority_rules.md             #   优先级
│   ├── difficulty_level_rules.md     #   难度框架（关键字在各项目下）
│   └── import_coverage_rules.md      #   导入覆盖规则
├── projects/                         # 项目专属配置
│   ├── qrs/
│   │   ├── business_constants.py     #   QRS 追踪字段、核心链路、站点类型
│   │   ├── difficulty_keywords.md    #   QRS 难度关键字
│   │   ├── knowledge_base/           #   QRS 知识库
│   │   └── coverage_rules/           #   QRS 专属覆盖规则
│   └── cpv/
│       ├── business_constants.py     #   CPV 追踪字段、核心链路、站点类型
│       ├── difficulty_keywords.md    #   CPV 难度关键字
│       ├── project_business_rules.py #   CPV 一键分析校验
│       └── knowledge_base/           #   CPV 知识库
├── testcase_templates/               # 参考用例（共享通用模板 + 项目专属模板）
│   ├── common_templates/             #   通用模板（边界 / 兼容 / 异常）
│   └── modules/
│       ├── qrs/                      #   QRS 菜单参考用例
│       │   └── menu_index.md
│       └── cpv/                      #   CPV 菜单参考用例
│           ├── menu_index.md
│           ├── business_site/        #   业务站点模板（13 个）
│           └── public_site/          #   公共管理站点模板
├── inputs/                           # 输入层（按项目隔离）
│   ├── qrs/
│   │   ├── requirements/
│   │   │   ├── raw_docs/             #   原始 Word（.docx）
│   │   │   └── archive/              #   历史 PRD 归档
│   │   └── ui_design/                #   界面设计图
│   └── cpv/
│       ├── requirements/
│       │   ├── raw_docs/
│       │   └── archive/
│       └── ui_design/
└── outputs/                          # 输出层（按项目 + 站点隔离）
    ├── qrs/
    │   └── business_site/
    │       ├── origin_exports/       #   原始 Markdown 用例
    │       └── excel_exports/        #   Excel 交付文件
    └── cpv/
        └── business_site/
            ├── origin_exports/
            └── excel_exports/
```

## 多项目支持

通过 `--project` 参数或 `CASE_GEN_PROJECT` 环境变量切换项目：

```bash
# QRS 项目
python scripts/validate_cases.py --project qrs --source ...

# CPV 项目
python scripts/validate_cases.py --project cpv --source ...

# 或用环境变量
export CASE_GEN_PROJECT=qrs
python scripts/validate_cases.py --source ...
```

| 项目 | 追踪字段 | 站点分类 | 核心链路 | 业务校验 |
|---|---|---|---|---|
| QRS | 关联模块、关联数据流、是否涉及 ALCOA+、是否涉及电子签名 | business_site / public_site | 6 条链路 | core_flow_coverage、group_depth_limit |
| CPV | 是否自动化、关联接口、用例测试类、关联项目 | business_site / public_site | 9 条链路 | core_flow_coverage、data_analysis_one_click、group_depth_limit |

## 工作流程

```
用户提供 Word 文件 + 章节名
       │
       ▼
① AI 提取章节内容
   - 用 extract_docx.py --project <name> --section "<章节名>" --print 直接从 .docx 提取
       │
       ▼
② AI 读取同名 UI 图目录（inputs/<project>/ui_design/<章节名>/）
       │
       ▼
③ AI 读取规则层和参考用例（只读）
       │
       ▼
④ AI 做生成前需求审查
       │
       ▼
⑤ AI 生成用例（Markdown）
       │
       ▼
⑥ 脚本校验（validate_cases.py --project <name>）
   有 ERROR？── 是 ──▶ AI 修复 ──▶ 重新校验
       │ 否
       ▼
⑦ 导出 Excel（export_testcases.py --project <name>）
       │
       ▼
⑧ 回复结果
```

## 快速开始

### 1. 准备输入文件

| 输入类型 | QRS 保存位置 | CPV 保存位置 |
|---|---|---|
| 原始 Word 文档 | `inputs/qrs/requirements/raw_docs/` | `inputs/cpv/requirements/raw_docs/` |
| UI 设计图 | `inputs/qrs/ui_design/<章节名>/` | `inputs/cpv/ui_design/<章节名>/` |
| 历史 PRD 归档 | `inputs/qrs/requirements/archive/` | `inputs/cpv/requirements/archive/` |

### 2. 提出需求

直接在对话中说明项目和章节名：

```
根据需求文档的"新增首页菜单"章节生成测试用例   ← 默认 QRS
根据 CPV 的"数据分析"章节生成测试用例
```

### 3. 获取输出

- Markdown：`outputs/<project>/business_site/origin_exports/<module_name>_testcases.md`
- Excel：`outputs/<project>/business_site/excel_exports/<module_name>_testcases.xlsx`

## 脚本命令

> 所有命令通过 `--project qrs/cpv` 指定项目，或设置环境变量 `export CASE_GEN_PROJECT=qrs`。

```bash
# 列出 Word 文档所有章节
python scripts/extract_docx.py --project qrs inputs/qrs/requirements/raw_docs/<文件名>.docx --list-sections

# 查找可用 Word 文档
python scripts/extract_docx.py --find-docs

# 从 Word 提取指定章节
python scripts/extract_docx.py --project qrs inputs/qrs/requirements/raw_docs/<文件名>.docx --section "<章节名>" --print

# 校验用例
python scripts/validate_cases.py --project qrs --source outputs/qrs/business_site/origin_exports/<module_name>_testcases.md

# 导出 Excel
python scripts/export_testcases.py --project qrs --source outputs/qrs/business_site/origin_exports/<module_name>_testcases.md

# 推荐：一次完成校验、导出 Excel 并回填实际生成耗时
python scripts/export_testcases.py --project qrs --source outputs/qrs/business_site/origin_exports/<module_name>_testcases.md --started-at
```

## Python 环境要求

大部分脚本仅使用 Python 标准库，建议使用 Python 3.10 或更高版本。

`extract_docx.py` 需要额外安装 `python-docx`，其余脚本无需额外依赖。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install python-docx
```

## 运行测试

```bash
cd .claude/skills/case-generator
pip install -r requirements-dev.txt
python -m pytest scripts/tests/ -v
```

## 设计思路

**多项目共享**：通用脚本和规则只维护一套，项目差异通过 `projects/<name>/` 配置隔离。`business_constants.py` 自动加载器按 `--project` 参数动态加载对应配置。

**质量门禁优先**：生成后必须通过脚本校验才能导出，有 ERROR 时强制修复。难度标签偏差已提升为 ERROR 级别。

**知识与规则分离**：业务知识（项目背景、流程）和生成规则（怎么写用例）分开存放，换项目时只需替换项目配置目录。

**参考用例只读**：`testcase_templates/` 存放高质量范例，AI 只读不写，新生成内容一律写入 `outputs/`。

**完整可追溯**：每条用例通过"分组 + 用例名称"定位，并在 `备注` 中记录具体来源；生成后附需求问题清单、用例统计摘要和需求覆盖率对照表。
