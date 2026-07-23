# -*- coding: utf-8 -*-
"""覆盖率校验单元测试。

覆盖 ``parse_coverage_tables``、``validate_coverage_references``、
``validate_hard_coverage`` 及其辅助函数的纯函数路径与文件级集成路径。
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest

from case_utils import parse_coverage_tables
import validate_cases
from validate_cases import (
    Issue,
    extract_prd_numbered_items,
    extract_prd_table_items,
    extract_source_doc_path,
    extract_source_section,
    validate_coverage_references,
    validate_hard_coverage,
)


@pytest.fixture(autouse=True)
def _trust_generated_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """让所有用例文件都被视为"生成输出"，绕过对 outputs/origin_exports 的硬路径检查。

    测试用 tmp_path 写临时文件，不在项目根目录下，因此需要替换
    ``is_generated_output_path`` 的判定逻辑。validate_coverage_references
    和 validate_hard_coverage 内部都通过模块级名字引用此函数。
    """
    monkeypatch.setattr(
        validate_cases, "is_generated_output_path", lambda path: True
    )


# ---------------------------------------------------------------------------
# 可复用 DocBlock 替身：与 extract_docx.DocBlock 结构兼容，避免依赖 python-docx
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeBlock:
    kind: str
    text: str
    level: int = 0


# ---------------------------------------------------------------------------
# parse_coverage_tables
# ---------------------------------------------------------------------------


_COVERAGE_MD_TEMPLATE = """# 用例标题

<!--
来源文档：inputs/requirements/raw_docs/prd.docx
来源章节：3.3.1 新增任务管理菜单
-->

---

## 测试用例

| 一级分组 | 二级分组 | 用例名称 | 优先级 | 创建人 | 用例描述 | 前置条件 | 用例步骤 | 预期结果 | 备注 | 用例标签 |
|---|---|---|---|---|---|---|---|---|---|---|
| 模块A | 子模块 | 用例一 | P0 | AI | 正例 | 已登录 | 1. 步骤 | 1. 结果 | 来源：prd | 简单 |
| 模块A | 子模块 | 用例二 | P1 | AI | 正例 | 已登录 | 1. 步骤 | 1. 结果 | 来源：prd | 简单 |

---

## 需求覆盖率对照表

| 需求点 / 验收标准 | 需求描述 | 覆盖用例名称 |
|---|---|---|
| [PRD] 字段定义表-任务名称 | 必填，长度 2-100 字符 | 用例一 |
| [PRD] 状态对照表-草稿 | 查看、提交 | 用例一、用例二 |

"""


class TestParseCoverageTables:
    def test_parses_entries_with_case_name_split(self, tmp_path: Path) -> None:
        md = tmp_path / "sample_testcases.md"
        md.write_text(_COVERAGE_MD_TEMPLATE, encoding="utf-8")

        entries = parse_coverage_tables(md)

        assert len(entries) == 2
        assert entries[0]["requirement_point"] == "[PRD] 字段定义表-任务名称"
        assert entries[0]["requirement_desc"] == "必填，长度 2-100 字符"
        assert entries[0]["case_names"] == ["用例一"]
        assert entries[0]["source_file"] == str(md)
        assert entries[0]["source_line"] == _COVERAGE_MD_TEMPLATE.count(
            "\n", 0, _COVERAGE_MD_TEMPLATE.find("[PRD] 字段定义表-任务名称")
        ) + 1

        # 顿号拆分 + 兼容英文逗号
        assert entries[1]["case_names"] == ["用例一", "用例二"]

    def test_no_coverage_table_returns_empty(self, tmp_path: Path) -> None:
        md = tmp_path / "no_table_testcases.md"
        md.write_text(
            "# 标题\n\n"
            "| 一级分组 | 用例名称 | 优先级 | 创建人 | 用例描述 | 前置条件 | "
            "用例步骤 | 预期结果 | 备注 | 用例标签 |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n"
            "| M | 用例 | P0 | AI | 正例 | x | 1.x | 1.y | 来源：prd | 简单 |\n",
            encoding="utf-8",
        )
        assert parse_coverage_tables(md) == []

    def test_multiple_tables_all_parsed(self, tmp_path: Path) -> None:
        md = tmp_path / "multi_testcases.md"
        md.write_text(
            "## 需求覆盖率对照表\n\n"
            "| 需求点 / 验收标准 | 需求描述 | 覆盖用例名称 |\n"
            "|---|---|---|\n"
            "| A | 描述A | 用例A |\n\n"
            "## 追加记录\n\n"
            "| 需求点 / 验收标准 | 需求描述 | 覆盖用例名称 |\n"
            "|---|---|---|\n"
            "| B | 描述B | 用例B |\n",
            encoding="utf-8",
        )
        entries = parse_coverage_tables(md)
        assert [e["requirement_point"] for e in entries] == ["A", "B"]


# ---------------------------------------------------------------------------
# extract_source_doc_path / extract_source_section
# ---------------------------------------------------------------------------


class TestExtractSource:
    def test_doc_path_extracted(self) -> None:
        metadata = "<!--\n来源文档：inputs/requirements/raw_docs/prd.docx\n-->"
        assert (
            extract_source_doc_path(metadata)
            == "inputs/requirements/raw_docs/prd.docx"
        )

    def test_doc_path_missing_returns_none(self) -> None:
        assert extract_source_doc_path("<!-- 无来源 -->") is None

    def test_section_strips_numeric_prefix(self) -> None:
        metadata = "<!--\n来源章节：3.3.1 新增任务管理菜单\n-->"
        assert extract_source_section(metadata) == "新增任务管理菜单"

    def test_section_strips_chinese_number_prefix(self) -> None:
        metadata = "<!--\n来源章节：三、任务管理\n-->"
        assert extract_source_section(metadata) == "任务管理"

    def test_section_no_prefix_preserved(self) -> None:
        metadata = "<!--\n来源章节：任务管理\n-->"
        assert extract_source_section(metadata) == "任务管理"

    def test_section_missing_returns_none(self) -> None:
        assert extract_source_section("<!-- 无章节 -->") is None


# ---------------------------------------------------------------------------
# validate_coverage_references
# ---------------------------------------------------------------------------


def _make_case(name: str, source_file: str) -> dict[str, str]:
    return {
        "一级分组": "模块",
        "用例名称": name,
        "优先级": "P0",
        "创建人": "AI",
        "用例描述": "正例",
        "前置条件": "x",
        "用例步骤": "1. x",
        "预期结果": "1. y",
        "备注": "来源：prd",
        "用例标签": "简单",
        "_source_file": source_file,
        "_source_line": "5",
        "_headers": [
            "一级分组",
            "用例名称",
            "优先级",
            "创建人",
            "用例描述",
            "前置条件",
            "用例步骤",
            "预期结果",
            "备注",
            "用例标签",
        ],
    }


def _write_case_file_with_coverage(
    path: Path, case_names_in_coverage: list[str]
) -> None:
    """写一个最小可用的生成用例文件，含覆盖率表。"""
    names_line = "、".join(case_names_in_coverage) if case_names_in_coverage else ""
    path.write_text(
        "<!--\n来源文档：inputs/requirements/raw_docs/prd.docx\n"
        "来源章节：3.3.1 新增任务\n生成时间：2024-01-01 00:00:00\n-->\n\n"
        "| 一级分组 | 用例名称 | 优先级 | 创建人 | 用例描述 | 前置条件 | "
        "用例步骤 | 预期结果 | 备注 | 用例标签 |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
        "| M | 存在的用例 | P0 | AI | 正例 | x | 1.x | 1.y | 来源：prd | 简单 |\n\n"
        "## 需求覆盖率对照表\n\n"
        "| 需求点 / 验收标准 | 需求描述 | 覆盖用例名称 |\n"
        "|---|---|---|\n"
        f"| [PRD] A | 描述A | {names_line} |\n",
        encoding="utf-8",
    )


def _put_under_origin_exports(tmp_path: Path, filename: str) -> Path:
    """把文件写到 ``outputs/origin_exports/`` 下，让 is_generated_output_path 通过。"""
    origin = tmp_path / "outputs" / "origin_exports"
    origin.mkdir(parents=True, exist_ok=True)
    return origin / filename


class TestValidateCoverageReferences:
    def test_missing_reference_triggers_error(self, tmp_path: Path) -> None:
        case_file = _put_under_origin_exports(tmp_path, "a_testcases.md")
        _write_case_file_with_coverage(case_file, ["存在的用例", "不存在的用例"])

        cases = [_make_case("存在的用例", str(case_file))]
        issues = validate_coverage_references([case_file], cases)

        errors = [i for i in issues if i.code == "coverage_reference_invalid"]
        assert len(errors) == 1
        assert issues[0].severity == "ERROR"
        assert "不存在的用例" in issues[0].message

    def test_all_references_valid_no_error(self, tmp_path: Path) -> None:
        case_file = _put_under_origin_exports(tmp_path, "b_testcases.md")
        _write_case_file_with_coverage(case_file, ["存在的用例"])

        cases = [_make_case("存在的用例", str(case_file))]
        issues = validate_coverage_references([case_file], cases)

        assert not any(i.code == "coverage_reference_invalid" for i in issues)

    def test_no_coverage_table_warns(self, tmp_path: Path) -> None:
        case_file = _put_under_origin_exports(tmp_path, "c_testcases.md")
        case_file.write_text(
            "<!--\n来源文档：x.docx\n生成时间：2024-01-01 00:00:00\n-->\n\n"
            "| 一级分组 | 用例名称 | 优先级 | 创建人 | 用例描述 | 前置条件 | "
            "用例步骤 | 预期结果 | 备注 | 用例标签 |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n"
            "| M | 用例 | P0 | AI | 正例 | x | 1.x | 1.y | 来源：prd | 简单 |\n",
            encoding="utf-8",
        )
        cases = [_make_case("用例", str(case_file))]
        issues = validate_coverage_references([case_file], cases)

        warns = [i for i in issues if i.code == "coverage_table_missing"]
        assert len(warns) == 1
        assert warns[0].severity == "WARN"

    def test_non_generated_path_skipped(self, tmp_path: Path) -> None:
        # 路径不在 outputs/origin_exports 下，应被跳过
        other = tmp_path / "other_testcases.md"
        _write_case_file_with_coverage(other, ["用例"])
        cases = [_make_case("用例", str(other))]
        issues = validate_coverage_references([other], cases)
        assert issues == []


# ---------------------------------------------------------------------------
# extract_prd_table_items
# ---------------------------------------------------------------------------


class TestExtractPrdTableItems:
    def test_state_table_rows_extracted(self) -> None:
        blocks = [
            _FakeBlock(kind="heading", text="3.3.1 新增任务管理菜单", level=3),
            _FakeBlock(kind="table", text="表格行1：状态 | 可执行操作"),
            _FakeBlock(kind="table", text="表格行2：草稿 | 查看、提交"),
            _FakeBlock(kind="table", text="表格行3：已完成 | 查看、重启"),
        ]
        items = extract_prd_table_items(blocks)
        assert items == [("state_table", "草稿"), ("state_table", "已完成")]

    def test_field_table_rows_extracted(self) -> None:
        blocks = [
            _FakeBlock(kind="table", text="表格行1：字段名称 | 必填 | 校验规则"),
            _FakeBlock(kind="table", text="表格行2：任务名称 | 是 | 2-100"),
            _FakeBlock(kind="table", text="表格行3：任务描述 | 否 | 0-1000"),
        ]
        items = extract_prd_table_items(blocks)
        assert items == [
            ("field_table", "任务名称"),
            ("field_table", "任务描述"),
        ]

    def test_unrecognized_table_skipped(self) -> None:
        blocks = [
            _FakeBlock(kind="table", text="表格行1：章节 | 内容"),
            _FakeBlock(kind="table", text="表格行2：概述 | xxx"),
        ]
        assert extract_prd_table_items(blocks) == []

    def test_multiple_tables_separated_by_heading(self) -> None:
        blocks = [
            _FakeBlock(kind="table", text="表格行1：状态 | 操作"),
            _FakeBlock(kind="table", text="表格行2：草稿 | 提交"),
            _FakeBlock(kind="heading", text="其他章节", level=4),
            _FakeBlock(kind="table", text="表格行1：字段名称 | 必填"),
            _FakeBlock(kind="table", text="表格行2：任务名称 | 是"),
        ]
        items = extract_prd_table_items(blocks)
        assert items == [
            ("state_table", "草稿"),
            ("field_table", "任务名称"),
        ]

    def test_table_row1_resets_current_table(self) -> None:
        # 两个表格之间没有非表格块分隔，靠"表格行1"切分
        blocks = [
            _FakeBlock(kind="table", text="表格行1：状态 | 操作"),
            _FakeBlock(kind="table", text="表格行2：草稿 | 提交"),
            _FakeBlock(kind="table", text="表格行1：字段名称 | 必填"),
            _FakeBlock(kind="table", text="表格行2：任务名称 | 是"),
        ]
        items = extract_prd_table_items(blocks)
        assert items == [
            ("state_table", "草稿"),
            ("field_table", "任务名称"),
        ]


# ---------------------------------------------------------------------------
# extract_prd_numbered_items
# ---------------------------------------------------------------------------


class TestExtractPrdNumberedItems:
    def test_sub_items_extracted(self) -> None:
        blocks = [
            _FakeBlock(kind="heading", text="3.3.1 某章节", level=3),
            _FakeBlock(
                kind="paragraph",
                text=(
                    "功能描述：\n"
                    "一、树形导航\n"
                    "1. 左侧固定宽度，顶部搜索框\n"
                    "2. 层级为产品→原料药/辅料\n"
                    "二、任务列表\n"
                    "1. 状态切换筛选\n"
                ),
            ),
        ]
        keywords = extract_prd_numbered_items(blocks)
        assert "左侧固定宽度" in keywords
        # "层级为产品→原料药/辅料" 超过 10 字会被截断
        assert any(kw.startswith("层级为产品") for kw in keywords)
        assert "状态切换筛选" in keywords

    def test_truncates_to_max_length(self) -> None:
        long_title = "这是一个非常非常非常非常非常非常非常长的子项标题文本"
        blocks = [
            _FakeBlock(
                kind="paragraph",
                text=f"1. {long_title}，后续补充内容\n",
            ),
        ]
        keywords = extract_prd_numbered_items(blocks)
        assert len(keywords) == 1
        assert len(keywords[0]) <= 10

    def test_title_cut_at_boundary_punctuation(self) -> None:
        blocks = [
            _FakeBlock(
                kind="paragraph",
                text="1. 点击依赖图节点跳转，跳转后展示详情。",
            ),
        ]
        keywords = extract_prd_numbered_items(blocks)
        assert keywords == ["点击依赖图节点跳转"]

    def test_no_sub_items_returns_empty(self) -> None:
        blocks = [
            _FakeBlock(kind="heading", text="章节", level=3),
            _FakeBlock(kind="paragraph", text="这是一段无编号的描述性文字。"),
        ]
        assert extract_prd_numbered_items(blocks) == []

    def test_headings_excluded(self) -> None:
        # heading 块不应参与 numbered items 提取
        blocks = [
            _FakeBlock(kind="heading", text="1. 不应被提取", level=4),
        ]
        assert extract_prd_numbered_items(blocks) == []


# ---------------------------------------------------------------------------
# validate_hard_coverage
# ---------------------------------------------------------------------------


def _install_fake_extract_docx(
    monkeypatch: pytest.MonkeyPatch,
    section_blocks: list[_FakeBlock] | None = None,
    raises: Exception | None = None,
) -> None:
    """向 sys.modules 注入 extract_docx 替身，绕过真实 python-docx 依赖。"""
    fake_module = types.ModuleType("extract_docx")

    def _resolve_docx_path(raw_path: str) -> Path:
        return Path(raw_path)

    def _read_docx_blocks(docx_path: Path) -> list[_FakeBlock]:
        if raises is not None:
            raise raises
        return section_blocks or []

    def _extract_section(blocks: list, section: str) -> list:
        if section:
            # 测试场景里 section 不参与切分逻辑，直接返回全部
            return blocks
        return blocks

    fake_module.resolve_docx_path = _resolve_docx_path
    fake_module.read_docx_blocks = _read_docx_blocks
    fake_module.extract_section = _extract_section
    monkeypatch.setitem(sys.modules, "extract_docx", fake_module)


def _write_full_case_file(path: Path, coverage_rows: list[tuple[str, str, str]]) -> None:
    """写一个含元信息和覆盖率表的生成用例文件。"""
    coverage_lines = "\n".join(
        f"| {point} | {desc} | {names} |" for point, desc, names in coverage_rows
    )
    path.write_text(
        "<!--\n"
        "来源文档：inputs/requirements/raw_docs/prd.docx\n"
        "来源章节：3.3.1 新增任务管理菜单\n"
        "生成时间：2024-01-01 00:00:00\n"
        "生成耗时：10 分\n"
        "-->\n\n"
        "| 一级分组 | 用例名称 | 优先级 | 创建人 | 用例描述 | 前置条件 | "
        "用例步骤 | 预期结果 | 备注 | 用例标签 |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
        "| M | 用例 | P0 | AI | 正例 | x | 1.x | 1.y | 来源：prd | 简单 |\n\n"
        "## 需求覆盖率对照表\n\n"
        "| 需求点 / 验收标准 | 需求描述 | 覆盖用例名称 |\n"
        "|---|---|---|\n"
        f"{coverage_lines}\n",
        encoding="utf-8",
    )


class TestValidateHardCoverage:
    def test_uncovered_table_row_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        case_file = _put_under_origin_exports(tmp_path, "hard_testcases.md")
        # 覆盖率表只覆盖了"草稿"，未覆盖"已完成"
        _write_full_case_file(
            case_file,
            [("[PRD] 状态对照表-草稿", "查看、提交", "用例")],
        )

        blocks = [
            _FakeBlock(kind="heading", text="3.3.1 新增任务管理菜单", level=3),
            _FakeBlock(kind="table", text="表格行1：状态 | 操作"),
            _FakeBlock(kind="table", text="表格行2：草稿 | 查看、提交"),
            _FakeBlock(kind="table", text="表格行3：已完成 | 查看、重启"),
        ]
        _install_fake_extract_docx(monkeypatch, section_blocks=blocks)

        issues = validate_hard_coverage([case_file], [_make_case("用例", str(case_file))])
        warns = [i for i in issues if i.code == "prd_table_row_uncovered"]
        assert len(warns) == 1
        assert "已完成" in warns[0].message

    def test_all_table_rows_covered_no_warn(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        case_file = _put_under_origin_exports(tmp_path, "hard2_testcases.md")
        _write_full_case_file(
            case_file,
            [
                ("[PRD] 状态对照表-草稿", "查看、提交", "用例"),
                ("[PRD] 状态对照表-已完成", "查看、重启", "用例"),
            ],
        )

        blocks = [
            _FakeBlock(kind="table", text="表格行1：状态 | 操作"),
            _FakeBlock(kind="table", text="表格行2：草稿 | 查看、提交"),
            _FakeBlock(kind="table", text="表格行3：已完成 | 查看、重启"),
        ]
        _install_fake_extract_docx(monkeypatch, section_blocks=blocks)

        issues = validate_hard_coverage([case_file], [_make_case("用例", str(case_file))])
        assert not any(i.code == "prd_table_row_uncovered" for i in issues)

    def test_uncovered_numbered_item_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        case_file = _put_under_origin_exports(tmp_path, "hard3_testcases.md")
        _write_full_case_file(
            case_file,
            [("[PRD] 树形导航-搜索", "搜索框支持模糊搜索", "用例")],
        )

        blocks = [
            _FakeBlock(
                kind="paragraph",
                text=(
                    "一、树形导航\n"
                    "1. 左侧固定宽度，顶部为搜索框\n"
                    "2. 点击节点筛选右侧任务列表\n"
                ),
            ),
        ]
        _install_fake_extract_docx(monkeypatch, section_blocks=blocks)

        issues = validate_hard_coverage([case_file], [_make_case("用例", str(case_file))])
        # 覆盖率只命中"搜索"，"点击节点"未命中（keyword 截断到 10 字）
        numbered_warns = [i for i in issues if i.code == "prd_numbered_item_uncovered"]
        messages = "\n".join(i.message for i in numbered_warns)
        assert "左侧固定宽度" in messages
        assert "点击节点筛选右侧任务" in messages

    def test_no_source_doc_skipped_silently(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        case_file = _put_under_origin_exports(tmp_path, "hard4_testcases.md")
        # 元信息中无"来源文档"行
        case_file.write_text(
            "<!--\n生成时间：2024-01-01 00:00:00\n生成耗时：10 分\n-->\n\n"
            "| 一级分组 | 用例名称 | 优先级 | 创建人 | 用例描述 | 前置条件 | "
            "用例步骤 | 预期结果 | 备注 | 用例标签 |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n"
            "| M | 用例 | P0 | AI | 正例 | x | 1.x | 1.y | 来源：prd | 简单 |\n",
            encoding="utf-8",
        )
        _install_fake_extract_docx(monkeypatch, section_blocks=[])

        issues = validate_hard_coverage([case_file], [_make_case("用例", str(case_file))])
        # 无来源文档不应产生任何 issue（静默跳过）
        assert issues == []

    def test_docx_unavailable_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        case_file = _put_under_origin_exports(tmp_path, "hard5_testcases.md")
        _write_full_case_file(
            case_file,
            [("[PRD] A", "描述A", "用例")],
        )
        _install_fake_extract_docx(
            monkeypatch, raises=FileNotFoundError("文件不存在")
        )

        issues = validate_hard_coverage([case_file], [_make_case("用例", str(case_file))])
        warns = [i for i in issues if i.code == "prd_doc_unavailable"]
        assert len(warns) == 1
        assert warns[0].severity == "WARN"

    def test_no_coverage_table_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        case_file = _put_under_origin_exports(tmp_path, "hard6_testcases.md")
        case_file.write_text(
            "<!--\n来源文档：inputs/requirements/raw_docs/prd.docx\n"
            "来源章节：3.3.1 新增任务管理菜单\n"
            "生成时间：2024-01-01 00:00:00\n生成耗时：10 分\n-->\n\n"
            "| 一级分组 | 用例名称 | 优先级 | 创建人 | 用例描述 | 前置条件 | "
            "用例步骤 | 预期结果 | 备注 | 用例标签 |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n"
            "| M | 用例 | P0 | AI | 正例 | x | 1.x | 1.y | 来源：prd | 简单 |\n",
            encoding="utf-8",
        )
        _install_fake_extract_docx(monkeypatch, section_blocks=[])

        issues = validate_hard_coverage([case_file], [_make_case("用例", str(case_file))])
        # 覆盖率表缺失已由 coverage_reference_invalid 提示，此处不重复
        assert not any(i.code == "prd_table_row_uncovered" for i in issues)
        assert not any(i.code == "prd_numbered_item_uncovered" for i in issues)
