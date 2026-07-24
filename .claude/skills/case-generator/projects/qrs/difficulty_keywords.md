# QRS 难度关键字配置

> 本文件由 `case_utils.py` 的 `_load_difficulty_rule_config()` 自动加载。
> 框架规则（评分表、判定顺序、字段匹配口径）见 `generation_rules/difficulty_level_rules.md`。

---

## 困难强规则（命中即判"困难"，不进入综合评分）

### 高置信困难强规则关键字

> 匹配字段：`用例名称`、`用例步骤`、`预期结果`。命中任一直接判"困难"。

<!-- difficulty-rule:difficult_high_confidence_keywords -->
`跨模块联动`
`跨环境迁移`
`外部工具对比`
<!-- /difficulty-rule -->

### 仅用例名称困难强规则关键字

> 匹配字段：仅 `用例名称`。出现在预期结果中不抬高难度。

<!-- difficulty-rule:difficult_title_only_keywords -->
`多级复核`
<!-- /difficulty-rule -->

### 困难组合关键字

> 匹配字段：`用例名称` + `用例步骤` 合并后同时命中组合。不读取预期结果。

<!-- difficulty-rule:difficult_keyword_combinations -->
- `分析模版` + `执行分析`
- `回顾计划` + `自动分解`
- `数据复核` + `多级`
<!-- /difficulty-rule -->

---

## 简单优先关键字（命中可短路判"简单"，需满足步骤/校验点数量限制）

### 单字段提示类

> 适用条件：前置 ≤3 条、步骤 ≤3 步、校验点 ≤3 个，不得命中复杂度信号。

<!-- difficulty-rule:simple_field_validation_keywords -->
`必填`
`格式`
`长度`
`唯一性`
`数据类型`
`单位`
`范围`
`规格上限`
`规格下限`
<!-- /difficulty-rule -->

### 基础配置项和字段级操作

> 适用条件：前置 ≤4 条、步骤 ≤4 步、校验点 ≤3 个，不得命中复杂度信号。

<!-- difficulty-rule:simple_operation_keywords -->
`下拉框`
`单选`
`复选`
`切换`
`添加`
`删除`
`保存`
`取消`
`查询`
`重置`
`重命名`
`启用`
`停用`
<!-- /difficulty-rule -->

### 导入文件级基础校验

> 适用条件：前置 ≤3 条、步骤 ≤3 步、校验点 ≤3 个，不得涉及错误报告明细/落库/回滚。

<!-- difficulty-rule:simple_import_file_validation_keywords -->
`导入`
`文件类型`
`文件大小`
`空文件`
`表头`
`合并单元格`
`加密`
`损坏`
`无数据`
<!-- /difficulty-rule -->

### 导入模板下载

> 适用条件：前置 ≤3 条、步骤 ≤3 步、校验点 ≤4 个，不得涉及字段逐项说明/下拉选项。

<!-- difficulty-rule:simple_import_template_download_keywords -->
`模板下载`
`下载模板`
`模板文件`
`导入模板`
<!-- /difficulty-rule -->

---

## 复杂度信号（命中加 1 分，不按数量叠加）

### 复杂度单关键字

> 非 UI 用例匹配：`用例名称`、`用例描述`、`前置条件`、`用例步骤`、`预期结果`。
> UI 用例只匹配：`用例名称`、`用例步骤`、`预期结果`。

<!-- difficulty-rule:complexity_keywords -->
`跨模块`
`审批`
`复核`
`确认`
`提交`
`退回`
`生效`
`统计计算`
`关联引用`
`异步任务`
`批处理`
`定时任务`
<!-- /difficulty-rule -->

### 复杂度组合关键字

> 匹配字段：`用例名称` + `用例步骤` 合并后命中组合。不读取预期结果。

<!-- difficulty-rule:complexity_keyword_combinations -->
- `分析模版` + `数据源`
- `报告模版` + `章节`
- `回顾计划` + `周期`
- `任务` + `自动分解`
- `数据复核` + `状态`
- `分析结果` + `引用`
<!-- /difficulty-rule -->
