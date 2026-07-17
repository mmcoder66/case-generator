#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""业务常量集中定义（骨架版本）。

换项目时，本文件是要替换的核心入口——所有业务关键字、站点分类、
表头字段约定、Excel 导出品牌都集中在这里。

换项目检查清单：
    1. CPV_SPECIFIC_HEADERS —— 改成新项目的追踪字段（表头尾部列）
    2. SITE_TYPES —— 改成新项目的站点分类
    3. SHEET_NAME / CREATOR_NAME —— 改 Excel 品牌
    4. COLUMN_WIDTH_BY_HEADER —— 按新表头字段调整列宽
    5. CORE_FLOW_KEYWORDS —— 替换成新项目的核心业务模块词表（或置空）
    6. ENABLED_BUSINESS_RULES —— 按保留的业务规则开关
"""
import re

# ===== 表头字段（团队约定，非测试行业通用）=====
# 测试行业通用的 9 列（用例名称/优先级/...）已在 case_utils._GENERIC_FIXED_HEADERS；
# 这里放项目专属的追踪字段，会拼接到通用列后。
CPV_SPECIFIC_HEADERS: list[str] = []  # TODO: 填入新项目专属字段，如 ["是否自动化", "关联接口", ...]

# ===== 站点分类 =====
# outputs/origin_exports 下的一级子目录名；只一个站点时保留单元素 tuple。
SITE_TYPES: tuple[str, ...] = ("default_site",)  # TODO: 改成新项目的站点分类

# ===== Excel 导出品牌 =====
SHEET_NAME = "测试用例"
CREATOR_NAME = "测试用例生成器"  # TODO: 改成新项目品牌

COLUMN_WIDTH_BY_HEADER = {
    "一级分组": 16, "二级分组": 16, "三级分组": 16,
    "用例名称": 36, "优先级": 10, "创建人": 12, "用例描述": 16,
    "前置条件": 36, "用例步骤": 48, "预期结果": 52,
    "备注": 24, "用例标签": 18,
    # TODO: 为 CPV_SPECIFIC_HEADERS 中每个字段补列宽
}

# ===== 核心链路覆盖（业务模块词表）=====
# 留空：新项目填入后，配合 validate_core_flow_coverage 校验使用。
CORE_FLOW_KEYWORDS: dict[str, list[list[str]]] = {}  # TODO: 填入新项目核心模块词表

# ===== 业务校验插件开关 =====
MAX_GROUP_DEPTH = 5  # 分组深度上限

ENABLED_BUSINESS_RULES: tuple[str, ...] = (
    "group_depth_limit",  # 默认只启用分组深度上限（通用约束）
    # TODO: 启用 core_flow_coverage 等业务规则
)
