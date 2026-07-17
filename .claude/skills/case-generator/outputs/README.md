# 输出结果说明

## 目录用途

本目录用于保存测试用例生成后的原始文件和导出文件。

## 目录结构

```
outputs/
├── origin_exports/      # 原始测试用例文件（Markdown 格式）
│   └── <site_type>/     # 按 business_constants.SITE_TYPES 分类
│       └── <module_name>_testcases.md
└── excel_exports/       # Excel 导出文件
    └── <site_type>/
        └── <module_name>_testcases.xlsx
```

> 新项目按 `business_constants.SITE_TYPES` 在 `origin_exports/` 和 `excel_exports/` 下建立对应站点子目录。骨架项目默认只有 `default_site` 一个占位站点；不需要在本仓库内预创建站点子目录，脚本会在导出时按需创建。

## 保存规则

- 原始测试用例按站点分类保存到 `origin_exports/<site_type>/`，文件命名格式：`<module_name>_testcases.md`
- 分需求 Excel 导出文件按站点分类保存到 `excel_exports/<site_type>/`，文件命名格式：`<module_name>_testcases.xlsx`
- 不带 `--source` 或传入目录批量导出时，脚本会生成 `测试用例导出_YYYYMMDD_HHMMSS.xlsx` 汇总文件；该文件仅用于临时汇总，不作为默认交付格式
- `export_testcases.py --clean` 仅清理 `测试用例导出_*.xlsx` 临时汇总文件，不删除 `<module_name>_testcases.xlsx` 分需求交付文件
- `testcase_templates/` 仅作为参考模板，不保存新生成的用例
- 生成模式下，新增或补充的 Markdown 用例只写入 `origin_exports/<site_type>/`

## 站点分类

站点分类由 `business_constants.SITE_TYPES` 决定。骨架项目默认值：

| 站点分类 | Markdown 保存目录 | Excel 保存目录 | 适用范围 |
|---|---|---|---|
| `default_site` | `origin_exports/default_site/` | `excel_exports/default_site/` | <TODO: 新项目按业务实际拆分站点后调整> |

## 用例追踪规则

- 输出表头不包含独立用例编号字段
- 用例追踪和去重使用当前表头中的完整分组路径 + `用例名称`；`一级分组` 必填，`二级分组`、`三级分组` 及后续分组没有对应节点时可留空
- 同一输出文件的同一分组下 `用例名称` 不允许重复；不同需求拆分到不同 Markdown 文件时，允许复用通用场景名称
