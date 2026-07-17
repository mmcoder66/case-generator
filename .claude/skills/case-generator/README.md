# 测试用例生成器

## 项目是什么

这是一个**基于 Claude Code 的 AI 测试用例生成工具**，以 Skill（技能插件）形式封装，服务于任意业务系统的功能测试工作。

核心价值：把需求文档、界面设计图等输入，自动转化为结构化、可执行、可导出的测试用例，代替测试人员手工编写用例的重复劳动，并通过规则和脚本保证用例质量。

> 这是一个**通用骨架版本**：业务关键字、追踪字段和核心链路词表都通过 `scripts/business_constants.py` 配置；业务知识存放在 `knowledge_base/`；新项目接入时只需替换这两个位置的业务内容，框架代码无需修改。

## 项目结构

```
case-generator/
├── knowledge_base/       # 知识层：项目背景、业务术语、用户角色、各模块核心流程（新项目按实际填充）
├── generation_rules/     # 规则层：编写规范、输出路径、优先级、覆盖维度、补充规则
├── testcase_templates/   # 参考层：各模块高质量参考用例（只读）
│   ├── common_templates/ # 通用格式模板（边界 / 兼容 / 异常）
│   └── modules/          # 菜单参考用例
│       ├── menu_index.md # 菜单路径到参考文件的索引
│       └── [<category>/]<level1_menu>/<level2_menu>_template.md
├── inputs/               # 输入层：本次生成的素材
│   ├── requirements/     # 需求文档
│   │   ├── raw_docs/     # 原始 Word 文档（.docx）
│   │   └── archive/      # 历史 PRD 归档
│   └── ui_design/        # 界面设计图，按章节名组织
└── outputs/              # 输出层
    ├── origin_exports/   # 原始测试用例（Markdown）
    └── excel_exports/    # Excel 交付文件
```

> Markdown 和 Excel 交付物直接保存在输出根目录下，不再创建项目分类子目录。

## 工作流程

```
用户提供 Word 文件 + 章节名
       │
       ▼
① AI 提取章节内容
   - 默认用 extract_docx.py --section "<章节名>" --print 直接从 .docx 提取章节
   - 原始 .docx 是需求事实源，不生成中间需求文件
       │
       ▼
② AI 读取同名 UI 图目录（inputs/ui_design/<章节名>/）
   目录存在且有图片时读取，否则跳过
       │
       ▼
③ AI 读取规则层和参考用例（只读）
   了解编写规范、该模块已有哪些场景
       │
       ▼
④ AI 做生成前需求审查
   对照 PRD、UI 图、知识库、规则和参考模板，
   列出需求不明确、资料冲突、需求遗漏和规则不一致问题
       │
       ▼
⑤ AI 生成用例
   按覆盖维度设计场景，附需求问题清单、用例统计摘要和需求覆盖率对照表，
   保存为 Markdown
       │
       ▼
⑥ 脚本校验（validate_cases.py）
   检查字段完整性、预期结果质量、场景重复等
       │
      有 ERROR？── 是 ──▶ AI 修复 ──▶ 重新校验
       │ 否
       ▼
⑦ 导出 Excel（export_testcases.py）
   生成带冻结表头、列宽、自动筛选的 .xlsx 文件
       │
       ▼
⑧ 回复结果
   文件路径、用例数量、覆盖模块、需求覆盖率
```

## 设计思路

**质量门禁优先**：生成后必须通过脚本校验才能导出，有 ERROR 时强制修复，防止空洞或格式错误的用例流入交付物。

**知识与规则分离**：业务知识（项目背景、流程）和生成规则（怎么写用例）分开存放，互不干扰，换项目时只需替换知识层（`knowledge_base/`）和业务常量（`scripts/business_constants.py`）。

**参考用例只读**：`testcase_templates/` 存放高质量范例，AI 只读不写，新生成内容一律写入 `outputs/origin_exports/`，模板不被污染。

**完整可追溯**：每条用例通过"分组 + 用例名称"定位，并在 `备注` 中记录具体来源；生成后附需求问题清单、用例统计摘要和需求覆盖率对照表，直接依赖待确认项的用例名称前加 `【待确认】`。

## 适用场景

| 场景 | 输入 | 输出 |
|---|---|---|
| 新功能上线前 | PRD 文件 | 功能、异常、边界等完整用例 |
| UI 改版 | 界面设计图说明 | 交互、展示、兼容性用例 |
| 补充存量模块 | 已有用例 + 新需求 | 去重后仅生成缺失场景 |

## 快速开始

### 1. 准备输入文件

| 输入类型 | 保存位置 | 说明 |
|---|---|---|
| 原始 Word 文档 | `inputs/requirements/raw_docs/` | 产品经理提供的 .docx，默认作为事实源直接按章节读取 |
| UI 设计图 | `inputs/ui_design/<章节名>/` | 目录名与 PRD 章节名一致，AI 自动匹配读取 |
| 历史 PRD 归档 | `inputs/requirements/archive/` | 已处理过的历史版本 |

### 2. 配置业务常量

打开 `scripts/business_constants.py`，按文件顶部的"换项目检查清单"填写：

- `PROJECT_SPECIFIC_HEADERS`：项目专属追踪字段（拼接到通用 9 列后）
- `SHEET_NAME` / `CREATOR_NAME`：Excel 品牌
- `COLUMN_WIDTH_BY_HEADER`：列宽
- `CORE_FLOW_KEYWORDS`：核心链路覆盖词表（可选，留空则跳过该业务校验）
- `ENABLED_BUSINESS_RULES`：启用的业务校验规则

### 3. 填充业务知识

先阅读 `generation_rules/project_onboarding_rules.md`，再按 `knowledge_base/README.md` 推荐结构，根据项目实际填充：

- `knowledge_base/project_overview.md`
- `knowledge_base/business_glossary.md`
- `knowledge_base/user_roles.md`
- `knowledge_base/core_flows/<flow_name>.md`

### 4. 填充难度关键字（可选）

`generation_rules/difficulty_level_rules.md` 中每个 `difficulty-rule` 配置块当前是 `<TODO_*>` 占位符。新项目按业务实际替换为关键字，即可让难度推断命中强规则路径；不想使用强规则关键字时可保留占位符（评分机制仍可用）。

### 5. 校验项目配置

生成正式用例前，建议先运行项目配置校验，检查旧项目残留、临时 Word 文件、输出产物污染和关键配置缺失：

```bash
python scripts/validate_project_config.py
```

### 6. 提出需求

直接在对话中说明 PRD 文件和章节名，无需手动执行任何脚本：

```
根据需求文档的"<章节名>"章节生成测试用例
```

```
根据需求文档的"<章节名>"章节追加生成测试用例
```

不确定章节名时，可以先问：

```
<文件名>.docx 里有哪些章节？
```

### 7. 获取输出

Agent 会自动完成校验和导出，最终输出：

- Markdown 用例文件：`outputs/origin_exports/<module_name>_testcases.md`
- 分需求 Excel 文件：`outputs/excel_exports/<module_name>_testcases.xlsx`

Markdown 用例文件包含元信息块、需求问题清单、用例统计摘要、标准用例表和需求覆盖率对照表。标准用例表使用连续分组列加固定业务字段；`一级分组` 必须填写，`二级分组`、`三级分组` 及后续分组按实际业务层级填写，没有对应节点时留空。若 PRD / UI 未明确具体字段、范围、格式、状态、影响对象或生效条件，且现有规则或测试团队既有判定口径无法给出可执行预期，会在需求问题清单中标记；直接依赖待确认项的用例名称前加 `【待确认】`。

不带 `--source` 或传入目录批量导出时，脚本会生成 `测试用例导出_YYYYMMDD_HHMMSS.xlsx` 汇总文件；交付时默认按单个 Markdown 源文件分别导出同名 Excel。

## Python 环境要求

大部分脚本仅使用 Python 标准库，建议使用 Python 3.10 或更高版本。

`extract_docx.py` 需要额外安装 `python-docx`，其余脚本无需额外依赖。

### 初始化虚拟环境

**macOS / Linux：**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install python-docx
```

激活后直接用 `python` 运行脚本即可。

**Windows：**

> 注意：项目路径较长时，Windows 长路径限制会导致在项目目录内创建虚拟环境失败。建议在短路径下创建，例如 `C:\venv\testcase`。

```powershell
python -m venv C:\venv\testcase
C:\venv\testcase\Scripts\pip install python-docx
```

运行脚本时用完整路径：

```powershell
C:\venv\testcase\Scripts\python scripts/extract_docx.py ...
```

## 脚本命令

```bash
# 列出 Word 文档所有章节（不确定章节名时先执行）
python scripts/extract_docx.py inputs/requirements/raw_docs/<文件名>.docx --list-sections

# 查找可用 Word 文档（会忽略 ~$ 开头的 Word 临时锁文件）
python scripts/extract_docx.py --find-docs

# 从 Word 直接提取指定章节（正式生成默认推荐）
python scripts/extract_docx.py inputs/requirements/raw_docs/<文件名>.docx --section "<章节名>" --print

# 校验本次生成的用例
python scripts/validate_cases.py --source outputs/origin_exports/<module_name>_testcases.md

# 导出 Excel（校验通过后执行）
python scripts/export_testcases.py --source outputs/origin_exports/<module_name>_testcases.md

# 推荐：一次完成校验、导出 Excel 并回填实际生成耗时
python scripts/export_testcases.py --source outputs/origin_exports/<module_name>_testcases.md --started-at

# 导出并清理历史 xlsx，仅保留本次文件
python scripts/export_testcases.py --source outputs/origin_exports/<module_name>_testcases.md --clean

# 如需校验参考用例库，显式指定 source
python scripts/validate_cases.py --source testcase_templates/modules

# 校验通用项目配置和残留
python scripts/validate_project_config.py
```

> 不带 `--source` 时脚本会默认递归扫描 `outputs/origin_exports/` 下所有用例文件；
> 分需求导出时必须显式指定单个 Markdown 文件，避免生成合并 Excel。

## 运行测试

核心纯函数（表头识别、难度推断、XML 转义等）配有 pytest 单元测试，便于在改动后快速回归。

```bash
cd .claude/skills/case-generator
pip install -r requirements-dev.txt
python -m pytest scripts/tests/ -v
```

> 改动 `scripts/` 下任何代码或 `generation_rules/difficulty_level_rules.md` 后，请运行 `python -m pytest scripts/tests/ -v` 确认无回归。

## 文件说明

- **SKILL.md**：Agent 执行规则，包含完整的生成流程和质量要求
- **README.md**：给使用者看的快速上手说明
- **scripts/business_constants.py**：业务常量集中入口（追踪字段、Excel 品牌、核心链路词表、业务校验开关），换项目时改这一处即可全局生效
- **scripts/validate_project_config.py**：检查项目接入配置、旧业务残留、临时 Word 文件和输出产物污染
- **scripts/case_utils.py**：测试用例表头定义、Markdown 解析、难度推断、路径安全
- **scripts/extract_docx.py**：从 Word 提取章节 / 列章节 / 提取嵌入图片
- **scripts/validate_cases.py**：校验格式、质量、优先级和重复场景
- **scripts/export_testcases.py**：导出 Excel
- **testcase_templates/modules/**：按可选分类和一级菜单组织的参考用例库，参考文件统一以 `_template.md` 作为公共后缀；二级菜单未拆分时用 `<level2_menu>_template.md`，按需求或子功能拆分时用 `<level2_menu>_<requirement_or_submodule>_template.md`，只读使用，不保存新生成用例
- **outputs/origin_exports/**：原始 Markdown 用例保存位置
- **outputs/excel_exports/**：Excel 导出文件保存位置

输出文件按业务模块聚合，不按分类、租户、组织或二级菜单继续拆分。

## 参考模块路径

参考文件路径以 `testcase_templates/modules/menu_index.md` 为准，根 README 不再重复维护完整索引表。若需要区分不同产品线、终端或业务域，可在 `modules/` 下增加一层可选 `<category>`；否则直接按一级菜单目录维护。一级菜单下的参考文件统一以 `_template.md` 作为公共后缀。二级菜单未拆分或本身已足够精确时用 `<level2_menu>_template.md`，同一二级菜单下按需求或子功能拆分时用 `<level2_menu>_<requirement_or_submodule>_template.md`。目录名和文件名必须全部小写，不带空格，以 `_` 分隔单词。
