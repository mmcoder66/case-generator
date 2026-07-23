#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用途：
    校验 Markdown 测试用例表格是否符合本项目的固定格式和质量规则。
    这是生成用例后、导出 Excel 前的质量门禁。

默认读取：
    outputs/origin_exports/**/*_testcases.md

适用场景：
    - 校验 Agent 新生成的输出用例。
    - 导出 Excel 前确认字段、优先级、用例描述和追踪信息可用。
    - 通过 --source 显式校验某个文件或参考用例目录。
    - 通过 --fix 自动修复 outputs/origin_exports/ 下的 Markdown 表格格式，不修改业务语义。
    - 通过 --json 输出结构化结果，便于 Agent 根据问题明细修复用例。

校验内容：
    - 是否存在标准测试用例表格
    - 字段是否完整
    - 优先级是否只使用 P0、P1、P2
    - 生成用例的备注是否写明来源
    - 生成用例的追踪字段（PROJECT_SPECIFIC_HEADERS 声明的列）是否留空
    - 测试场景是否重复
    - 操作步骤和预期结果是否过于空泛
    - 用例步骤和预期结果是否包含“按...规则”等抽象不可验证表达
    - 备注和元信息是否错误引用 outputs 下已生成用例作为来源
    - UI 图来源与 UI 用例是否一致
    - 展示类用例是否误标为正例、同一区域 UI 展示用例是否疑似重复拆分

结果规则：
    - ERROR 表示必须修复，脚本退出码为 1。
    - WARN 表示建议修复，默认不阻断脚本成功退出。

示例：
    python scripts/validate_cases.py
    python scripts/validate_cases.py --source outputs/origin_exports/<module_name>_testcases.md
    python scripts/validate_cases.py --fix
    python scripts/validate_cases.py --json
    python scripts/validate_cases.py --source testcase_templates/modules

改动本文件后，请运行 `python -m pytest scripts/tests/ -v` 确认无回归。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from business_constants import (
    PROJECT_SPECIFIC_HEADERS,
    CORE_FLOW_KEYWORDS,
    ENABLED_BUSINESS_RULES,
    MAX_GROUP_DEPTH,
    ALL_VALID_TAGS,
    CHANGE_TAGS,
)
from case_utils import (
    DIFFICULTY_LEVELS,
    EXPECTED_HEADERS,
    GROUP_HEADER_LEVELS,
    GROUP_HEADERS_BY_LEVEL,
    VALID_PRIORITIES,
    build_source_path,
    configure_output_encoding,
    discover_case_files,
    ensure_under,
    expected_headers_for,
    group_headers_from_case,
    group_headers_from_headers,
    infer_case_difficulty_with_reason,
    is_case_header,
    is_separator_row,
    normalize_cell,
    parse_case_file,
    parse_coverage_tables,
    project_root,
    read_text_file,
    required_headers_for,
    split_case_tags,
    split_markdown_row,
    write_text_file,
)


VAGUE_EXPECTATION_PATTERNS = [
    re.compile(r"^页面展示正常[。.]?$"),
    re.compile(r"^功能可用[。.]?$"),
    re.compile(r"^结果正确[。.]?$"),
    re.compile(r"^按需求展示[。.]?$"),
    re.compile(r"^显示正确[。.]?$"),
    re.compile(r"^展示成功[。.]?$"),
    re.compile(r"^操作成功[。.]?$"),
    re.compile(r"^操作完成[。.]?$"),
    re.compile(r"^符合预期[。.]?$"),
    re.compile(r"^正常显示[。.]?$"),
    re.compile(r"^展示正确[。.]?$"),
    re.compile(r"^正常展示[。.]?$"),
    re.compile(r"^页面正常[。.]?$"),
    re.compile(r"^成功[。.]?$"),
    re.compile(r"^通过[。.]?$"),
]

FORBIDDEN_ABSTRACT_PATTERNS = [
    (re.compile(r"按[^。；;\n]*规则"), "按...规则"),
    (re.compile(r"根据[^。；;\n]*规则"), "根据...规则"),
    (re.compile(r"符合[^。；;\n]*规则"), "符合...规则"),
    (re.compile(r"按需求"), "按需求"),
    (re.compile(r"对照\s*PRD", re.IGNORECASE), "对照 PRD"),
    (re.compile(r"检查是否符合"), "检查是否符合"),
]

WEAK_EXPECTATION_PHRASE_RE = re.compile(
    r"(显示正确|展示正确|展示完整|内容正确|数据正确|结果正确|页面正确)"
)
CONCRETE_EXPECTATION_CONTEXT_RE = re.compile(
    r"(<br|\n|[、；;：:]|包含|提示|更新为|变为|不可|不生成|为空|"
    r"回显|置灰|字段|列表|按钮|弹窗|页签|标签|默认值|展示|显示|"
    r"名称|数值|文件|图表|状态)"
)

OUTPUT_REFERENCE_RE = re.compile(r"(?:^|[\\/])outputs[\\/]|outputs[\\/]|_testcases\.md", re.IGNORECASE)

UI_DISPLAY_SIGNAL_RE = re.compile(
    r"(UI|页面|区域|布局|元素|按钮|文案|说明|标题|字段|列|列表|卡片|"
    r"弹窗|页签|标签|默认值|展示|显示|回显|置灰)"
)
UI_DISPLAY_TITLE_RE = re.compile(
    r"(UI校验|基础元素显示|元素显示|按钮展示|文案展示|布局展示|"
    r"页面展示|区域展示|整体展示)"
)
BUSINESS_RESULT_SIGNAL_RE = re.compile(
    r"(保存|提交|新增|编辑|删除|导入|导出|下载|上传|生成|创建|更新|"
    r"推送|写入|生效|审批|确认|发布|退回|关闭|拦截|阻止|失败|成功|"
    r"状态|记录|审计|计算|校验通过|校验失败|提示“|提示\")"
)
UI_REGION_SUFFIX_RE = re.compile(
    r"(基础元素显示|元素显示|按钮展示|文案展示|布局展示|页面展示|区域展示|"
    r"整体展示|UI校验|显示|展示|校验)$"
)

# 预期结果建议的最少字符数，过短通常说明缺少可验证的页面/数据/业务状态描述
MIN_EXPECTATION_LENGTH = 10

# 前置条件、用例步骤、预期结果单句/单步建议的最大字符数，超过建议拆分为多个编号
MAX_SENTENCE_LENGTH = 50

INVALID_SOURCE_REMARKS = {"", "无", "待填", "来源：待填"}
INVALID_SOURCE_ATTRIBUTION_PATTERNS = [
    (
        re.compile(r"来源：[^；;\n]*?(?:未明确|需要确认|需确认|待确认)"),
        "备注中的“来源：”后只能填写真实来源，不能填写“未明确/需确认”等说明；"
        "请改为“来源：<规则或资料>；说明：需求文档未明确需要确认”",
    ),
    (
        re.compile(r"来源：[^；;\n]*?需求文档"),
        "PRD 来源备注必须写为“来源：prd”，不得写为“来源：需求文档”",
    ),
    (
        re.compile(r"来源：[^；;\n]*?UI设计图"),
        "UI 图来源备注必须写为“来源：UI图”，不得写为“来源：UI设计图”",
    ),
]
EMPTY_GENERATED_HEADERS = PROJECT_SPECIFIC_HEADERS

# 生成耗时占位词：交付前必须按实际耗时回填
DURATION_PLACEHOLDER_RE = re.compile(r"生成耗时：(?:待回填|约|预计)")

# 生成时间：提取行内容并校验格式必须为 YYYY-MM-DD HH:MM:SS（精确到秒）
GENERATED_TIME_LINE_RE = re.compile(r"生成时间：([^\n\r]+)")
GENERATED_TIME_FORMAT_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

# 元信息块提取正则：用于覆盖率校验中定位来源 docx 和来源章节
SOURCE_DOC_RE = re.compile(r"来源文档：\s*(.+)")
SOURCE_SECTION_RE = re.compile(r"来源章节：\s*(.+)")

# PRD 表格行文本前缀（与 extract_docx._table_lines 输出保持一致）
PRD_TABLE_ROW_PREFIX = "表格行"
# PRD 状态对照表识别：表头同时含"状态"和"操作"
PRD_STATE_TABLE_HEADER_HINTS = ("状态", "操作")
# PRD 字段定义表识别：表头同时含"字段名称"和"必填"
PRD_FIELD_TABLE_HEADER_HINTS = ("字段名称", "必填")

# PRD 顶级章节编号（汉字数字+顿号），用于切分章节内的子项
PRD_TOP_LEVEL_CHAPTER_RE = re.compile(r"[一二三四五六七八九十]+、")
# PRD 子项编号（数字+.、)、)），用于切分子项
PRD_SUB_ITEM_NUMBER_RE = re.compile(r"[0-9]+[.、）)]")
# 子项标题截断符：标题在遇到这些标点前都视为关键字一部分
PRD_SUB_ITEM_TITLE_BOUNDARY_RE = re.compile(r"[，。：；,;:]")
# 子项关键字最大长度
PRD_SUB_ITEM_KEYWORD_MAX_LENGTH = 10


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    file: str = ""
    line: int | None = None
    case_name: str = ""
    field: str = ""


def case_location(case: dict[str, str]) -> str:
    return f"{case['_source_file']} 第 {case['_source_line']} 行"


def case_group(case: dict[str, str]) -> str:
    groups = [case.get(header, "") for header in group_headers_from_case(case)]
    return " / ".join(group for group in groups if group) or "未分组"


def case_text(case: dict[str, str]) -> str:
    return "\n".join(
        normalize_cell(case.get(field, ""))
        for field in [
            *group_headers_from_case(case),
            "用例名称",
            "前置条件",
            "用例步骤",
            "预期结果",
            "备注",
        ]
    )


def case_issue(
    case: dict[str, str],
    severity: str,
    code: str,
    message: str,
    field: str = "",
) -> Issue:
    source_line = case.get("_source_line", "")
    return Issue(
        severity=severity,
        code=code,
        message=message,
        file=case.get("_source_file", ""),
        line=int(source_line) if source_line.isdigit() else None,
        case_name=case.get("用例名称", ""),
        field=field,
    )


def text_issue(severity: str, code: str, message: str) -> Issue:
    return Issue(severity=severity, code=code, message=message)


def format_issue(issue: Issue) -> str:
    location = ""
    if issue.file and issue.line is not None:
        location = f"{issue.file} 第 {issue.line} 行 "
    elif issue.file:
        location = f"{issue.file} "

    field = f" [{issue.field}]" if issue.field else ""
    case_name = f" ({issue.case_name})" if issue.case_name else ""
    return f"[{issue.severity}] {issue.code}: {location}{issue.message}{field}{case_name}"


def has_blocking_issues(issues: list[Issue], strict: bool = False) -> bool:
    # strict=True 时 WARN 也视为阻塞；将来若新增 INFO 等级别，此处不会误判。
    return any(
        issue.severity == "ERROR" or (strict and issue.severity == "WARN")
        for issue in issues
    )


def run_all_validations(
    case_files: list[Path],
    cases: list[dict[str, str]],
    parse_warnings: list[str] | None = None,
) -> list[Issue]:
    """运行完整校验规则集，返回所有 Issue。

    校验链分两组：
    - **通用校验**（表头、优先级、重复、分组相邻、元信息等）永远运行，与业务无关。
    - **业务校验**通过 ``business_constants.ENABLED_BUSINESS_RULES`` 开关按需加载，
      换项目时可整体关闭或替换为新的业务规则（注册表见模块末尾 ``_BUSINESS_RULE_REGISTRY``）。
    """
    issues: list[Issue] = []
    if parse_warnings:
        issues.extend(
            text_issue("ERROR", "parse_error", warning) for warning in parse_warnings
        )
    # 通用校验链：与业务无关，任何项目都需要
    issues.extend(validate_case_rows(cases))
    issues.extend(validate_group_priority_order(cases))
    issues.extend(validate_ui_case_deduplication(cases))
    issues.extend(validate_file_sources(case_files, cases))
    issues.extend(validate_duplicates(cases))
    issues.extend(validate_group_adjacency(cases))
    issues.extend(validate_group_depth_consistency(cases))
    issues.extend(validate_duration_metadata(case_files))
    issues.extend(validate_coverage_references(case_files, cases))
    issues.extend(validate_hard_coverage(case_files, cases))
    # 业务校验链：按 business_constants.ENABLED_BUSINESS_RULES 开关加载
    for rule_name in ENABLED_BUSINESS_RULES:
        validator = _BUSINESS_RULE_REGISTRY.get(rule_name)
        if validator is not None:
            issues.extend(validator(cases))
    return issues


def escape_markdown_cell(value: str) -> str:
    value = value.strip().replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = value.replace("\\", "\\\\")
    value = value.replace("|", r"\|")
    value = value.replace("\n", "<br>")
    return value


def markdown_row(values: list[str]) -> str:
    return "| " + " | ".join(escape_markdown_cell(value) for value in values) + " |"


def markdown_separator(headers: list[str] | None = None) -> str:
    headers = headers or EXPECTED_HEADERS
    return "| " + " | ".join("---" for _ in headers) + " |"


def fix_case_file(path: Path) -> dict[str, object]:
    # 统一以无 BOM 的 utf-8 读写，去除 BOM 是有意为之，保证后续处理的一致性。
    original_text = read_text_file(path, encoding="utf-8-sig")
    lines = original_text.splitlines()
    updated_lines: list[str] = []
    changed_rows = 0
    fixed_headers = 0
    fixed_separators = 0
    removed_blank_lines = 0

    index = 0
    while index < len(lines):
        cells = [normalize_cell(cell) for cell in split_markdown_row(lines[index])]
        is_known_header = is_case_header(cells)

        if not is_known_header:
            updated_lines.append(lines[index].rstrip())
            index += 1
            continue

        headers = expected_headers_for(group_headers_from_headers(cells))
        canonical_header = markdown_row(headers)
        if lines[index].rstrip() != canonical_header:
            fixed_headers += 1
        updated_lines.append(canonical_header)
        index += 1

        if index < len(lines) and is_separator_row(split_markdown_row(lines[index])):
            if lines[index].rstrip() != markdown_separator(headers):
                fixed_separators += 1
            index += 1
        else:
            fixed_separators += 1
        updated_lines.append(markdown_separator(headers))

        while index < len(lines) and lines[index].strip().startswith("|"):
            row_cells = split_markdown_row(lines[index])
            if is_separator_row(row_cells):
                fixed_separators += 1
                index += 1
                continue

            normalized_cells = [normalize_cell(cell) for cell in row_cells]
            if len(normalized_cells) == len(cells):
                row_by_header = dict(zip(cells, normalized_cells))
                fixed_row = markdown_row(
                    [row_by_header.get(header, "") for header in headers]
                )
                if lines[index].rstrip() != fixed_row:
                    changed_rows += 1
                updated_lines.append(fixed_row)
            else:
                updated_lines.append(lines[index].rstrip())
            index += 1

    compact_lines: list[str] = []
    previous_blank = False
    for line in updated_lines:
        is_blank = not line.strip()
        if is_blank and previous_blank:
            removed_blank_lines += 1
            continue
        compact_lines.append("" if is_blank else line)
        previous_blank = is_blank

    updated_text = "\n".join(compact_lines).rstrip() + "\n"
    changed = updated_text != original_text
    if changed:
        write_text_file(path, updated_text, encoding="utf-8")

    return {
        "file": str(path),
        "changed": changed,
        "fixed_headers": fixed_headers,
        "fixed_separators": fixed_separators,
        "changed_rows": changed_rows,
        "removed_blank_lines": removed_blank_lines,
    }


def fix_case_files(case_files: list[Path]) -> list[dict[str, object]]:
    return [fix_case_file(case_file) for case_file in case_files]


def duplicate_values(
    cases: list[dict[str, str]], key_func
) -> dict[tuple[str, ...], list[dict[str, str]]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for case in cases:
        key = key_func(case)
        if any(not value for value in key):
            continue
        grouped.setdefault(key, []).append(case)
    return {key: value for key, value in grouped.items() if len(value) > 1}


def is_vague_expectation(value: str) -> bool:
    normalized = "".join(value.split())
    return any(pattern.match(normalized) for pattern in VAGUE_EXPECTATION_PATTERNS)


def is_too_short_expectation(value: str) -> bool:
    return len("".join(value.split())) < MIN_EXPECTATION_LENGTH


def split_into_sentences(value: str) -> list[str]:
    """按 <br>、换行或编号点（1. 2. 3.）拆分为独立句子。

    用于前置条件、用例步骤、预期结果的"单句/单步"字数检查。
    编号点格式包括 `1. `、`1、`，可写在同行或跨行。
    """
    if not value:
        return []
    # 先按 <br> 或换行拆分
    parts = re.split(r"<br\s*/?>|\n", value)
    # 再按行内编号点拆分（如 "1. xxx 2. yyy" 写在一行）
    sentences: list[str] = []
    for part in parts:
        sub_parts = re.split(r"(?:^|\s)\d+[.、]\s*", part)
        sentences.extend(p.strip() for p in sub_parts if p.strip())
    return sentences


def find_overlong_sentences(value: str) -> list[str]:
    """返回单句字符数超过 MAX_SENTENCE_LENGTH 的子句列表，空时表示合规。"""
    return [s for s in split_into_sentences(value) if len(s) > MAX_SENTENCE_LENGTH]


def requires_source_remark(case: dict[str, str]) -> bool:
    source_file = case.get("_source_file", "")
    if not source_file:
        return False

    try:
        Path(source_file).resolve().relative_to(
            (project_root() / "outputs" / "origin_exports").resolve()
        )
        return True
    except ValueError:
        return False


def has_valid_source_remark(value: str) -> bool:
    normalized = value.strip()
    return normalized not in INVALID_SOURCE_REMARKS and "来源：" in normalized


def invalid_source_attribution_reason(value: str) -> str:
    normalized = value.strip()
    for pattern, message in INVALID_SOURCE_ATTRIBUTION_PATTERNS:
        if pattern.search(normalized):
            return message
    return ""


def first_forbidden_abstract_expression(value: str) -> str:
    normalized = normalize_cell(value)
    for pattern, label in FORBIDDEN_ABSTRACT_PATTERNS:
        if pattern.search(normalized):
            return label
    return ""


def has_weak_contextless_expectation(value: str) -> bool:
    normalized = normalize_cell(value)
    return bool(
        WEAK_EXPECTATION_PHRASE_RE.search(normalized)
        and not CONCRETE_EXPECTATION_CONTEXT_RE.search(normalized)
    )


def is_ui_case(case: dict[str, str]) -> bool:
    return (
        normalize_cell(case.get("用例描述", "")).upper() == "UI"
        or "UI校验" in case.get("用例名称", "")
    )


def is_display_only_candidate(case: dict[str, str]) -> bool:
    name = normalize_cell(case.get("用例名称", ""))
    expectation = normalize_cell(case.get("预期结果", ""))
    display_signal = UI_DISPLAY_TITLE_RE.search(name)
    business_signal = BUSINESS_RESULT_SIGNAL_RE.search(expectation)
    return bool(display_signal and not business_signal)


def ui_region_key(case: dict[str, str]) -> str:
    name = normalize_cell(case.get("用例名称", ""))
    name = name.replace(" ", "")
    name = UI_REGION_SUFFIX_RE.sub("", name)
    name = re.sub(r"[，,；;：:。.\-_/]+", "", name)
    return name


def is_generated_output_path(path: Path) -> bool:
    try:
        path.resolve().relative_to((project_root() / "outputs" / "origin_exports").resolve())
        return True
    except ValueError:
        return False


def file_metadata_block(path: Path) -> str:
    text = read_text_file(path, encoding="utf-8-sig")
    stripped = text.lstrip()
    if stripped.startswith("<!--"):
        end_index = stripped.find("-->")
        if end_index != -1:
            return stripped[: end_index + 3]

    table_index = text.find("| 一级分组 |")
    return text[:table_index] if table_index != -1 else ""


def validate_case_rows(cases: list[dict[str, str]]) -> list[Issue]:
    issues: list[Issue] = []

    for case in cases:
        missing_fields = [
            header
            for header in required_headers_for(group_headers_from_case(case))
            if not case.get(header, "")
        ]
        if missing_fields:
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "missing_fields",
                    f"字段缺失：{', '.join(missing_fields)}",
                )
            )

        priority = case["优先级"]
        if priority and priority not in VALID_PRIORITIES:
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "invalid_priority",
                    f"优先级为 {priority}，应为 P0、P1 或 P2",
                    "优先级",
                )
            )

        steps = case["用例步骤"]
        if steps and not re.search(r"(^|\n|<br\s*/?>)\s*\d+[.、]", steps, re.IGNORECASE):
            issues.append(
                case_issue(
                    case,
                    "WARN",
                    "unordered_steps",
                    "用例步骤建议使用 1. 2. 3. 的有序步骤",
                    "用例步骤",
                )
            )
        forbidden_steps = first_forbidden_abstract_expression(steps)
        if forbidden_steps:
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "abstract_step_expression",
                    f"用例步骤包含不可直接执行的抽象表达：{forbidden_steps}，请改为具体页面、字段或操作对象",
                    "用例步骤",
                )
            )
        overlong_steps = find_overlong_sentences(steps) if steps else []
        if overlong_steps:
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "step_too_long",
                    f"用例步骤单步超过 {MAX_SENTENCE_LENGTH} 字（最长 {len(overlong_steps[0])} 字），建议按业务阶段拆分为多个编号",
                    "用例步骤",
                )
            )

        precondition = case["前置条件"]
        overlong_preconditions = (
            find_overlong_sentences(precondition) if precondition else []
        )
        if overlong_preconditions:
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "precondition_too_long",
                    f"前置条件单条超过 {MAX_SENTENCE_LENGTH} 字（最长 {len(overlong_preconditions[0])} 字），建议按外部依赖类型拆分为多个编号",
                    "前置条件",
                )
            )

        remark = case["备注"]
        if requires_source_remark(case) and not has_valid_source_remark(remark):
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "missing_source_remark",
                    "生成用例的备注必须写明来源，例如 来源：prd、来源：UI图 或 来源：<规则文件>.md",
                    "备注",
                )
            )
        elif requires_source_remark(case):
            invalid_source_reason = invalid_source_attribution_reason(remark)
            if invalid_source_reason:
                issues.append(
                    case_issue(
                        case,
                        "ERROR",
                        "invalid_source_attribution",
                        invalid_source_reason,
                        "备注",
                    )
                )
            if OUTPUT_REFERENCE_RE.search(remark):
                issues.append(
                    case_issue(
                        case,
                        "ERROR",
                        "output_file_used_as_source",
                        "备注不得引用 outputs 下已生成用例或 *_testcases.md 作为来源；参考用例只能来自 testcase_templates 下模板文件",
                        "备注",
                    )
                )

        if requires_source_remark(case):
            filled_empty_headers = [
                header for header in EMPTY_GENERATED_HEADERS if case.get(header, "")
            ]
            if filled_empty_headers:
                issues.append(
                    case_issue(
                        case,
                        "ERROR",
                        "generated_fields_must_be_empty",
                        "生成用例的以下字段必须留空："
                        + "、".join(filled_empty_headers),
                    )
                )

        tags = split_case_tags(case.get("用例标签", ""))
        difficulty_tags = [tag for tag in tags if tag in DIFFICULTY_LEVELS]
        expected_difficulty, difficulty_reasons = infer_case_difficulty_with_reason(case)
        difficulty_reason_text = (
            f"；原因：{'；'.join(difficulty_reasons)}" if difficulty_reasons else ""
        )
        if not difficulty_tags:
            issues.append(
                case_issue(
                    case,
                    "WARN",
                    "missing_difficulty_tag",
                    f"用例标签缺少难度等级，按 difficulty_level_rules.md 推断应为：{expected_difficulty}{difficulty_reason_text}",
                    "用例标签",
                )
            )
        elif expected_difficulty not in difficulty_tags:
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "mismatched_difficulty_tag",
                    f"用例标签中的难度为 {'、'.join(difficulty_tags)}，按 difficulty_level_rules.md 推断应为：{expected_difficulty}{difficulty_reason_text}",
                    "用例标签",
                )
            )
        elif len(difficulty_tags) > 1:
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "multiple_difficulty_tags",
                    f"用例标签中存在多个难度等级：{'、'.join(difficulty_tags)}，仅应保留 {expected_difficulty}{difficulty_reason_text}",
                    "用例标签",
                )
            )

        if ALL_VALID_TAGS:
            unknown_tags = [tag for tag in tags if tag not in ALL_VALID_TAGS]
            if unknown_tags:
                issues.append(
                    case_issue(
                        case,
                        "WARN",
                        "unknown_case_tag",
                        f"用例标签存在非约定值：{'、'.join(unknown_tags)}；"
                        f"只允许难度等级（简单/一般/困难）"
                        + (f"和变更类标记（{'/'.join(CHANGE_TAGS)}）" if CHANGE_TAGS else ""),
                        "用例标签",
                    )
                )

        if not is_ui_case(case) and is_display_only_candidate(case):
            issues.append(
                case_issue(
                    case,
                    "WARN",
                    "ui_case_misclassified",
                    "该用例主要验证页面元素、按钮、文案或布局展示，建议改为 UI 用例并在名称中包含 UI校验；若同一区域已有 UI校验 用例，应合并去重",
                    "用例描述",
                )
            )

        expectation = case["预期结果"]
        forbidden_expectation = first_forbidden_abstract_expression(expectation)
        if forbidden_expectation:
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "abstract_expectation_expression",
                    f"预期结果包含抽象不可验证表达：{forbidden_expectation}，请直接写最终可观察结果",
                    "预期结果",
                )
            )
        if expectation and is_vague_expectation(expectation):
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "vague_expectation",
                    f"预期结果过于空泛：{expectation}",
                    "预期结果",
                )
            )
        elif expectation and has_weak_contextless_expectation(expectation):
            issues.append(
                case_issue(
                    case,
                    "WARN",
                    "weak_expectation_context",
                    f"预期结果包含“显示正确/展示完整”等弱表达，建议列出具体字段、状态、页面元素或数据变化：{expectation}",
                    "预期结果",
                )
            )
        elif expectation and is_too_short_expectation(expectation):
            issues.append(
                case_issue(
                    case,
                    "WARN",
                    "short_expectation",
                    f"预期结果过短，建议补充页面表现、数据状态或业务状态：{expectation}",
                    "预期结果",
                )
            )

        overlong_expectations = (
            find_overlong_sentences(expectation) if expectation else []
        )
        if overlong_expectations:
            issues.append(
                case_issue(
                    case,
                    "ERROR",
                    "expectation_too_long",
                    f"预期结果单句超过 {MAX_SENTENCE_LENGTH} 字（最长 {len(overlong_expectations[0])} 字），建议按验证目标拆分为多个编号",
                    "预期结果",
                )
            )

    return issues


def validate_group_priority_order(cases: list[dict[str, str]]) -> list[Issue]:
    """检查同一分组下用例的优先级是否满足 P0 → P1 → P2 非降序。"""
    priority_order = {"P0": 0, "P1": 1, "P2": 2}

    # 按 (源文件, 完整分组路径) 聚合，跨文件不合并
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for case in cases:
        key = (case.get("_source_file", ""), case_group(case))
        groups.setdefault(key, []).append(case)

    issues: list[Issue] = []
    for (_source_file, group_path), group_cases in groups.items():
        if len(group_cases) < 2:
            continue
        priorities = [case.get("优先级", "") for case in group_cases]
        # 存在非法优先级时由其他规则处理，跳过本检查
        if any(p not in priority_order for p in priorities):
            continue
        values = [priority_order[p] for p in priorities]
        is_non_decreasing = all(
            values[i] <= values[i + 1] for i in range(len(values) - 1)
        )
        if is_non_decreasing:
            continue
        # 找第一条违反非降序的位置作为定位
        violation_idx = next(
            (i for i in range(1, len(values)) if values[i] < values[i - 1]),
            None,
        )
        if violation_idx is None:
            continue
        violation_case = group_cases[violation_idx]
        prev_priority = group_cases[violation_idx - 1].get("优先级", "")
        curr_priority = violation_case.get("优先级", "")
        issues.append(
            case_issue(
                violation_case,
                "ERROR",
                "group_priority_order",
                f"分组 [{group_path}] 内优先级顺序不符合 P0 → P1 → P2，"
                f"当前顺序 {' → '.join(priorities)}，"
                f"{curr_priority} 不应排在 {prev_priority} 之后",
                field="优先级",
            )
        )
    return issues


def validate_ui_case_deduplication(cases: list[dict[str, str]]) -> list[Issue]:
    issues: list[Issue] = []
    ui_cases_by_scope: dict[tuple[str, str, str], list[dict[str, str]]] = {}

    for case in cases:
        key = ui_region_key(case)
        if not key or not is_ui_case(case):
            continue
        ui_cases_by_scope.setdefault(
            (case.get("_source_file", ""), case_group(case), key), []
        ).append(case)

    for case in cases:
        if is_ui_case(case) or not is_display_only_candidate(case):
            continue
        key = ui_region_key(case)
        matched_ui_cases = ui_cases_by_scope.get(
            (case.get("_source_file", ""), case_group(case), key), []
        )
        if not matched_ui_cases:
            continue
        matched_names = "、".join(
            matched_case["用例名称"] for matched_case in matched_ui_cases
        )
        issues.append(
            case_issue(
                case,
                "WARN",
                "ui_case_duplicate_split",
                f"同一分组下已存在相同页面区域的 UI校验 用例：{matched_names}；建议把本用例的展示校验项合并到 UI 用例中",
                "用例名称",
            )
        )

    return issues


def validate_file_sources(case_files: list[Path], cases: list[dict[str, str]]) -> list[Issue]:
    issues: list[Issue] = []
    cases_by_file: dict[str, list[dict[str, str]]] = {}
    for case in cases:
        cases_by_file.setdefault(case.get("_source_file", ""), []).append(case)

    for case_file in case_files:
        if not is_generated_output_path(case_file):
            continue

        metadata = file_metadata_block(case_file)
        normalized_metadata = metadata.replace("\\", "/")
        if OUTPUT_REFERENCE_RE.search(normalized_metadata):
            issues.append(
                Issue(
                    severity="ERROR",
                    code="output_file_used_as_input_source",
                    message=(
                        "元信息输入文件不得引用 outputs 下已生成用例或 *_testcases.md；"
                        "参考用例只能来自 testcase_templates 下模板文件"
                    ),
                    file=str(case_file),
                )
            )

        file_cases = cases_by_file.get(str(case_file), [])
        has_ui_source = bool(
            re.search(
                r"inputs/ui_design/.*\.(?:png|jpg|jpeg|webp|gif)",
                normalized_metadata,
                re.IGNORECASE,
            )
        )
        has_ui_remark = any("UI图" in case.get("备注", "") for case in file_cases)
        has_ui_case = any(
            normalize_cell(case.get("用例描述", "")).upper() == "UI"
            or "UI校验" in case.get("用例名称", "")
            for case in file_cases
        )

        if has_ui_remark and not has_ui_source:
            issues.append(
                Issue(
                    severity="ERROR",
                    code="ui_source_missing_in_metadata",
                    message="用例备注引用了 UI图，但文件元信息输入文件未列出 inputs/ui_design 下的图片",
                    file=str(case_file),
                )
            )
        if has_ui_source and not has_ui_case:
            issues.append(
                Issue(
                    severity="WARN",
                    code="ui_source_without_ui_case",
                    message="文件元信息包含 UI 图，但未发现用例描述为 UI 或用例名称包含 UI校验 的用例",
                    file=str(case_file),
                )
            )

    return issues


def _case_module_set(case: dict[str, str]) -> set[str]:
    """业务模块名匹配一级/二级分组（避免子串误命中三级分组里的同名词）。"""
    return {case.get("一级分组", ""), case.get("二级分组", "")}


def group_path_contains(case: dict[str, str], keyword: str) -> bool:
    return any(keyword in case.get(header, "") for header in group_headers_from_case(case))


def validate_core_flow_coverage(cases: list[dict[str, str]]) -> list[Issue]:
    """核心业务模块应覆盖约定的关键场景关键词，缺失时给出 WARN。

    词表来自 ``business_constants.CORE_FLOW_KEYWORDS``；新项目填入词表后即可启用，
    留空时本函数不产生任何 Issue。
    """
    issues: list[Issue] = []
    if not CORE_FLOW_KEYWORDS:
        return issues

    modules_present: set[str] = set()
    for case in cases:
        modules_present |= _case_module_set(case)
    modules_present.discard("")

    for module, keyword_groups in CORE_FLOW_KEYWORDS.items():
        if module not in modules_present:
            continue
        module_cases = [case for case in cases if module in _case_module_set(case)]
        if not module_cases:
            continue
        module_text = "".join(
            f"{case['用例名称']}{case['前置条件']}{case['用例步骤']}{case['预期结果']}".lower()
            for case in module_cases
        )
        missing_groups = [
            groups[0]
            for groups in keyword_groups
            if not any(keyword.lower() in module_text for keyword in groups)
        ]
        if missing_groups:
            issues.append(
                text_issue(
                    "WARN",
                    "core_flow_coverage_gap",
                    f"核心链路模块“{module}”疑似缺少关键场景覆盖：{'、'.join(missing_groups)}",
                )
            )

    return issues


def validate_duration_metadata(case_files: list[Path]) -> list[Issue]:
    """最终交付前，"生成耗时"不得保留 待回填/约/预计 占位词；"生成时间"必须为真实系统时间。"""
    issues: list[Issue] = []
    now = datetime.now()
    for case_file in case_files:
        if not is_generated_output_path(case_file):
            continue
        try:
            metadata = file_metadata_block(case_file)
        except OSError:
            continue
        if DURATION_PLACEHOLDER_RE.search(metadata):
            issues.append(
                Issue(
                    severity="WARN",
                    code="duration_placeholder_remaining",
                    message="生成耗时仍为待回填/约/预计，导出前必须按实际耗时回填",
                    file=str(case_file),
                )
            )
        # 校验生成时间：必须精确到秒、不得为未来时间
        time_match = GENERATED_TIME_LINE_RE.search(metadata)
        if time_match:
            time_str = time_match.group(1).strip()
            if not GENERATED_TIME_FORMAT_RE.match(time_str):
                issues.append(
                    Issue(
                        severity="ERROR",
                        code="generated_time_format_invalid",
                        message=(
                            f"生成时间格式必须为 YYYY-MM-DD HH:MM:SS（精确到秒），"
                            f"当前为 {time_str}；请通过 date +%Y-%m-%d\\ %H:%M:%S 命令获取真实系统时间"
                        ),
                        file=str(case_file),
                    )
                )
            else:
                try:
                    generated_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                    if generated_time > now:
                        issues.append(
                            Issue(
                                severity="ERROR",
                                code="generated_time_in_future",
                                message=(
                                    f"生成时间 {time_str} 是未来时间，"
                                    f"必须为真实的开始读取资料时刻，不得手动编写"
                                ),
                                file=str(case_file),
                            )
                        )
                    elif (now - generated_time).total_seconds() > 86400:
                        issues.append(
                            Issue(
                                severity="WARN",
                                code="generated_time_too_old",
                                message=f"生成时间 {time_str} 距今超过24小时，请确认是否正确",
                                file=str(case_file),
                            )
                        )
                except ValueError:
                    issues.append(
                        Issue(
                            severity="ERROR",
                            code="generated_time_format_invalid",
                            message=f"生成时间 {time_str} 无法解析为有效日期时间",
                            file=str(case_file),
                        )
                    )
    return issues


# ---------------------------------------------------------------------------
# 覆盖率校验
#
# 两个 check 都需要 case_files（覆盖率表和来源 docx 都在文件层级），
# 因此挂在通用校验链里，不进业务注册表（业务注册表签名只有 cases）。
# ---------------------------------------------------------------------------


def extract_source_doc_path(metadata: str) -> str | None:
    """从元信息块提取"来源文档"路径，不存在返回 None。"""
    match = SOURCE_DOC_RE.search(metadata)
    if not match:
        return None
    return match.group(1).strip()


def _strip_leading_number(text: str) -> str:
    """剥离前导编号（如 '3.3.1 新增任务管理菜单' → '新增任务管理菜单'）。

    兼容阿拉伯数字分段编号（3.3.1）和汉字数字编号（三、）。
    """
    stripped = text.strip()
    stripped = re.sub(r"^[\d.]+[.\s]*", "", stripped)
    stripped = re.sub(r"^[一二三四五六七八九十]+、\s*", "", stripped)
    return stripped.strip()


def extract_source_section(metadata: str) -> str | None:
    """从元信息块提取"来源章节"名称，不存在返回 None。

    自动剥离前导编号（如 '3.3.1 新增任务管理菜单' → '新增任务管理菜单'）。
    """
    match = SOURCE_SECTION_RE.search(metadata)
    if not match:
        return None
    return _strip_leading_number(match.group(1))


def _cases_by_file(cases: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for case in cases:
        grouped.setdefault(case.get("_source_file", ""), []).append(case)
    return grouped


def validate_coverage_references(
    case_files: list[Path], cases: list[dict[str, str]]
) -> list[Issue]:
    """检查覆盖率对照表引用的用例名称是否在用例表中真实存在。

    不存在的引用会直接 ERROR 阻断导出——这通常是用例被改名但覆盖率表
    未同步更新导致的，必须人工确认。
    """
    issues: list[Issue] = []
    cases_by_file = _cases_by_file(cases)

    for case_file in case_files:
        # 只对生成出来的用例文件做此检查；参考模板里可能没有覆盖率表
        if not is_generated_output_path(case_file):
            continue
        entries = parse_coverage_tables(case_file)
        if not entries:
            issues.append(
                Issue(
                    severity="WARN",
                    code="coverage_table_missing",
                    message="文件无需求覆盖率对照表，覆盖率引用校验已跳过",
                    file=str(case_file),
                )
            )
            continue

        file_cases = cases_by_file.get(str(case_file), [])
        case_name_set = {case.get("用例名称", "") for case in file_cases}
        case_name_set.discard("")

        for entry in entries:
            for case_name in entry.get("case_names", []):
                if case_name not in case_name_set:
                    issues.append(
                        Issue(
                            severity="ERROR",
                            code="coverage_reference_invalid",
                            message=(
                                f"覆盖率对照表引用的用例 '{case_name}' "
                                f"在用例表中不存在"
                            ),
                            file=str(entry.get("source_file", "")),
                            line=entry.get("source_line"),
                            field="覆盖用例名称",
                        )
                    )
    return issues


_PRD_TABLE_TYPE_LABELS = {
    "state_table": "状态对照表",
    "field_table": "字段定义表",
}


def _parse_prd_table_row_text(text: str) -> tuple[int | None, list[str]]:
    """从 '表格行N：cell1 | cell2' 文本中解析行号和单元格列表。

    由 extract_docx._table_lines 生成的格式，行号用于识别表格边界
    （每个表格的第 1 行是表头）。
    """
    match = re.match(r"^表格行(\d+)：(.*)$", text)
    if not match:
        return None, []
    row_num = int(match.group(1))
    rest = match.group(2)
    cells = [cell.strip() for cell in rest.split("|")]
    return row_num, cells


def extract_prd_table_items(
    section_blocks: list,  # list[DocBlock]，用 duck typing 避免 import 循环
) -> list[tuple[str, str]]:
    """提取 PRD 章节中的表格行需求点。

    识别两类表格：
    - 状态对照表（表头含"状态"和"操作"）→ ``state_table``
    - 字段定义表（表头含"字段名称"和"必填"）→ ``field_table``

    其他表格（如需求概述类）跳过。返回 ``[(table_type, key), ...]``，
    key 取每条数据行的第一列。
    """
    items: list[tuple[str, str]] = []
    current_rows: list[list[str]] = []

    def flush() -> None:
        if not current_rows:
            return
        if len(current_rows) < 2:
            current_rows.clear()
            return
        header_text = " ".join(current_rows[0])
        if all(hint in header_text for hint in PRD_STATE_TABLE_HEADER_HINTS):
            table_type = "state_table"
        elif all(hint in header_text for hint in PRD_FIELD_TABLE_HEADER_HINTS):
            table_type = "field_table"
        else:
            current_rows.clear()
            return
        for row_cells in current_rows[1:]:
            if not row_cells:
                continue
            key = row_cells[0].strip()
            if key:
                items.append((table_type, key))
        current_rows.clear()

    for block in section_blocks:
        if getattr(block, "kind", None) != "table":
            flush()
            continue
        row_num, cells = _parse_prd_table_row_text(block.text)
        if row_num == 1 and current_rows:
            # 遇到新的"表格行1"说明上一个表格结束
            flush()
        if cells:
            current_rows.append(cells)
    flush()

    return items


def extract_prd_numbered_items(
    section_blocks: list,  # list[DocBlock]
) -> list[str]:
    """提取 PRD 章节中的编号子项关键字。

    流程：
    1. 收集所有 paragraph + table 文本（不含 heading）
    2. 用 [一二三四五六七八九十]+、 切分顶级章节
    3. 在每个章节内用 [0-9]+[.、）)] 切分子项
    4. 对每个子项，取编号后到首个边界标点之间的文字，截取前 10 字作为 keyword
    """
    lines: list[str] = []
    for block in section_blocks:
        if getattr(block, "kind", None) in ("paragraph", "table"):
            lines.append(block.text)
    text = "\n".join(lines)

    chapter_marks = list(PRD_TOP_LEVEL_CHAPTER_RE.finditer(text))
    if chapter_marks:
        chapter_texts: list[str] = []
        if chapter_marks[0].start() > 0:
            chapter_texts.append(text[: chapter_marks[0].start()])
        for i, match in enumerate(chapter_marks):
            start = match.end()
            end = (
                chapter_marks[i + 1].start() if i + 1 < len(chapter_marks) else len(text)
            )
            chapter_texts.append(text[start:end])
    else:
        chapter_texts = [text]

    keywords: list[str] = []
    for chapter_text in chapter_texts:
        sub_marks = list(PRD_SUB_ITEM_NUMBER_RE.finditer(chapter_text))
        if not sub_marks:
            continue
        for i, match in enumerate(sub_marks):
            start = match.end()
            end = (
                sub_marks[i + 1].start() if i + 1 < len(sub_marks) else len(chapter_text)
            )
            sub_text = chapter_text[start:end].strip()
            if not sub_text:
                continue
            first_line = sub_text.split("\n", 1)[0].strip()
            boundary = PRD_SUB_ITEM_TITLE_BOUNDARY_RE.search(first_line)
            title = first_line[: boundary.start()].strip() if boundary else first_line
            if not title:
                continue
            keywords.append(title[:PRD_SUB_ITEM_KEYWORD_MAX_LENGTH])
    return keywords


def validate_hard_coverage(
    case_files: list[Path], cases: list[dict[str, str]]
) -> list[Issue]:
    """检查 PRD 表格行和编号项是否在覆盖率对照表中有对应覆盖记录。

    弱信号（WARN）：未覆盖时仅提示人工确认，不阻断导出。来源 docx
    不可读或 python-docx 未安装时整体跳过本文件检查。
    """
    issues: list[Issue] = []
    cases_by_file = _cases_by_file(cases)

    for case_file in case_files:
        if not is_generated_output_path(case_file):
            continue
        try:
            metadata = file_metadata_block(case_file)
        except OSError:
            issues.append(
                Issue(
                    severity="WARN",
                    code="prd_doc_unavailable",
                    message="无法读取元信息块，硬覆盖检查已跳过",
                    file=str(case_file),
                )
            )
            continue

        source_doc = extract_source_doc_path(metadata)
        if not source_doc:
            # 没有来源文档（如模板文件）不是错，静默跳过
            continue
        source_section = extract_source_section(metadata)

        # 延迟 import：python-docx 不是必装依赖
        try:
            from extract_docx import (
                extract_section,
                read_docx_blocks,
                resolve_docx_path,
            )
        except ImportError:
            issues.append(
                Issue(
                    severity="WARN",
                    code="prd_doc_unavailable",
                    message="未安装 python-docx，PRD 硬覆盖检查已跳过",
                    file=str(case_file),
                )
            )
            continue

        try:
            docx_path = resolve_docx_path(source_doc)
            blocks = read_docx_blocks(docx_path)
            if source_section:
                section_blocks = extract_section(blocks, source_section)
            else:
                section_blocks = blocks
        except (FileNotFoundError, ValueError):
            issues.append(
                Issue(
                    severity="WARN",
                    code="prd_doc_unavailable",
                    message=(
                        f"来源文档 {source_doc} 不存在或不可读，"
                        f"PRD 硬覆盖检查已跳过"
                    ),
                    file=str(case_file),
                )
            )
            continue
        except Exception as exc:
            issues.append(
                Issue(
                    severity="WARN",
                    code="prd_doc_unavailable",
                    message=(
                        f"读取来源文档 {source_doc} 失败：{exc}，"
                        f"PRD 硬覆盖检查已跳过"
                    ),
                    file=str(case_file),
                )
            )
            continue

        if not section_blocks:
            issues.append(
                Issue(
                    severity="WARN",
                    code="prd_doc_unavailable",
                    message=(
                        f"在来源文档中未找到章节 '{source_section}'，"
                        f"PRD 硬覆盖检查已跳过"
                    ),
                    file=str(case_file),
                )
            )
            continue

        entries = parse_coverage_tables(case_file)
        if not entries:
            # coverage_reference_invalid 检查已提示 coverage_table_missing，
            # 此处不再重复
            continue

        # 把所有覆盖率条目的 requirement_point 和 requirement_desc 拼成可搜索的文本
        coverage_texts = [
            f"{entry.get('requirement_point', '')} {entry.get('requirement_desc', '')}"
            for entry in entries
        ]

        # 检查 PRD 表格行
        for table_type, key in extract_prd_table_items(section_blocks):
            if not any(key in text for text in coverage_texts):
                label = _PRD_TABLE_TYPE_LABELS.get(table_type, table_type)
                issues.append(
                    Issue(
                        severity="WARN",
                        code="prd_table_row_uncovered",
                        message=(
                            f"PRD {label}的 '{key}' 行在覆盖率对照表中"
                            f"未找到对应覆盖记录，请人工确认"
                        ),
                        file=str(case_file),
                    )
                )

        # 检查 PRD 编号项
        for keyword in extract_prd_numbered_items(section_blocks):
            if not any(keyword in text for text in coverage_texts):
                issues.append(
                    Issue(
                        severity="WARN",
                        code="prd_numbered_item_uncovered",
                        message=(
                            f"PRD 编号项 '{keyword}' 在覆盖率对照表中"
                            f"未找到明确匹配，请人工确认"
                        ),
                        file=str(case_file),
                    )
                )

    return issues


def validate_group_depth_limit(cases: list[dict[str, str]]) -> list[Issue]:
    """检查分组深度是否超过 MAX_GROUP_DEPTH 上限。

    与 ``validate_group_depth_consistency``（"填到底"）配套：
    - ``consistency`` 管"形状"——某级有值时更深层级也必须有值
    - ``limit`` 管"上限"——某级超过 MAX_GROUP_DEPTH 时不允许填值

    只检查"**有值**"的超限层级：表头声明了超限列但用例实际没填值不算违规
    （那种情况由"禁止保留冗余的空分组列"规则处理）。
    """
    issues: list[Issue] = []
    for case in cases:
        for header in group_headers_from_case(case):
            level = GROUP_HEADER_LEVELS.get(header, 0)
            if level > MAX_GROUP_DEPTH and case.get(header, "").strip():
                issues.append(
                    case_issue(
                        case,
                        "ERROR",
                        "group_depth_exceeded",
                        f"分组层级超过上限：{header}（{level} 级）有值，"
                        f"本项目最大分组深度为 {MAX_GROUP_DEPTH} 级；"
                        f"更深层级的业务请拆分到独立输出文件或归并到上级分组",
                        header,
                    )
                )
                break  # 同条用例只报一次
    return issues


# 业务校验插件注册表。
# 通用校验（表头、优先级、重复、分组相邻、元信息等）在 run_all_validations 里
# 无条件调用；业务校验通过 business_constants.ENABLED_BUSINESS_RULES 开关按需加载，
# 换项目时可整体关闭、只保留其一，或在下方注册新的业务规则。
# 新增业务校验时：写 validate_* 函数 → 在此注册 → 在 ENABLED_BUSINESS_RULES 加名字。
_BUSINESS_RULE_REGISTRY: dict[str, ...] = {
    "core_flow_coverage": validate_core_flow_coverage,
    "group_depth_limit": validate_group_depth_limit,
}

# 动态加载项目专属业务校验规则
try:
    from project_business_rules import register_business_rules
    for name, func in register_business_rules().items():
        _BUSINESS_RULE_REGISTRY[name] = func
except ImportError:
    pass  # 项目无专属业务规则时不影响


def validate_group_adjacency(cases: list[dict[str, str]]) -> list[Issue]:
    """检查同一文件内分组相邻性和一级分组聚集性。

    规则依据 testcase_writing_guidelines.md：
    - 相同完整分组路径的用例必须连续放在一起，不得被其他分组路径用例打断。
    - 同一一级分组下的所有用例必须聚集在连续区间内，不得被其他一级分组的用例打断。
    """
    issues: list[Issue] = []

    # 按文件分组，保持原顺序；跨文件不合并
    cases_by_file: dict[str, list[dict[str, str]]] = {}
    for case in cases:
        cases_by_file.setdefault(case.get("_source_file", ""), []).append(case)

    for _source_file, file_cases in cases_by_file.items():
        if len(file_cases) < 2:
            continue

        # 检查 1：完整分组路径相邻性
        seen_full_path: dict[str, dict[str, str]] = {}
        prev_full_path: str | None = None
        for case in file_cases:
            full_path = case_group(case)
            if (
                full_path in seen_full_path
                and prev_full_path != full_path
                and prev_full_path is not None
            ):
                first_case = seen_full_path[full_path]
                first_line = first_case.get("_source_line", "")
                issues.append(
                    case_issue(
                        case,
                        "ERROR",
                        "group_not_adjacent",
                        f"分组 [{full_path}] 与第 {first_line} 行的同名分组不相邻，中间被其他分组打断；"
                        "相同完整分组路径的用例必须连续排列",
                        "分组",
                    )
                )
            if full_path not in seen_full_path:
                seen_full_path[full_path] = case
            prev_full_path = full_path

        # 检查 2：按层级检查分组聚集性（一级到 MAX_GROUP_DEPTH-1 级）
        # 完整路径（最深层级）的相邻性由检查 1（group_not_adjacent）覆盖
        level_names_cn = {1: "一级", 2: "二级", 3: "三级", 4: "四级", 5: "五级"}
        for level in range(1, MAX_GROUP_DEPTH):
            level_header = GROUP_HEADERS_BY_LEVEL.get(level)
            if not level_header:
                continue
            headers_up_to = [
                GROUP_HEADERS_BY_LEVEL[l] for l in range(1, level + 1) if l in GROUP_HEADERS_BY_LEVEL
            ]
            seen_prefix: dict[str, dict[str, str]] = {}
            prev_prefix: str | None = None
            for case in file_cases:
                # 构建从一级到当前层级的路径前缀
                parts: list[str] = []
                for h in headers_up_to:
                    v = case.get(h, "").strip()
                    if not v:
                        break
                    parts.append(v)
                # 当前用例未填到本层级时跳过（不影响该层级检查）
                if len(parts) < level:
                    prev_prefix = None  # 重置前序，避免跨层级空值误判
                    continue
                prefix = " / ".join(parts)
                if (
                    prefix in seen_prefix
                    and prev_prefix is not None
                    and prev_prefix != prefix
                ):
                    first_case = seen_prefix[prefix]
                    first_line = first_case.get("_source_line", "")
                    level_cn = level_names_cn.get(level, f"{level}级")
                    issues.append(
                        case_issue(
                            case,
                            "ERROR",
                            "group_level_split",
                            f"{level_cn}分组前缀 [{prefix}] 与第 {first_line} 行的同前缀分组不相邻，"
                            f"被其他分组打断；同一上级分组下相同{level_cn}分组前缀的所有用例必须聚集在连续区间内",
                            level_header,
                        )
                    )
                if prefix not in seen_prefix:
                    seen_prefix[prefix] = case
                prev_prefix = prefix

    return issues


def validate_group_depth_consistency(cases: list[dict[str, str]]) -> list[Issue]:
    """检查分组层级是否填到最深层级（一旦开始填值，必须填到底）。

    规则依据 testcase_writing_guidelines.md：
    某条用例的某级分组一旦有值，其所有更深层级分组列也必须有值。
    即同一用例的分组深度必须填到底，不允许"三级分组有值、四级分组为空"
    等中间层空值；不适用更深层级的用例应整体归并到上级分组。
    """
    issues: list[Issue] = []
    for case in cases:
        group_headers = group_headers_from_case(case)
        if not group_headers:
            continue
        values = [case.get(header, "") for header in group_headers]
        # 找到首个空值位置
        first_empty_idx: int | None = None
        for idx, value in enumerate(values):
            if not value:
                first_empty_idx = idx
                break
        if first_empty_idx is None:
            continue  # 所有分组列都有值，通过
        # 找到最深有值的层级
        last_filled_idx = -1
        for idx in range(len(values) - 1, -1, -1):
            if values[idx]:
                last_filled_idx = idx
                break
        if last_filled_idx < 0:
            continue  # 全空（理论上不会，因为一级必填由其他规则处理）
        if first_empty_idx > last_filled_idx:
            # 首个空值在最后一个有值之后——不是"中间跳空"，
            # 而是用例属于浅层分组、更深层级整体留空的合法情况（如
            # 表头声明 5 级但用例只用到 3 级）。不视为违规。
            continue
        empty_header = group_headers[first_empty_idx]
        deepest_filled_header = group_headers[last_filled_idx]
        issues.append(
            case_issue(
                case,
                "ERROR",
                "group_depth_inconsistent",
                f"分组层级未填到底：{deepest_filled_header}有值但{empty_header}为空，"
                f"某级分组有值时所有更深层级分组也必须有值；"
                f"不适用更深层级的用例应整体归并到上级分组",
                empty_header,
            )
        )
    return issues


def validate_duplicates(cases: list[dict[str, str]]) -> list[Issue]:
    issues: list[Issue] = []

    duplicated_names = duplicate_values(
        cases,
        lambda case: (
            case.get("_source_file", ""),
            case_group(case),
            case["用例名称"],
        ),
    )
    for key, duplicated_cases in duplicated_names.items():
        _, group, case_name = key
        locations = "；".join(case_location(case) for case in duplicated_cases)
        issues.append(
            text_issue(
                "ERROR",
                "duplicate_case_name",
                f"用例名称重复：{group} / {case_name}，位置：{locations}",
            )
        )

    duplicated_flows = duplicate_values(
        cases,
        lambda case: (
            case.get("_source_file", ""),
            case_group(case),
            case["前置条件"],
            case["用例步骤"],
            case["预期结果"],
        ),
    )
    for key, duplicated_cases in duplicated_flows.items():
        group = key[1]
        locations = "；".join(case_location(case) for case in duplicated_cases)
        issues.append(
            text_issue(
                "ERROR",
                "duplicate_flow",
                f"疑似重复流程：{group}，位置：{locations}",
            )
        )

    return issues


def build_summary(
    case_files: list[Path],
    cases: list[dict[str, str]],
    issues: list[Issue],
    fixes: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    modules = Counter(case_group(case) for case in cases if case_group(case))
    errors = [issue for issue in issues if issue.severity == "ERROR"]
    warnings = [issue for issue in issues if issue.severity == "WARN"]
    fixes = fixes or []
    return {
        "file_count": len(case_files),
        "case_count": len(cases),
        "modules": sorted(modules),
        "issue_count": len(issues),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "fixed_file_count": sum(1 for fix in fixes if fix["changed"]),
    }


def print_text_report(
    case_files: list[Path],
    cases: list[dict[str, str]],
    issues: list[Issue],
    summary_only: bool = False,
    fixes: list[dict[str, object]] | None = None,
) -> None:
    summary = build_summary(case_files, cases, issues, fixes)
    if fixes is not None:
        print("格式修复结果：")
        print(f"- 处理文件数量：{len(fixes)}")
        print(f"- 更新文件数量：{summary['fixed_file_count']}")
        changed_fixes = [fix for fix in fixes if fix["changed"]]
        if changed_fixes and not summary_only:
            for fix in changed_fixes:
                print(
                    "- "
                    f"{fix['file']}：表头 {fix['fixed_headers']}，"
                    f"分隔行 {fix['fixed_separators']}，"
                    f"用例行 {fix['changed_rows']}，"
                    f"重复空行 {fix['removed_blank_lines']}"
                )
        print()

    print("测试用例校验结果：")
    print(f"- 文件数量：{summary['file_count']}")
    print(f"- 用例数量：{summary['case_count']}")
    print(f"- 覆盖模块：{', '.join(summary['modules'])}")
    print(f"- 问题数量：{summary['issue_count']}")
    print(f"- 错误数量：{summary['error_count']}")
    print(f"- 警告数量：{summary['warning_count']}")

    if issues and not summary_only:
        print("\n问题明细：")
        for issue in issues:
            print(f"- {format_issue(issue)}")


def print_json_report(
    case_files: list[Path],
    cases: list[dict[str, str]],
    issues: list[Issue],
    fixes: list[dict[str, object]] | None = None,
) -> None:
    payload = {
        "summary": build_summary(case_files, cases, issues, fixes),
        "issues": [asdict(issue) for issue in issues],
        "fixes": fixes or [],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parse_args(argv: list[str]) -> argparse.Namespace:
    root = project_root()
    parser = argparse.ArgumentParser(description="校验 Markdown 测试用例表格")
    parser.add_argument(
        "--source",
        default=None,
        help="输入文件或目录，默认扫描 outputs/<project>/business_site/origin_exports/**/*_testcases.md",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="只输出汇总，不逐条输出问题明细",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="只修复 outputs/origin_exports/ 内的 Markdown 表格格式，不修改用例业务语义",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出校验结果，便于 Agent 或自动化流程解析",
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("CASE_GEN_PROJECT", "qrs"),
        help="项目名称（qrs/cpv），默认读取环境变量 CASE_GEN_PROJECT 或 qrs",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    configure_output_encoding()
    root = project_root()
    args = parse_args(argv)

    # 根据项目设置默认 source
    if args.source is None:
        args.source = str(root / "outputs" / args.project / "business_site" / "origin_exports")

    try:
        source = ensure_under(build_source_path(args.source, root), root, "输入路径")
        if args.fix:
            output_cases_dir = root / "outputs" / args.project / "business_site" / "origin_exports"
            ensure_under(source, output_cases_dir, "--fix 输入路径")
        case_files = discover_case_files(source)
    except (FileNotFoundError, ValueError) as error:
        issues = [text_issue("ERROR", "source_error", str(error))]
        if args.json:
            print_json_report([], [], issues)
        else:
            print(f"校验失败：{error}", file=sys.stderr)
        return 1

    if not case_files:
        issues = [
            text_issue("ERROR", "no_case_files", "未找到任何测试用例 Markdown 文件")
        ]
        if args.json:
            print_json_report([], [], issues)
        else:
            print("校验失败：未找到任何测试用例 Markdown 文件", file=sys.stderr)
        return 1

    fixes: list[dict[str, object]] | None = None
    if args.fix:
        fixes = fix_case_files(case_files)

    cases: list[dict[str, str]] = []
    parse_warnings: list[str] = []
    for case_file in case_files:
        parsed_cases, file_warnings = parse_case_file(case_file)
        cases.extend(parsed_cases)
        parse_warnings.extend(file_warnings)

    issues: list[Issue] = []
    if not cases:
        issues.append(text_issue("ERROR", "no_cases", "未解析到测试用例"))
        if args.json:
            print_json_report(case_files, cases, issues, fixes)
        else:
            print_text_report(case_files, cases, issues, args.summary_only, fixes)
        return 1

    issues.extend(run_all_validations(case_files, cases, parse_warnings))

    if args.json:
        print_json_report(case_files, cases, issues, fixes)
    else:
        print_text_report(case_files, cases, issues, args.summary_only, fixes)

    return 1 if has_blocking_issues(issues) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
