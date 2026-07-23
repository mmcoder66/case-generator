#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate QRS case generator configuration and detect leftover contamination.

This script checks for common project-onboarding problems:
- old business/system-specific code identifiers left in rules or templates
  (e.g. legacy `CPV_SPECIFIC_HEADERS`, `default_site`, `SITE_TYPES` from prior projects)
- Word temporary lock files in raw_docs
- generated output artifacts left in outputs/
- missing recommended QRS knowledge-base files

It is intentionally conservative: findings are warnings by default and should be
reviewed before generating formal test cases.

QRS-specific business terms (质量回顾 / 回顾计划 / 数据复核 / 监控与预警 / QA 专员 / CPV 等)
are NOT treated as forbidden, because they are legitimate QRS business vocabulary.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from case_utils import configure_output_encoding, project_root, read_text_file


# Legacy code identifiers from a prior project (CPV site system). These should
# never appear in the QRS codebase; if they do, it's leftover contamination.
# QRS business terms are intentionally excluded — they are legitimate vocabulary.
DEFAULT_FORBIDDEN_TERMS = [
    "CPV_SPECIFIC_HEADERS",
    "default_site",
    "site_type",
    "SITE_TYPES",
    "站点",
]

SCAN_DIRS = [
    "SKILL.md",
    "README.md",
    "generation_rules",
    "testcase_templates",
    "knowledge_base",
    "scripts",
    "inputs",
    "outputs",
]

IGNORED_PATH_PARTS = {
    "__pycache__",
    ".pytest_cache",
}
IGNORED_FILE_NAMES = {
    "validate_project_config.py",
}

RECOMMENDED_KNOWLEDGE_FILES = [
    "project_overview.md",
    "business_glossary.md",
    "user_roles.md",
]


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str
    path: Path | None = None


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def iter_text_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for entry in SCAN_DIRS:
        base = root / entry
        if not base.exists():
            continue
        if base.is_file():
            candidates = [base]
        else:
            candidates = list(base.rglob("*"))
        for path in candidates:
            if not path.is_file():
                continue
            if any(part in IGNORED_PATH_PARTS for part in path.parts):
                continue
            if path.name in IGNORED_FILE_NAMES:
                continue
            if path.suffix.lower() in {".py", ".md", ".txt", ".json", ".yml", ".yaml"}:
                paths.append(path)
    return sorted(set(paths))


def scan_forbidden_terms(root: Path, terms: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_text_files(root):
        try:
            text = read_text_file(path, encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for term in terms:
            if term in text:
                findings.append(
                    Finding(
                        "WARN",
                        "forbidden_term",
                        f"发现旧项目代码标识符残留：{term}",
                        path,
                    )
                )
    return findings


def check_word_inputs(root: Path) -> list[Finding]:
    raw_docs = root / "inputs" / "requirements" / "raw_docs"
    findings: list[Finding] = []
    if not raw_docs.exists():
        return findings
    for path in sorted(raw_docs.glob("*.docx")):
        if path.name.startswith("~$"):
            findings.append(
                Finding("ERROR", "word_lock_file", "发现 Word 临时锁文件，应删除", path)
            )
        else:
            findings.append(
                Finding(
                    "WARN",
                    "input_doc_present",
                    "发现输入 PRD 文档；交付前建议确认是否为最新 QRS PRD",
                    path,
                )
            )
    return findings


def check_outputs(root: Path, allow_outputs: bool) -> list[Finding]:
    if allow_outputs:
        return []
    outputs = root / "outputs"
    findings: list[Finding] = []
    for pattern in ("origin_exports/**/*_testcases.md", "excel_exports/**/*.xlsx"):
        for path in sorted(outputs.glob(pattern)):
            findings.append(
                Finding(
                    "WARN",
                    "generated_output_present",
                    "发现已生成 QRS 用例交付物；交付前建议清理或归档",
                    path,
                )
            )
    return findings


def check_knowledge_base(root: Path) -> list[Finding]:
    knowledge_root = root / "knowledge_base"
    findings: list[Finding] = []
    for filename in RECOMMENDED_KNOWLEDGE_FILES:
        path = knowledge_root / filename
        if not path.exists():
            findings.append(
                Finding(
                    "WARN",
                    "missing_knowledge_file",
                    f"建议补充知识库文件：knowledge_base/{filename}",
                    path,
                )
            )
    core_flows = knowledge_root / "core_flows"
    if not core_flows.exists() or not any(core_flows.glob("*.md")):
        findings.append(
            Finding(
                "WARN",
                "missing_core_flow",
                "建议补充至少一个 knowledge_base/core_flows/*.md 核心流程文件",
                core_flows,
            )
        )
    return findings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验 QRS 用例生成器项目配置和残留")
    parser.add_argument(
        "--allow-outputs",
        action="store_true",
        help="允许 outputs/ 下存在已生成用例或 Excel 文件",
    )
    parser.add_argument(
        "--term",
        action="append",
        default=[],
        help="追加要扫描的旧项目残留词（QRS 业务词除外），可重复传入",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="将 WARN 也视为失败退出",
    )
    return parser.parse_args(argv)


def print_findings(findings: list[Finding], root: Path) -> None:
    if not findings:
        print("项目配置校验通过：未发现阻断项或残留警告。")
        return
    print("项目配置校验结果：")
    print(f"- 问题数量：{len(findings)}")
    print(f"- 错误数量：{sum(1 for item in findings if item.severity == 'ERROR')}")
    print(f"- 警告数量：{sum(1 for item in findings if item.severity == 'WARN')}")
    print()
    for finding in findings:
        location = f"{rel(finding.path, root)}: " if finding.path else ""
        print(f"- [{finding.severity}] {finding.code}: {location}{finding.message}")


def main(argv: list[str]) -> int:
    configure_output_encoding()
    args = parse_args(argv)
    root = project_root()
    terms = DEFAULT_FORBIDDEN_TERMS + args.term

    findings: list[Finding] = []
    findings.extend(scan_forbidden_terms(root, terms))
    findings.extend(check_word_inputs(root))
    findings.extend(check_outputs(root, args.allow_outputs))
    findings.extend(check_knowledge_base(root))

    print_findings(findings, root)
    has_error = any(item.severity == "ERROR" for item in findings)
    has_warn = any(item.severity == "WARN" for item in findings)
    return 1 if has_error or (args.strict and has_warn) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
