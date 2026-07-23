---
name: case-generator
description: 根据需求文档、界面设计图、业务规则和已有参考用例，为多个业务系统（QRS 质量回顾系统、CPV 持续工艺确认系统）生成结构化、可执行、可校验、可导出的测试用例。通过 --project 参数切换项目，业务关键字、追踪字段和覆盖词表以 projects/<name>/business_constants.py 为准。
---

# 测试用例生成器（多项目）

## 目标

为 QRS（质量回顾系统）、CPV（持续工艺确认系统）等多个业务系统生成结构化、可执行、可校验、可导出的功能测试用例。

生成结果必须面向真实业务场景，不能只输出"功能正常""页面展示正确"等空泛描述。

## 多项目支持

通过 `--project` 参数或 `CASE_GEN_PROJECT` 环境变量切换项目：

- `--project qrs`：QRS 质量回顾系统
- `--project cpv`：CPV 持续工艺确认系统

项目专属配置（追踪字段、模块名、核心链路、难度关键字、知识库、模板）在 `projects/<name>/` 下维护。
通用脚本和规则在 `scripts/` 和 `generation_rules/` 下共享。

## 适用场景

- 根据原始 Word PRD 或用户直接提供的需求文本生成各模块测试用例。
- 根据 UI 设计图补充页面展示、交互和校验用例。
- 补充、追加、覆盖或另存已有模块用例。
- 将 Markdown 用例校验并导出为分需求 Excel。

## 必读规则

生成、补充或导出用例前，按顺序读取以下文件：

1. `generation_rules/workflow_rules.md`
2. `generation_rules/testcase_writing_guidelines.md`
3. `generation_rules/coverage_dimension_rules.md`
4. `generation_rules/priority_rules.md`
5. `generation_rules/difficulty_level_rules.md`
6. `testcase_templates/modules/menu_index.md`

按需读取：

- 新项目首次接入、知识库为空、`validate_project_config.py` 存在配置警告，或用户要求初始化 / 通用化项目时，读取 `generation_rules/project_onboarding_rules.md`。
- 命中 `generation_rules/coverage_dimension_rules.md` 的专项规则路由时，必须先读取对应专项规则，再生成或补充用例；未命中专项规则路由时，不得读取对应专项规则文件。
- 任何涉及 Excel / CSV / 模板文件导入、批量导入、导入模板或错误报告的工作（含初次生成、补充、修改、拆分、重命名、删除任一导入用例），必须先读取 `generation_rules/import_coverage_rules.md`，并按规则全量核对本次涉及的所有导入用例后再继续。
- `testcase_templates/modules/menu_index.md` 命中的 `*_template.md` 参考用例。
- `knowledge_base/` 下业务知识文件（`project_overview.md` 已填入 QRS 系统背景）。
- `knowledge_base/core_flows/` 下与当前模块相关的流程。
- `testcase_templates/common_templates/` 下的异常、边界、兼容等通用模板。

规则职责：

| 文件 | 职责 |
|---|---|
| `project_onboarding_rules.md` | 新项目最小接入信息、资料优先级、缺失信息处理和输出命名 |
| `workflow_rules.md` | 输入处理、资料读取、输出路径、追加 / 覆盖 / 另存、去重、元信息、覆盖率、校验和导出闭环 |
| `testcase_writing_guidelines.md` | 动态分组列表头、字段写法、备注来源、标签和质量底线 |
| `coverage_dimension_rules.md` | 通用覆盖维度、高风险场景和专项规则路由 |
| `import_coverage_rules.md` | 文件导入、导入模板、批量导入和错误报告专项覆盖规则 |
| `priority_rules.md` | P0 / P1 / P2 判定 |
| `difficulty_level_rules.md` | `用例标签` 中的简单 / 一般 / 困难判定 |

## 执行流程

1. 判断需求影响模块和输出文件路径。
2. 若输入是 Word，按 `workflow_rules.md` 直接从 `.docx` 提取用户指定章节。
3. 若用户直接提供需求文本，按用户提供的文本范围提取章节及必要上下文。
4. 按章节名检查并读取 `inputs/ui_design/<章节名>/`。
5. 读取菜单索引和命中参考用例；参考用例只读，不修改。
6. 按 `coverage_dimension_rules.md` 判断是否命中项目专项规则；命中时先读取专项规则并形成生成前 checklist。
7. 若输出文件已存在且包含有效用例表，必须等待用户明确选择 `追加`、`覆盖` 或 `另存`。
8. 生成或更新 Markdown 用例：新建 / 覆盖 / 另存写入元信息块、需求问题清单、用例统计摘要、动态分组列表头的标准用例表和需求覆盖率对照表；追加模式不改写历史摘要和历史覆盖率，只补充本次新增记录。`生成耗时` 必须在校验和 Excel 导出完成后按实际耗时回填，最终交付文件不得保留估算值或待回填占位。
9. 运行 `validate_cases.py` 前先确认：若本次会话修改了任一专项规则覆盖的用例（导入、文件级异常等），必须重读对应专项规则并核对本次涉及用例全部合规；存在 ERROR 时先修复 Markdown，不导出 Excel。
10. 校验通过后运行 `export_testcases.py --source <md> --started-at`，按单个 Markdown 源文件导出同名 Excel，并在导出完成后回填实际 `生成耗时`。`--started-at` 不带值时自动从元信息块的"生成时间"行读取起点；元信息块的"生成时间"必须落盘为真实的开始读取资料时刻，不得瞎编。
11. 回复 Markdown 路径、Excel 路径、用例数量、覆盖模块和需求覆盖情况；追加模式需区分本次新增数量和文件合计数量。

## 关键约束

- 新生成或补充的用例只写入 `outputs/origin_exports/` 根目录，不再按项目分类创建子目录。
- Excel 交付默认分需求导出：`outputs/excel_exports/<module_name>_testcases.xlsx`。
- 不带 `--source` 或传入目录会生成合并 Excel，仅用于临时汇总，不作为默认交付方式。
- `export_testcases.py --clean` 只用于清理临时汇总 Excel，不作为删除分需求交付文件的手段。
- `testcase_templates/` 是只读参考库，不保存新生成用例。
- 不得静默覆盖已有有效用例文件。
- 不得通过删除业务场景绕过校验错误。
- 每条新用例的 `备注` 必须按 `testcase_writing_guidelines.md` 记录真实来源。
- 每条新用例必须填写 `一级分组`；`二级分组`、`三级分组` 及后续分组列按当前用例适用层级填写，没有对应节点时留空，不得为了补齐层级写入"通用场景"等占位值。分组值可以是页面、操作类型、子流程或子功能名称。
- 若 `business_constants.PROJECT_SPECIFIC_HEADERS` 声明了追踪字段，新生成用例的对应字段必须留空。
- 第三方软件、测试团队既有对比口径或业务确认值可作为测试判定依据时，不得仅因 PRD 未展开算法公式而写入需求问题清单。
- 命中专项规则时，需求覆盖率对照表必须包含适用默认覆盖项和不适用项的回查结果；回查项不得直接当作用例分组名。
- 直接依赖待确认需求的用例名称前加 `【待确认】`，并在需求问题清单中说明对应的用例处理方式。

## 常用命令

> 所有命令通过 `--project qrs/cpv` 指定项目，或设置环境变量 `export CASE_GEN_PROJECT=qrs`。

```bash
# 列出 Word 章节
python scripts/extract_docx.py --project qrs inputs/qrs/requirements/raw_docs/<文件名>.docx --list-sections

# 查找可用 Word 文档（忽略 ~$ 临时锁文件）
python scripts/extract_docx.py --find-docs

# 从 Word 直接提取章节内容（默认推荐）
python scripts/extract_docx.py --project qrs inputs/qrs/requirements/raw_docs/<文件名>.docx --section "<章节名>" --print

# 从 Word 提取章节内的嵌入图片到 inputs/qrs/ui_design/<章节名>/
python scripts/extract_docx.py --project qrs inputs/qrs/requirements/raw_docs/<文件名>.docx --section "<章节名>" --extract-images

# 校验单个 Markdown 用例文件
python scripts/validate_cases.py --project qrs --source outputs/qrs/business_site/origin_exports/<module_name>_testcases.md

# 仅修复 Markdown 表格格式
python scripts/validate_cases.py --project qrs --source outputs/qrs/business_site/origin_exports/<module_name>_testcases.md --fix

# 校验、导出 Excel 并回填实际生成耗时（推荐）
python scripts/export_testcases.py --project qrs --source outputs/qrs/business_site/origin_exports/<module_name>_testcases.md --started-at

# 不回填耗时，仅导出 Excel
python scripts/export_testcases.py --project qrs --source outputs/qrs/business_site/origin_exports/<module_name>_testcases.md
```

## 质量底线

- 前置条件必须可复现，写清用户、权限范围、数据状态和必要环境。
- 步骤必须可执行，使用有序编号。
- 预期结果必须可验证，包含页面反馈、数据状态或业务状态。
- 优先级只能使用 `P0`、`P1`、`P2`。
- `用例描述` 使用 `正例`、`反例`、`边界`、`权限`、`UI`、`兼容`、`回归`、`联动`。
- `用例标签` 只保留难度等级：`简单`、`一般` 或 `困难`。
