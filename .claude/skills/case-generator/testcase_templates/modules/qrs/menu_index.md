# 菜单参考用例索引

本文件维护 QRS（质量回顾系统）菜单路径到参考用例文件的映射。

> QRS 菜单来源于 PRD `qrs-0720.docx`「模块需求描述」章节，共 17 个业务模块 + 系统模块。

## 匹配规则

- 生成测试用例前，优先按本索引匹配菜单路径。
- 命中索引时，只读取索引表中的参考文件，具体路径以索引表为准。
- 若索引未命中，再读取该一级菜单目录下最相关的 `*_template.md` 参考文件。
- 参考用例只能读取 `testcase_templates/` 下的模板文件，不得读取 `outputs/` 下已生成用例作为参考。
- 若需求跨多个菜单，应读取所有命中的参考文件，用于去重和补充场景判断。
- 找不到对应菜单参考文件时，不阻塞生成，应在元信息或回复中记录缺失参考资料和生成假设。

## QRS 业务模块索引

| 分类 | 菜单路径 | 参考文件 |
|---|---|---|
| 门户展现层 | 首页 | `business/home_template.md` |
| 计划管理层 | 回顾计划 | `business/review_plan_template.md` |
| 计划管理层 | 任务管理 | `business/task_management_template.md` |
| 数据管理层 | 数据表模版 | `business/data_table_template.md` |
| 数据管理层 | 数据复核 | `business/data_review_template.md` |
| 分析管理层 | 数据分析 | `business/data_analysis_template.md` |
| 分析管理层 | 分析模版 | `business/analysis_template.md` |
| 分析管理层 | 分析结果 | `business/analysis_result_template.md` |
| 报告管理层 | 报告模版 | `business/report_template.md` |
| 报告管理层 | 回顾报告 | `business/review_report_template.md` |
| 基础数据层 | 回顾对象 | `business/review_object_template.md` |
| 业务支撑 | 监控与预警 | `business/monitor_alert_template.md` |
| 业务支撑 | 数据分析工作台 | `business/analysis_workbench_template.md` |
| 业务支撑 | 工作流配置 | `business/workflow_config_template.md` |
| 系统模块 | 用户管理 | `system/user_management_template.md` |
| 系统模块 | 角色管理 | `system/role_management_template.md` |
| 系统模块 | 审计追踪 | `system/audit_trail_template.md` |

> 参考文件按 `<category>/<level1_menu>/<level2_menu>_template.md` 组织。当前分为 `business`（业务模块）和 `system`（系统模块）两类，文件按需创建；未创建的参考文件不阻塞生成。

## 维护规则

- 使用可选分类时，每个 `<category>/` 下只维护一级菜单目录；不需要分类时直接从一级菜单目录开始。
- 一级菜单下的参考用例统一以 `_template.md` 作为公共后缀；二级菜单未拆分时使用 `<level2_menu>_template.md`，同一二级菜单下按需求或子功能拆分时使用 `<level2_menu>_<requirement_or_submodule>_template.md`。
- 新增、移动或重命名参考用例文件时，必须同步更新本索引。
- QRS PRD 升级或菜单调整时，应同步更新本索引的分类、菜单路径和参考文件路径。
