# CPV 难度关键字配置

> 本文件由 `case_utils.py` 的 `_load_difficulty_rule_config()` 自动加载。
> 框架规则（评分表、判定顺序、字段匹配口径）见 `generation_rules/difficulty_level_rules.md`。

---

## 误命中排除词

> 在匹配业务关键字前先从文本中移除这些词，避免"错误报告""失败报告"等 CPV 一键分析产物文件名误命中报告生成链路。

<!-- difficulty-rule:report_lifecycle_exclusions -->
`txt错误报告`
`错误报告`
`失败报告`
<!-- /difficulty-rule -->

---

## 困难强规则（命中即判"困难"，不进入综合评分）

### 高置信困难强规则关键字

> 匹配字段：`用例名称`、`用例步骤`、`预期结果`。命中任一直接判"困难"。

<!-- difficulty-rule:difficult_high_confidence_keywords -->
`数据迁移`
`跨环境`
`第三方`
`minitab`
<!-- /difficulty-rule -->

### 仅用例名称困难强规则关键字

> 匹配字段：仅 `用例名称`。出现在预期结果中不抬高难度。

<!-- difficulty-rule:difficult_title_only_keywords -->
`超出参考线检查`
`过程数据正确`
<!-- /difficulty-rule -->

### 困难组合关键字

> 匹配字段：`用例名称` + `用例步骤` 合并后同时命中组合。不读取预期结果。

<!-- difficulty-rule:difficult_keyword_combinations -->
- `导入` + `跨环境`
- `导入` + `接口越权`
- `导入` + `权限生效`
- `报告` + `分析结果`
- `分析成功` + `结果`
- `未分析` + `一键分析`
- `一键分析` + `异常提示`
- `一键分析` + `优先`
- `判异检查` + `正确性`
<!-- /difficulty-rule -->

---

## 简单优先关键字（命中可短路判"简单"，需满足步骤/校验点数量限制）

### 单字段提示类

> 适用条件：前置 ≤3 条、步骤 ≤3 步、校验点 ≤3 个，不得命中复杂度信号。

<!-- difficulty-rule:simple_field_validation_keywords -->
`单字段校验`
`必填`
`格式提示`
`长度`
<!-- /difficulty-rule -->

### 基础配置项和字段级操作

> 适用条件：前置 ≤4 条、步骤 ≤4 步、校验点 ≤3 个，不得命中复杂度信号。

<!-- difficulty-rule:simple_operation_keywords -->
`变量区域`
`放入横轴变量`
`子组大小`
`横轴旋转角度`
`新增参考线`
`下拉框`
`输入框`
`默认值`
`拖拽失败`
`添加失败`
`删除变量`
`删除纵轴变量`
`第二个定量变量`
`纵轴范围`
`参考线数据范围`
`阻止添加`
`只读`
<!-- /difficulty-rule -->

### 导入文件级基础校验

> 适用条件：前置 ≤3 条、步骤 ≤3 步、校验点 ≤3 个，不得涉及错误报告明细/落库/回滚。

<!-- difficulty-rule:simple_import_file_validation_keywords -->
`非excel文件`
`文件超过`
`空文件`
`有表头无数据`
`有数据无表头`
`表头不匹配`
`合并单元格`
`加密文件`
`文件损坏`
`已删除`
<!-- /difficulty-rule -->

### 导入模板下载

> 适用条件：前置 ≤3 条、步骤 ≤3 步、校验点 ≤4 个，不得涉及字段逐项说明/下拉选项。

<!-- difficulty-rule:simple_import_template_download_keywords -->
`导入模板`
`模板下载`
`下载模板`
`下载模版`
<!-- /difficulty-rule -->

---

## 复杂度信号（命中加 1 分，不按数量叠加）

### 复杂度单关键字

> 非 UI 用例匹配：`用例名称`、`用例描述`、`前置条件`、`用例步骤`、`预期结果`。
> UI 用例只匹配：`用例名称`、`用例步骤`、`预期结果`。

<!-- difficulty-rule:complexity_keywords -->
`导入`
`批量导出`
`跨页面`
`跨模块`
`审计追踪详情`
`批量删除`
`组合搜索`
`组合查询`
`联动`
`数据一致性`
`报告`
`工作流`
`会签`
`多角色`
`一键分析`
`越权`
`参考线异常点`
<!-- /difficulty-rule -->

### 复杂度组合关键字

> 匹配字段：`用例名称` + `用例步骤` 合并后命中组合。不读取预期结果。

<!-- difficulty-rule:complexity_keyword_combinations -->
- `报告` + `生成`
- `报告` + `导出`
- `操作历史` + `详情`
- `操作历史` + `记录`
<!-- /difficulty-rule -->
