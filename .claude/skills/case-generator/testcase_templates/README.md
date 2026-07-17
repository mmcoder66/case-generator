# 用例模板库说明

## 目录用途

本目录用于保存通用用例模板和各菜单模块的参考用例。生成新用例时，应按需参考命中的模块用例或通用模板，但不要修改本目录内容。

## 模块目录结构

`modules/` 按站点分类和一级菜单组织，参考文件维护在一级菜单目录下，统一以 `_template.md` 作为公共后缀。二级菜单未拆分或本身已足够精确时用 `<level2_menu>_template.md`，同一二级菜单下按需求或子功能拆分时用 `<level2_menu>_<requirement_or_submodule>_template.md`。目录名和文件名必须全部小写，不带空格，以 `_` 分隔单词：

```text
modules/
├── menu_index.md                   # 菜单路径到参考文件的索引
└── <site_type>/
    └── <level1_menu>/
        ├── <level2_menu>_template.md
        └── <level2_menu>_<requirement_or_submodule>_template.md
                                      # 二级菜单参考用例，或二级菜单 + 需求名称/子功能模块参考用例
```

> `<site_type>` 取自 `business_constants.SITE_TYPES`，新项目按实际站点分类建立对应子目录。

具体参考文件匹配规则见 `modules/menu_index.md`。

## 维护原则

- 通用模板只描述字段结构和编写方法。
- `modules/` 下的参考用例只读维护，每个 `<site_type>/` 下只保留一级菜单目录。
- 新增、移动或重命名参考用例文件时，必须同步更新 `modules/menu_index.md`。
- 新生成或补充的用例必须保存到 `outputs/origin_exports/<site_type>/<module_name>_testcases.md`，其中 `site_type` 必须是 `business_constants.SITE_TYPES` 中声明的值之一。
- 不允许把多个模块的新用例混写到一个输出文件中。
- 生成前必须检查参考用例，避免重复场景。

## 默认字段

| 一级分组 | 二级分组 | 三级分组 | 用例名称 | 优先级 | 创建人 | 用例描述 | 前置条件 | 用例步骤 | 预期结果 | 备注 | 用例标签 |
|---|---|---|---|---|---|---|---|---|---|---|---|

> 若 `business_constants.CPV_SPECIFIC_HEADERS` 声明了追踪字段，会自动拼接到 `用例标签` 列后。

如参考用例需要表达更细业务层级，可在 `三级分组` 后、`用例名称` 前连续增加 `四级分组`、`五级分组` 等分组列；`一级分组` 必填，其他分组按实际节点填写，没有对应节点时留空。

`备注` 用于记录新生成用例的具体来源，写法以 `generation_rules/testcase_writing_guidelines.md` 的"备注、标签和关联字段"为准。

若 `business_constants.CPV_SPECIFIC_HEADERS` 声明了追踪字段，新生成或追加用例的对应字段值必须留空。

## 用例描述建议值

- 正例
- 反例
- 边界
- 权限
- UI
- 回归
- 兼容
- 联动
