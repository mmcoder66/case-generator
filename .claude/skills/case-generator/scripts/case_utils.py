#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试用例脚本公共工具。

本模块集中维护测试用例表头、路径安全检查、Markdown 表格解析和文件发现逻辑。
`validate_cases.py` 和 `export_testcases.py` 都依赖这里的公共能力，避免脚本之间互相承担不属于自身职责的工具函数。

改动本文件后，请运行 `python -m pytest scripts/tests/ -v` 确认无回归。
"""

from __future__ import annotations

import html
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable

from business_constants import PROJECT_SPECIFIC_HEADERS


DEFAULT_GROUP_HEADERS = ["一级分组", "二级分组", "三级分组"]
# 通用测试用例字段（9 项）+ 项目专属追踪字段（由 business_constants.PROJECT_SPECIFIC_HEADERS 提供）。
# 业务字段集中在 business_constants.py，换项目时改一处即可同步影响下游解析。
_GENERIC_FIXED_HEADERS = [
    "用例名称",
    "优先级",
    "创建人",
    "用例描述",
    "前置条件",
    "用例步骤",
    "预期结果",
    "备注",
    "用例标签",
]
FIXED_CASE_HEADERS = _GENERIC_FIXED_HEADERS + PROJECT_SPECIFIC_HEADERS
REQUIRED_FIXED_HEADERS = [
    "用例名称",
    "优先级",
    "创建人",
    "用例描述",
    "前置条件",
    "用例步骤",
    "预期结果",
    "备注",
    "用例标签",
]
GROUP_HEADER_LEVELS = {
    "一级分组": 1,
    "二级分组": 2,
    "三级分组": 3,
    "四级分组": 4,
    "五级分组": 5,
    "六级分组": 6,
    "七级分组": 7,
    "八级分组": 8,
    "九级分组": 9,
    "十级分组": 10,
}
GROUP_HEADERS_BY_LEVEL = {
    level: header for header, level in GROUP_HEADER_LEVELS.items()
}

EXPECTED_HEADERS = DEFAULT_GROUP_HEADERS + FIXED_CASE_HEADERS
REQUIRED_HEADERS = DEFAULT_GROUP_HEADERS + REQUIRED_FIXED_HEADERS

VALID_PRIORITIES = {"P0", "P1", "P2"}
DIFFICULTY_LEVELS = ("简单", "一般", "困难")


def is_group_header(header: str) -> bool:
    return header in GROUP_HEADER_LEVELS


def group_headers_from_headers(headers: Iterable[str]) -> list[str]:
    return [header for header in headers if is_group_header(header)]


def group_headers_from_case(case: dict[str, str]) -> list[str]:
    headers = case.get("_headers")
    if isinstance(headers, list):
        return group_headers_from_headers(headers)
    return [header for header in DEFAULT_GROUP_HEADERS if header in case]


def group_headers_for_count(count: int) -> list[str]:
    return [
        GROUP_HEADERS_BY_LEVEL[level]
        for level in range(1, count + 1)
        if level in GROUP_HEADERS_BY_LEVEL
    ]


def expected_headers_for(group_headers: list[str]) -> list[str]:
    return group_headers + FIXED_CASE_HEADERS


def required_headers_for(group_headers: list[str]) -> list[str]:
    return ["一级分组"] + REQUIRED_FIXED_HEADERS


def is_case_header(cells: list[str]) -> bool:
    if len(cells) != len(set(cells)):
        return False
    if "用例名称" not in cells:
        return False
    name_index = cells.index("用例名称")
    group_headers = cells[:name_index]
    if not group_headers:
        return False
    if cells[name_index:] != FIXED_CASE_HEADERS:
        return False
    levels = [GROUP_HEADER_LEVELS.get(header) for header in group_headers]
    return levels == list(range(1, len(group_headers) + 1))


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def is_under(path: Path, root: Path) -> bool:
    # 使用 Path.is_relative_to() 进行路径包含判断，在 Windows 大小写不敏感
    # 的文件系统上也能正确处理大小写不一致的路径（Python 3.9+）。
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def ensure_under(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    if not is_under(resolved, root):
        raise ValueError(f"{label} 必须位于以下目录内：{root}")
    return resolved


def build_source_path(source_arg: str, root: Path) -> Path:
    source_path = Path(source_arg)
    if not source_path.is_absolute():
        source_path = root / source_path
    return source_path


def windows_long_path(path: Path) -> str:
    """Return a filesystem path that works with long Windows paths."""
    resolved = str(path.resolve())
    if os.name != "nt" or resolved.startswith("\\\\?\\"):
        return resolved
    return "\\\\?\\" + resolved


def read_text_file(path: Path, encoding: str = "utf-8") -> str:
    with open(windows_long_path(path), encoding=encoding) as file:
        return file.read()


def write_text_file(path: Path, content: str, encoding: str = "utf-8") -> None:
    with open(windows_long_path(path), "w", encoding=encoding) as file:
        file.write(content)


def split_markdown_row(line: str) -> list[str]:
    text = line.strip()
    if not text.startswith("|") or not text.endswith("|"):
        return []

    text = text[1:-1]
    cells: list[str] = []
    current: list[str] = []

    for index, char in enumerate(text):
        if char == "|" and (index == 0 or text[index - 1] != "\\"):
            cells.append("".join(current).replace(r"\|", "|").strip())
            current = []
        else:
            current.append(char)

    cells.append("".join(current).replace(r"\|", "|").strip())
    return cells


def is_separator_row(cells: Iterable[str]) -> bool:
    normalized = ["".join(cell.split()) for cell in cells]
    return bool(normalized) and all(
        cell and set(cell) <= {"-", ":"} and "-" in cell for cell in normalized
    )


def normalize_cell(value: str) -> str:
    value = html.unescape(value.strip())
    # <br\s*/?> 的正则已能匹配所有变体（<br>、<br/>、<br />），无需额外 replace
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    return value.strip()


def split_case_tags(value: str) -> list[str]:
    """按项目约定拆分用例标签，兼容中文和英文分号。"""
    return [
        tag.strip()
        for tag in re.split(r"[;；]", value or "")
        if tag and tag.strip()
    ]


def count_effective_steps(value: str) -> int:
    """统计有效执行步骤，登录动作不计入。"""
    normalized = normalize_cell(value)
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    numbered_lines = [
        line for line in lines if re.match(r"^\d+[.、]\s*", line)
    ]
    candidates = numbered_lines or lines
    return sum(1 for line in candidates if "登录" not in line)


def count_non_empty_lines(value: str) -> int:
    normalized = normalize_cell(value)
    return len([line for line in normalized.splitlines() if line.strip()])


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _contains_all(text: str, keywords: Iterable[str]) -> bool:
    return all(keyword in text for keyword in keywords)


def _normalize_keyword_text(*values: str) -> str:
    normalized = unicodedata.normalize("NFKC", "\n".join(values))
    return "".join(normalized.split()).lower()


def _normalize_report_lifecycle_text(*values: str) -> str:
    """按 difficulty_level_rules.md 的 report_lifecycle_exclusions 配置，从文本中移除指定关键字。"""
    text = _normalize_keyword_text(*values)
    for keyword in _difficulty_string_list("report_lifecycle_exclusions"):
        text = text.replace(keyword, "")
    return text


def count_verification_points(value: str) -> int:
    """统计预期结果中的独立校验点数量。"""
    normalized = normalize_cell(value)
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if not lines:
        return 0

    total = 0
    for line in lines:
        numbered_points = re.findall(r"(?:^|[：:；;。\s])\d+[.、]", line)
        if numbered_points:
            total += len(numbered_points)
            continue

        semicolon_parts = [
            part.strip()
            for part in re.split(r"[;；]", line)
            if part and part.strip()
        ]
        total += len(semicolon_parts) if len(semicolon_parts) > 1 else 1

    return total


def _matched_keywords(text: str, keywords: Iterable[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def _matched_combinations(
    text: str, combinations: Iterable[tuple[str, ...]]
) -> list[str]:
    return [
        " + ".join(combination)
        for combination in combinations
        if _contains_all(text, combination)
    ]


def is_ui_case(case: dict[str, str]) -> bool:
    """判断是否为 UI 展示类用例：描述为 UI，或用例名称包含"UI校验"。

    判定口径与 validate_cases.is_ui_case 保持一致，避免难度推断和校验
    规则对同一用例给出冲突结论。
    """
    return (
        normalize_cell(case.get("用例描述", "")).upper() == "UI"
        or "UI校验" in case.get("用例名称", "")
    )


DIFFICULTY_RULE_BLOCK_RE = re.compile(
    r"<!--\s*difficulty-rule:([a-z_]+)\s*-->(.*?)<!--\s*/difficulty-rule\s*-->",
    re.DOTALL,
)


def _load_difficulty_rule_config() -> dict[str, str]:
    rules_path = project_root() / "generation_rules" / "difficulty_level_rules.md"
    markdown_text = read_text_file(rules_path, encoding="utf-8")
    config = {
        match.group(1): match.group(2).strip()
        for match in DIFFICULTY_RULE_BLOCK_RE.finditer(markdown_text)
    }
    if not config:
        raise ValueError("difficulty_level_rules.md 缺少 difficulty-rule 配置块")
    return config


def _config_string_list(config: dict[str, str], key: str) -> list[str]:
    value = config.get(key)
    if value is None:
        raise ValueError(f"difficulty_level_rules.md 缺少 difficulty-rule:{key}")

    keywords = [keyword.strip() for keyword in re.findall(r"`([^`]+)`", value)]
    if not keywords:
        raise ValueError(f"difficulty-rule:{key} 必须至少包含一个反引号关键字")
    return keywords


def _config_combinations(config: dict[str, str], key: str) -> list[tuple[str, ...]]:
    value = config.get(key)
    if value is None:
        raise ValueError(f"difficulty_level_rules.md 缺少 difficulty-rule:{key}")

    combinations: list[tuple[str, ...]] = []
    for line in value.splitlines():
        keywords = [keyword.strip() for keyword in re.findall(r"`([^`]+)`", line)]
        if keywords:
            if len(keywords) < 2:
                raise ValueError(f"difficulty-rule:{key} 的组合至少需要两个关键字")
            combinations.append(tuple(keywords))
    if not combinations:
        raise ValueError(f"difficulty-rule:{key} 必须至少包含一个关键字组合")
    return combinations


_DIFFICULTY_RULE_CONFIG: dict[str, str] | None = None
_DIFFICULTY_STRING_CACHE: dict[str, list[str]] = {}
_DIFFICULTY_COMBINATION_CACHE: dict[str, list[tuple[str, ...]]] = {}


def _difficulty_config() -> dict[str, str]:
    """Load difficulty rules lazily so lightweight helpers remain import-safe."""
    global _DIFFICULTY_RULE_CONFIG
    if _DIFFICULTY_RULE_CONFIG is None:
        _DIFFICULTY_RULE_CONFIG = _load_difficulty_rule_config()
    return _DIFFICULTY_RULE_CONFIG


def _difficulty_string_list(key: str) -> list[str]:
    if key not in _DIFFICULTY_STRING_CACHE:
        _DIFFICULTY_STRING_CACHE[key] = _config_string_list(_difficulty_config(), key)
    return _DIFFICULTY_STRING_CACHE[key]


def _difficulty_combinations(key: str) -> list[tuple[str, ...]]:
    if key not in _DIFFICULTY_COMBINATION_CACHE:
        _DIFFICULTY_COMBINATION_CACHE[key] = _config_combinations(
            _difficulty_config(), key
        )
    return _DIFFICULTY_COMBINATION_CACHE[key]


def infer_case_difficulty_with_reason(case: dict[str, str]) -> tuple[str, list[str]]:
    """综合强规则、简单优先规则和复杂度评分推断难度，并返回判定原因。"""
    difficult_high_confidence_keywords = _difficulty_string_list(
        "difficult_high_confidence_keywords"
    )
    difficult_title_only_keywords = _difficulty_string_list(
        "difficult_title_only_keywords"
    )
    difficult_keyword_combinations = _difficulty_combinations(
        "difficult_keyword_combinations"
    )
    complexity_keywords_config = _difficulty_string_list("complexity_keywords")
    complexity_keyword_combinations = _difficulty_combinations(
        "complexity_keyword_combinations"
    )
    simple_field_validation_keywords_config = _difficulty_string_list(
        "simple_field_validation_keywords"
    )
    simple_operation_keywords_config = _difficulty_string_list(
        "simple_operation_keywords"
    )
    simple_import_file_validation_keywords_config = _difficulty_string_list(
        "simple_import_file_validation_keywords"
    )
    simple_import_template_download_keywords_config = _difficulty_string_list(
        "simple_import_template_download_keywords"
    )

    title_text = case.get("用例名称", "")
    description_text = case.get("用例描述", "")
    precondition_text = case.get("前置条件", "")
    step_text = case.get("用例步骤", "")
    expectation_text = case.get("预期结果", "")
    ui_case = is_ui_case(case)

    normalized_title_text = _normalize_keyword_text(title_text)
    normalized_step_expectation_text = _normalize_keyword_text(step_text, expectation_text)
    normalized_combination_text = _normalize_keyword_text(title_text, step_text)
    normalized_report_lifecycle_text = _normalize_report_lifecycle_text(
        title_text, step_text
    )
    hard_reasons: list[str] = []
    hard_title_keywords = _matched_keywords(
        normalized_title_text, difficult_high_confidence_keywords
    )
    if hard_title_keywords:
        hard_reasons.append(f"用例名称命中困难强规则关键字：{'、'.join(hard_title_keywords)}")

    hard_title_only_keywords = _matched_keywords(
        normalized_title_text, difficult_title_only_keywords
    )
    if hard_title_only_keywords:
        hard_reasons.append(
            f"用例名称命中仅标题困难强规则关键字：{'、'.join(hard_title_only_keywords)}"
        )

    hard_step_keywords = _matched_keywords(
        normalized_step_expectation_text, difficult_high_confidence_keywords
    )
    if hard_step_keywords:
        hard_reasons.append(
            f"步骤或预期命中困难强规则关键字：{'、'.join(hard_step_keywords)}"
        )

    hard_combinations = _matched_combinations(
        normalized_report_lifecycle_text, difficult_keyword_combinations
    )
    if hard_combinations:
        hard_reasons.append(f"命中困难组合关键字：{'、'.join(hard_combinations)}")

    if hard_reasons:
        return "困难", hard_reasons

    score = 0
    reasons: list[str] = []

    precondition_count = count_non_empty_lines(case.get("前置条件", ""))
    step_count = count_effective_steps(case.get("用例步骤", ""))
    verification_count = count_verification_points(case.get("预期结果", ""))

    if precondition_count > 3:
        score += 2
        reasons.append(f"前置条件 {precondition_count} 条，准备复杂 +2")
    elif precondition_count >= 2:
        score += 1
        reasons.append(f"前置条件 {precondition_count} 条，准备中等 +1")

    if step_count > 5:
        score += 2
        reasons.append(f"有效步骤 {step_count} 步，路径复杂 +2")
    elif step_count >= 3:
        score += 1
        reasons.append(f"有效步骤 {step_count} 步，路径中等 +1")

    if ui_case and verification_count >= 2:
        score += 1
        reasons.append(f"UI 校验点 {verification_count} 个，展示验证中等 +1")
    elif verification_count >= 4:
        score += 2
        reasons.append(f"预期结果 {verification_count} 个校验点，验证复杂 +2")
    elif verification_count >= 2:
        score += 1
        reasons.append(f"预期结果 {verification_count} 个校验点，验证中等 +1")

    complexity_combinations = _matched_combinations(
        normalized_combination_text, complexity_keyword_combinations
    )
    complexity_keyword_fields = (title_text, step_text, expectation_text) if ui_case else (
        title_text,
        description_text,
        precondition_text,
        step_text,
        expectation_text,
    )
    complexity_keyword_text = _normalize_report_lifecycle_text(
        *complexity_keyword_fields
    )
    complexity_keywords = _matched_keywords(
        complexity_keyword_text, complexity_keywords_config
    )
    complexity_signals = list(
        dict.fromkeys(complexity_keywords + complexity_combinations)
    )
    if complexity_signals:
        score += 1
        reasons.append(f"命中复杂度信号：{'、'.join(complexity_signals)} +1")

    import_case = "导入" in normalized_combination_text

    simple_import_file_validation_keywords = _matched_keywords(
        normalized_title_text, simple_import_file_validation_keywords_config
    )
    if (
        simple_import_file_validation_keywords
        and verification_count <= 3
        and precondition_count <= 3
        and step_count <= 3
        and set(complexity_signals).issubset({"导入"})
    ):
        return "简单", [
            "导入文件级基础校验，"
            f"命中简单导入文件校验信号：{'、'.join(simple_import_file_validation_keywords)}"
        ]

    simple_import_template_download_keywords = _matched_keywords(
        normalized_title_text, simple_import_template_download_keywords_config
    )
    if (
        simple_import_template_download_keywords
        and verification_count <= 4
        and precondition_count <= 3
        and step_count <= 3
        and set(complexity_signals).issubset({"导入"})
    ):
        return "简单", [
            "导入模板下载低复杂度校验，"
            f"命中简单导入模板下载信号：{'、'.join(simple_import_template_download_keywords)}"
        ]

    simple_field_validation_keywords = _matched_keywords(
        normalized_title_text, simple_field_validation_keywords_config
    )
    if (
        simple_field_validation_keywords
        and verification_count <= 3
        and precondition_count <= 3
        and step_count <= 3
        and not complexity_signals
    ):
        return "简单", [
            "单字段提示类校验，"
            f"命中简单校验信号：{'、'.join(simple_field_validation_keywords)}"
        ]

    simple_operation_keywords = _matched_keywords(
        normalized_title_text, simple_operation_keywords_config
    )
    if (
        simple_operation_keywords
        and verification_count <= 3
        and precondition_count <= 4
        and step_count <= 4
        and not complexity_signals
    ):
        return "简单", [
            "基础配置项或字段级操作校验，"
            f"命中简单操作信号：{'、'.join(simple_operation_keywords)}"
        ]

    if score >= 5:
        if ui_case:
            reasons.append("UI 展示类用例未命中强规则，最高按一般处理")
            return "一般", reasons
        if import_case:
            reasons.append("导入场景未命中困难强规则，最高按一般处理")
            return "一般", reasons
        return "困难", reasons or [f"综合复杂度得分 {score}"]
    if score >= 3:
        return "一般", reasons or [f"综合复杂度得分 {score}"]

    return "简单", reasons or ["未命中复杂信号，前置、步骤和验证点均较少"]


def infer_case_difficulty(case: dict[str, str]) -> str:
    """根据 difficulty_level_rules.md 的综合评分规则推断用例难度。"""
    difficulty, _ = infer_case_difficulty_with_reason(case)
    return difficulty


def merge_difficulty_tag(existing_tags: str, difficulty: str) -> str:
    """用例标签只保留难度等级。"""
    return difficulty


def apply_difficulty_tag(case: dict[str, str]) -> dict[str, str]:
    updated = dict(case)
    difficulty = infer_case_difficulty(updated)
    updated["用例标签"] = merge_difficulty_tag(updated.get("用例标签", ""), difficulty)
    return updated


def apply_difficulty_tags(cases: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    return [apply_difficulty_tag(case) for case in cases]


def parse_case_file(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    warnings: list[str] = []
    cases: list[dict[str, str]] = []

    try:
        lines = read_text_file(path, encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError:
        lines = read_text_file(path, encoding="utf-8").splitlines()

    index = 0
    found_table = False
    while index < len(lines):
        cells = [normalize_cell(cell) for cell in split_markdown_row(lines[index])]
        if not is_case_header(cells):
            index += 1
            continue
        headers = expected_headers_for(group_headers_from_headers(cells))
        header_indexes = {header: cells.index(header) for header in headers}

        found_table = True
        index += 1

        if index < len(lines):
            separator_cells = split_markdown_row(lines[index])
            if is_separator_row(separator_cells):
                index += 1

        # 遇到非表格行时停止当前表格的解析；外层 while 循环会继续向下
        # 扫描，因此同一文件中的多张表格（如追加记录、需求覆盖率对照表）
        # 都能被正确识别和解析。
        while index < len(lines):
            row_line = lines[index]
            if not row_line.strip().startswith("|"):
                break

            row_cells = split_markdown_row(row_line)
            if is_separator_row(row_cells):
                index += 1
                continue

            normalized_cells = [normalize_cell(cell) for cell in row_cells]
            if len(normalized_cells) != len(headers):
                warnings.append(
                    f"{path} 第 {index + 1} 行列数为 {len(normalized_cells)}，"
                    f"期望 {len(headers)}，已跳过"
                )
                index += 1
                continue

            case = {
                header: normalized_cells[header_indexes[header]]
                for header in headers
            }
            case["_headers"] = headers
            case["_source_file"] = str(path)
            case["_source_line"] = str(index + 1)
            cases.append(case)
            index += 1

    if not found_table:
        warnings.append(f"{path} 未找到标准测试用例表格")

    return cases, warnings


def discover_case_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if source.is_dir():
        if "testcase_templates" in source.parts and "modules" in source.parts:
            skipped_names = {"menu_index.md", "module_overview.md", "README.md"}
            return sorted(
                path
                for path in source.rglob("*.md")
                if path.name not in skipped_names
                and path.name.endswith("_template.md")
            )

        # 仅匹配以 _testcases.md 结尾的文件，带时间戳的"另存"文件
        # （如 login_testcases_20260613.md）不在默认扫描范围内，需要
        # 通过 --source 显式指定才能被处理。
        return sorted(source.rglob("*_testcases.md"))
    raise FileNotFoundError(f"输入路径不存在：{source}")
