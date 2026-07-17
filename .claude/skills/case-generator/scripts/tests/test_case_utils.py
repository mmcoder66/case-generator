# -*- coding: utf-8 -*-
"""case_utils 核心纯函数单元测试。"""

from __future__ import annotations

from case_utils import (
    FIXED_CASE_HEADERS,
    infer_case_difficulty_with_reason,
    is_case_header,
)


# ---------------------------------------------------------------------------
# is_case_header
# ---------------------------------------------------------------------------


class TestCaseHeader:
    def test_standard_three_level_header(self) -> None:
        cells = ["一级分组", "二级分组", "三级分组"] + FIXED_CASE_HEADERS
        assert is_case_header(cells) is True

    def test_extended_four_level_header(self) -> None:
        cells = [
            "一级分组",
            "二级分组",
            "三级分组",
            "四级分组",
        ] + FIXED_CASE_HEADERS
        assert is_case_header(cells) is True

    def test_missing_case_name_returns_false(self) -> None:
        # 用例名称被移除后，表头尾部不再等于 FIXED_CASE_HEADERS
        cells = ["一级分组", "二级分组", "三级分组"] + FIXED_CASE_HEADERS[1:]
        assert is_case_header(cells) is False

    def test_duplicate_cell_returns_false(self) -> None:
        cells = [
            "一级分组",
            "一级分组",
            "二级分组",
            "三级分组",
        ] + FIXED_CASE_HEADERS
        assert is_case_header(cells) is False

    def test_group_level_out_of_order_returns_false(self) -> None:
        cells = [
            "二级分组",
            "一级分组",
            "三级分组",
        ] + FIXED_CASE_HEADERS
        assert is_case_header(cells) is False

    def test_empty_list_returns_false(self) -> None:
        assert is_case_header([]) is False


# ---------------------------------------------------------------------------
# infer_case_difficulty_with_reason
#
# 注：骨架项目 difficulty_level_rules.md 的关键字清单清空为 <TODO_*> 占位符，
# 因此以下样例只覆盖"综合评分"路径，使用中性业务词。
# 新项目填入真实关键字后，可在此补充关键字命中类测试。
# ---------------------------------------------------------------------------


def _case(
    title: str = "",
    description: str = "",
    precondition: str = "",
    steps: str = "",
    expectation: str = "",
) -> dict[str, str]:
    """构造最小可用的 case dict，只填难度推断读取的字段。"""
    return {
        "用例名称": title,
        "用例描述": description,
        "前置条件": precondition,
        "用例步骤": steps,
        "预期结果": expectation,
    }


def _numbered_steps(count: int) -> str:
    return "\n".join(f"{index}. 步骤{index}" for index in range(1, count + 1))


def _lines(count: int, prefix: str = "前置") -> str:
    return "\n".join(f"{prefix}{index}" for index in range(1, count + 1))


class TestInferCaseDifficulty:
    def test_score_difficult_high_complexity(self) -> None:
        # 前置 4 条 +2、步骤 6 步 +2、校验点 4 个 +2 → 总分 6 → 困难
        case = _case(
            title="复杂场景验证",
            precondition=_lines(4),
            steps=_numbered_steps(6),
            expectation=_lines(4, prefix="结果"),
        )
        difficulty, reasons = infer_case_difficulty_with_reason(case)
        assert difficulty == "困难"
        assert reasons

    def test_score_difficult_balanced_dimensions(self) -> None:
        # 前置 4 条 +2、步骤 6 步 +2、校验点 2 个 +1 → 总分 5 → 困难
        case = _case(
            title="外部工具对比",
            precondition=_lines(4),
            steps=_numbered_steps(6),
            expectation=_lines(2, prefix="结果"),
        )
        difficulty, reasons = infer_case_difficulty_with_reason(case)
        assert difficulty == "困难"
        assert reasons

    def test_score_normal_medium_complexity(self) -> None:
        # 前置 2 条 +1、步骤 3 步 +1、校验点 2 个 +1 → 总分 3 → 一般
        case = _case(
            title="常规业务流程验证",
            precondition=_lines(2),
            steps=_numbered_steps(3),
            expectation=_lines(2, prefix="结果"),
        )
        difficulty, reasons = infer_case_difficulty_with_reason(case)
        assert difficulty == "一般"
        assert reasons

    def test_score_normal_with_more_verification(self) -> None:
        # 前置 2 条 +1、步骤 3 步 +1、校验点 4 个 +2 → 总分 4 → 一般
        case = _case(
            title="多校验点常规验证",
            precondition=_lines(2),
            steps=_numbered_steps(3),
            expectation=_lines(4, prefix="结果"),
        )
        difficulty, reasons = infer_case_difficulty_with_reason(case)
        assert difficulty == "一般"
        assert reasons

    def test_score_simple_low_complexity(self) -> None:
        # 前置 1 条 +0、步骤 2 步 +0、校验点 1 个 +0 → 总分 0 → 简单
        case = _case(
            title="常规查看操作",
            precondition=_lines(1),
            steps=_numbered_steps(2),
            expectation=_lines(1, prefix="结果"),
        )
        difficulty, reasons = infer_case_difficulty_with_reason(case)
        assert difficulty == "简单"
        assert reasons

    def test_score_simple_field_check(self) -> None:
        # 简单字段类场景（关键字已清空，走评分路径）
        case = _case(
            title="字段校验",
            precondition=_lines(1),
            steps=_numbered_steps(2),
            expectation=_lines(1, prefix="结果"),
        )
        difficulty, reasons = infer_case_difficulty_with_reason(case)
        assert difficulty == "简单"
        assert reasons

    def test_score_difficult_with_extra_steps(self) -> None:
        # 步骤 6 步 +2 是主要困难来源
        case = _case(
            title="多步骤链路验证",
            precondition=_lines(3),
            steps=_numbered_steps(6),
            expectation=_lines(3, prefix="结果"),
        )
        difficulty, reasons = infer_case_difficulty_with_reason(case)
        # 前置 3 +1、步骤 6 +2、校验点 3 +1 → 总分 4 → 一般
        #（验证：单纯长步骤链路不一定到困难，需要叠加更多维度）
        assert difficulty == "一般"
        assert reasons

    def test_ui_case_capped_at_normal(self) -> None:
        # UI 用例即使综合分达到困难，最高也只能是一般
        case = _case(
            title="UI校验页面展示",
            description="UI",
            precondition=_lines(4),
            steps=_numbered_steps(6),
            expectation=_lines(2, prefix="结果"),
        )
        difficulty, reasons = infer_case_difficulty_with_reason(case)
        assert difficulty == "一般"
        assert reasons

    def test_empty_case_returns_simple(self) -> None:
        # 完全空的用例（无任何字段），走评分路径应判为简单
        case = _case()
        difficulty, reasons = infer_case_difficulty_with_reason(case)
        assert difficulty == "简单"
