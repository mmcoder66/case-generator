#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CPV 项目专属业务校验规则注册。

本文件由通用 ``validate_cases.py`` 在运行时动态导入（通过 ``--project cpv`` 触发）。
``register_business_rules()`` 返回的规则会合并到 ``_BUSINESS_RULE_REGISTRY``。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from business_constants import (
    ONE_CLICK_REPAIR_INVALID_STATE_RE,
    ONE_CLICK_REPAIR_FIELD_RE,
    ONE_CLICK_REPAIR_FIELD_PRESERVED_RE,
    ONE_CLICK_FIELD_CLEARED_MARKERS,
    ONE_CLICK_REASON_STRIP_RE,
    ONE_CLICK_METHOD_RE,
)

# 从通用 validate_cases 导入共享类型和工具
from validate_cases import Issue, case_issue, case_group, case_text, normalize_cell, group_path_contains


def extract_one_click_reason(name: str) -> str:
    """从一键分析用例名称中提取原因核心（去除结构性词汇和方法名称）。"""
    stripped = ONE_CLICK_REASON_STRIP_RE.sub("", name)
    stripped = ONE_CLICK_METHOD_RE.sub("", stripped)
    return stripped.strip()


def validate_data_analysis_one_click_rules(cases: list[dict[str, str]]) -> list[Issue]:
    """校验数据分析一键分析专项规则中容易漏掉或误判的语义场景。"""
    issues: list[Issue] = []
    cases_by_file: dict[str, list[dict[str, str]]] = {}
    for case in cases:
        cases_by_file.setdefault(case.get("_source_file", ""), []).append(case)

    for case in cases:
        group = case_group(case)
        name = normalize_cell(case.get("用例名称", ""))
        if "一键分析" not in group and "一键分析" not in name:
            continue

        text = case_text(case)
        if "修复后" in name and "成功" in name and "一键分析成功" not in name:
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "one_click_repair_name_missing_success",
                    "一键分析修复成功类用例名称必须明确包含'一键分析成功'，不得只写'修复后成功'",
                    "用例名称",
                )
            )

        is_repair_success = "修复后" in name and "一键分析成功" in name
        invalid_field_state = ONE_CLICK_REPAIR_INVALID_STATE_RE.search(text)
        affected_field = ONE_CLICK_REPAIR_FIELD_RE.search(text)
        field_preserved = ONE_CLICK_REPAIR_FIELD_PRESERVED_RE.search(text)
        if is_repair_success and invalid_field_state and affected_field and not field_preserved:
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "one_click_invalid_cleared_field_repair",
                    "字段删减、字段缺失、字段未匹配、匹配上定类变量或变量已清空时，不能生成一键分析修复成功用例；应改为未分析/需手动配置类用例",
                    "用例名称",
                )
            )

    for source_file, file_cases in cases_by_file.items():
        one_click_cases = [
            case
            for case in file_cases
            if "一键分析" in case_group(case)
            or "一键分析" in normalize_cell(case.get("用例名称", ""))
        ]
        if not one_click_cases:
            continue

        file_text = "\n".join(case_text(case) for case in file_cases)

        if (
            "字段删减" in file_text
            and "控制图" in file_text
            and not any("字段删减" in case_group(case) for case in one_click_cases)
        ):
            issues.append(
                Issue(
                    severity="ERROR",
                    code="one_click_missing_field_deletion_case",
                    message='控制图一键分析已出现字段删减风险，但缺少分组路径包含"字段删减"的独立用例',
                    file=source_file,
                )
            )

        field_retained_failures: list[str] = []
        for case in one_click_cases:
            name = normalize_cell(case.get("用例名称", ""))
            if "未分析" not in name:
                continue
            if "一键分析成功" in name:
                continue
            if any(marker in name for marker in ONE_CLICK_FIELD_CLEARED_MARKERS):
                continue
            field_retained_failures.append(name)

        if field_retained_failures:
            repair_success_names = [
                normalize_cell(case.get("用例名称", ""))
                for case in one_click_cases
                if "一键分析成功" in normalize_cell(case.get("用例名称", ""))
            ]
            if not repair_success_names:
                issues.append(
                    Issue(
                        severity="ERROR",
                        code="one_click_missing_field_retained_repair",
                        message=(
                            f"存在 {len(field_retained_failures)} 条字段保留类的未分析用例，"
                            "但缺少任何'一键分析成功'修复用例；"
                            "按未分析项修复判定，字段保留但值不满足约束时应生成修复后一键分析成功用例"
                        ),
                        file=source_file,
                    )
                )
            else:
                for failure_name in field_retained_failures:
                    reason_core = extract_one_click_reason(failure_name)
                    if len(reason_core) < 2:
                        continue
                    matched = any(
                        reason_core in repair_name
                        for repair_name in repair_success_names
                    )
                    if not matched:
                        issues.append(
                            Issue(
                                severity="WARN",
                                code="one_click_missing_field_retained_repair",
                                message=(
                                    f"存在字段保留类的未分析用例（{failure_name}），"
                                    f"但未匹配到原因核心'{reason_core}'对应的'一键分析成功'修复用例；"
                                    "按未分析项修复判定应成对生成修复后一键分析成功用例"
                                ),
                                file=source_file,
                            )
                        )

    return issues


def register_business_rules() -> dict[str, Any]:
    """注册 CPV 专属业务校验规则。"""
    return {
        "data_analysis_one_click": validate_data_analysis_one_click_rules,
    }
