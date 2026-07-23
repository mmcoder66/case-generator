# QRS 业务知识库

本目录存放 QRS（质量回顾系统）的业务知识，供 Agent 生成用例时参考。

> 知识库以 `inputs/<project>/requirements/raw_docs/qrs-0720.docx` 为事实源。如本目录内容与 PRD 原文冲突，以 PRD 原文为准。

## 目录结构

```
knowledge_base/
├── project_overview.md      # ✅ 已填入：QRS 系统定位、价值主张、功能架构图、核心业务主线流程、数据流转关系、模块索引
├── business_glossary.md     # ⏳ 待补充：QRS 业务术语、状态枚举、字段约束、单位规范
├── user_roles.md            # ⏳ 待补充：6 类角色的详细权限矩阵
└── core_flows/              # ⏳ 待补充：QRS 端到端业务流程
    └── <flow_name>.md
```

## 已填入内容

| 文件 | 内容来源 | 关键章节 |
|---|---|---|
| `project_overview.md` | PRD「系统定位与价值主张」「系统功能架构图」「核心业务主线流程」「数据流转关系」「目标用户与角色权限」「术语定义与缩略语」 | QRS 系统定位、ICH Q8/Q9/Q10 法规基准、6 层 11 模块架构、11 个模块依赖矩阵、10 条数据流（DF-001~DF-010）、6 类角色、12 个核心术语 |

## 待补充内容

### `business_glossary.md`

QRS 状态枚举与字段约束：

- **业务状态枚举**：草稿、待审批、审批中、已批准、已退回、已关闭、已生效、已复核、已完成、已放行、已归档等
- **参数类型**：CQA、CPP、IPC 的字段约束（数据类型、单位、规格限 USL/LSL、显示顺序）
- **统计指标**：Cpk、Ppk、SPC 控制图、趋势分析的算法口径
- **审计追踪字段**：操作人、操作时间、操作前后值、电子签名规则

### `user_roles.md`

6 类角色的详细权限矩阵：

| 角色 | 菜单权限 | 按钮权限 | 数据权限 |
|---|---|---|---|
| 质量经理 / QA Director | 全部 | 审批、放行、退回 | 全局 |
| QA 专员 | 全部业务模块 | 创建、复核、提交 | 本部门 |
| 工艺工程师 | 数据分析、监控与预警、回顾报告 | CPP 监控、异常调查 | 工艺技术部 |
| 生产人员 | 数据复核（仅录入） | 录入、提交 | 生产制造部 |
| 实验室人员 / QC | 数据复核（仅录入） | 录入、复核 | 质量控制部 |
| 系统管理员 | 用户管理、角色管理、基础数据 | 全部 | 全局 |

### `core_flows/<flow_name>.md`

QRS 端到端业务流程（建议补充以下流程）：

- `core_flows/review_plan_lifecycle.md`：回顾计划从创建到审批的全生命周期
- `core_flows/data_review_lifecycle.md`：原始数据录入到复核确认的全流程
- `core_flows/data_analysis_lifecycle.md`：从分析模版选择到分析结果生成的全流程
- `core_flows/report_generation_lifecycle.md`：从报告模版实例化到审批放行的全流程
- `core_flows/task_driven_execution.md`：任务驱动数据复核 / 分析 / 报告的执行链路

## 维护原则

- PRD 升级时，应同步更新本目录下的知识文件。
- 业务术语、状态枚举不得自行推断；未明确时按 PRD 原文归类，并写入生成假设。
- Agent 生成用例时会读取本目录作为业务上下文，因此本目录的准确性直接影响用例质量。
- 如本目录为空或关键文件缺失，Agent 会按 `generation_rules/project_onboarding_rules.md` 的缺失信息处理方式执行。
