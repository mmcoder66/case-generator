# CPV 菜单参考用例索引

本文件只维护 CPV 菜单路径到参考用例文件的映射。

## 匹配规则

- 生成测试用例前，优先按本索引匹配 CPV 菜单路径。
- 命中索引时，只读取索引表中的参考文件，具体路径以索引表为准。
- 若索引未命中，再读取该一级菜单目录下最相关的 `*_template.md` 参考文件。
- 参考用例只能读取 `testcase_templates/` 下的模板文件，不得读取 `outputs/` 下已生成用例作为参考。
- 若需求跨多个菜单，应读取所有命中的参考文件，用于去重和补充场景判断。
- 找不到对应菜单参考文件时，不阻塞生成，应在元信息或回复中记录缺失参考资料和生成假设。

| 站点分类 | CPV 菜单路径 | 参考文件 |
|---|---|---|
| 公共管理站点 | 公共管理站点 / 审计追踪 | `public_site/audit_trail/audit_trail_permission_manage_template.md` |
| 业务站点 | 业务站点 / 配置管理 / 角色管理 / 导入导出 | `business_site/configuration_manage/role_manage_import_export_template.md` |
| 业务站点 | 业务站点 / 配置管理 / 审计追踪 / 角色管理 | `business_site/configuration_manage/audit_trail_role_manage_template.md` |
| 业务站点 | 业务站点 / 计划管理 / 年度计划设置 | `business_site/plan_manage/annual_plan_settings_template.md` |
| 业务站点 | 业务站点 / 计划管理 / 任务管理 | `business_site/plan_manage/task_manage_template.md` |
| 业务站点 | 业务站点 / 方案管理 / 方案模板 | `business_site/scheme_manage/scheme_templates_template.md` |
| 业务站点 | 业务站点 / 方案管理 / 方案编制 | `business_site/scheme_manage/scheme_formulation_template.md` |
| 业务站点 | 业务站点 / 方案执行 / 相关性分析汇总 | `business_site/scheme_execution/correlation_analysis_template.md` |
| 业务站点 | 业务站点 / 方案执行 / 监控项目 / 单值控制图 | `business_site/scheme_execution/monitoring_items_i_chart_template.md` |
| 业务站点 | 业务站点 / 方案执行 / 监控项目 / 箱线图 | `business_site/scheme_execution/monitoring_items_box_plot_template.md` |
| 业务站点 | 业务站点 / 方案执行 / 监控项目 / 配对T检验 | `business_site/scheme_execution/monitoring_items_paired_t_template.md` |
| 业务站点 | 业务站点 / 报告管理 / 报告编制 | `business_site/report_manage/report_generation_template.md` |
| 业务站点 | 业务站点 / 报告管理 / 报告模板 | `business_site/report_manage/report_templates_template.md` |

## 维护规则

- `public_site/` 和 `business_site/` 下只维护一级菜单目录。
- 一级菜单下的参考用例统一以 `_template.md` 作为公共后缀；二级菜单未拆分时使用 `<level2_menu>_template.md`，同一二级菜单下按需求或子功能拆分时使用 `<level2_menu>_<requirement_or_submodule>_template.md`。
- 新增、移动或重命名参考用例文件时，必须同步更新本索引。
