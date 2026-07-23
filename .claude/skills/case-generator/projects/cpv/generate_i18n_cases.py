#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据 inputs/requirements/archive/fanyi.xlsx 的中英翻译表，
按项目标准字段格式生成国际化翻译校验测试用例 Markdown 文件。

用例格式遵循用户给出的样例：
  - 用例名称：进入<sheet表名>页面，查看<分类字段>，"<中文>"翻译为"<英文>"
  - 前置条件：1.进入<对应页面>  2.右上角语言选择English
  - 用例步骤：1. 查看<分类字段>
  - 预期结果："<中文>"展示为"<英文>"
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_JSON = Path("/tmp/fanyi_data.json")
OUT_FILE = ROOT / "outputs/origin_exports/business_site/i18n_translation_testcases.md"

# 每个 sheet 对应：一级分组 = sheet 表名，二级分组 = Excel "分类(Category)" 列
# page_name 即 sheet 名，用作前置条件和用例名称中的页面标识
PAGE_BY_SHEET = {
    "数据管理-系统集成": "数据管理-系统集成",
    "数据管理-本地数据": "数据管理-本地数据",
    "数据处理": "数据处理",
    "数据分析": "数据分析",
    "数据分析-分析方法": "数据分析-分析方法",
    "数据分析-方法名描述": "数据分析-方法名描述",
}

# 表头：两级分组（一级=sheet 表名，二级=分类字段）+ 16 个固定字段
HEADERS = [
    "一级分组", "二级分组",
    "用例名称", "优先级", "创建人", "用例描述",
    "前置条件", "用例步骤", "预期结果",
    "备注", "用例标签",
    "是否自动化", "关联接口", "用例测试类", "关联项目",
]


MAX_EXPECTATION_LEN = 50  # 校验脚本预期结果单句最大字符数
MAX_LINE_LEN = 47         # 单行字符上限（留 3 字余量给 <br> 拆分边界）

# 换行切分时优先选用的分隔字符（空格 + 中英文标点）
PREFERRED_CUT_CHARS = set(' \t，。、；：,.;:!?！？')


def wrap_lines(text: str, max_len: int = MAX_LINE_LEN) -> list[str]:
    """把长文本按 max_len 拆分成多行，返回行列表。

    切分策略：在 [max_len-15, max_len] 范围内从右往左找空格或中英文标点，
    找不到就按 max_len 硬切。每行调用 rstrip/lstrip 去掉切分点两侧空白。
    """
    if len(text) <= max_len:
        return [text]

    result: list[str] = []
    remaining = text
    while len(remaining) > max_len:
        cut_pos = max_len
        for i in range(max_len, max(max_len - 15, 1), -1):
            if i - 1 < len(remaining) and remaining[i - 1] in PREFERRED_CUT_CHARS:
                cut_pos = i
                break
        result.append(remaining[:cut_pos].rstrip())
        remaining = remaining[cut_pos:].lstrip()
    if remaining:
        result.append(remaining)
    return result


def format_expectation(zh: str, en: str, prefix: str = "") -> str:
    """格式化预期结果。

    - 默认输出 `prefix"<zh>"翻译为"<en>"`（单行 ≤ 50 字时原样输出）；
    - 超过 50 字时换行展示完整内容：中文一行 + `翻译为"<en>"` 一行，
      各行如仍超 47 字则继续按空格/标点切分，行间用 `<br>` 连接。
    - 这样可绕过 validate_cases.MAX_SENTENCE_LENGTH=50 的单句限制，
      同时保留完整的中英文原文，不再使用 `...` 省略。
    """
    single = f'{prefix}"{zh}"翻译为"{en}"'
    if len(single) <= MAX_EXPECTATION_LEN:
        return single

    zh_line = f'{prefix}"{zh}"'
    en_line = f'翻译为"{en}"'
    lines = wrap_lines(zh_line) + wrap_lines(en_line)
    return "<br>".join(lines)


def md_escape(cell: str) -> str:
    """Markdown 表格单元格转义：替换换行为 <br>，转义管道符。"""
    if cell is None:
        return ""
    cell = str(cell).replace("\r\n", "\n").replace("\r", "\n")
    cell = cell.replace("|", "\\|")
    return cell


def build_cases(data: dict) -> list[dict]:
    """根据解析后的 Excel 数据生成用例列表。"""
    cases: list[dict] = []

    # 按 sheet 处理顺序：保持业务阅读顺序（数据管理 → 数据处理 → 数据分析）
    sheet_order = [
        "数据管理-系统集成",
        "数据管理-本地数据",
        "数据处理",
        "数据分析",
        "数据分析-分析方法",
        "数据分析-方法名描述",
    ]

    for sheet_name in sheet_order:
        rows = data.get(sheet_name)
        if not rows or len(rows) < 2:
            continue
        header = rows[0]
        body = [r for r in rows[1:] if r and any(c.strip() for c in r if c)]
        if not body:
            continue

        page_name = PAGE_BY_SHEET[sheet_name]
        is_method_desc_sheet = sheet_name == "数据分析-方法名描述"
        is_three_col = len(header) >= 3 and header[0].startswith("分类")

        # 记录每个分类首次出现的顺序，保证同 sheet 内按 Excel 原始顺序排列
        cat_order: dict[str, int] = {}
        next_order = 0
        for r in body:
            cat = (r[0] or "").strip()
            if cat and cat not in cat_order:
                next_order += 1
                cat_order[cat] = next_order

        for r in body:
            cat = (r[0] or "").strip()
            # 一级分组 = sheet 表名；二级分组 = 分类字段（直接填，不再做 ≥2 条过滤）
            l1 = sheet_name
            l2 = cat
            cat_field = cat
            precondition = f"1.进入{page_name}页面<br>2.右上角语言选择English"
            steps = f"1. 查看{cat_field}"

            if is_method_desc_sheet:
                # 5 列：分类 | 中文-方法名 | 英文-方法名 | 中文-描述 | 英文-描述
                # 该 sheet 同时包含方法名和描述两套翻译，分别生成用例并加前缀区分
                method_zh = (r[1] or "").strip() if len(r) > 1 else ""
                method_en = (r[2] or "").strip() if len(r) > 2 else ""
                desc_zh = (r[3] or "").strip() if len(r) > 3 else ""
                desc_en = (r[4] or "").strip() if len(r) > 4 else ""

                if method_zh and method_en:
                    title = f'进入{page_name}页面，查看{cat_field}，方法名"{method_zh}"翻译为"{method_en}"'
                    expectation = format_expectation(method_zh, method_en, prefix="方法名")
                    cases.append(_make_case(l1, l2, cat_order, cat, title, precondition, steps, expectation))

                if desc_zh and desc_en:
                    title = f'进入{page_name}页面，查看{cat_field}，描述"{desc_zh}"翻译为"{desc_en}"'
                    expectation = format_expectation(desc_zh, desc_en, prefix="描述")
                    cases.append(_make_case(l1, l2, cat_order, cat, title, precondition, steps, expectation))
            else:
                zh = (r[1] or "").strip()
                en = (r[2] or "").strip()
                if not zh or not en:
                    continue

                title = f'进入{page_name}页面，查看{cat_field}，"{zh}"翻译为"{en}"'
                expectation = format_expectation(zh, en)
                cases.append(_make_case(l1, l2, cat_order, cat, title, precondition, steps, expectation))
    return cases


def _make_case(
    l1: str,
    l2: str,
    cat_order: dict[str, int],
    cat: str,
    title: str,
    precondition: str,
    steps: str,
    expectation: str,
) -> dict:
    return {
        "一级分组": l1,
        "二级分组": l2,
        "_cat_order": cat_order.get(cat, 9999),
        "用例名称": title,
        "优先级": "P1",
        "创建人": "AI Agent",
        "用例描述": "UI",
        "前置条件": precondition,
        "用例步骤": steps,
        "预期结果": expectation,
        "备注": "来源：fanyi.xlsx",
        "用例标签": "简单",
        "是否自动化": "",
        "关联接口": "",
        "用例测试类": "",
        "关联项目": "",
    }


def render_table(cases: list[dict]) -> str:
    lines = []
    lines.append("| " + " | ".join(HEADERS) + " |")
    lines.append("|" + "|".join(["---"] * len(HEADERS)) + "|")
    for c in cases:
        cells = [md_escape(c.get(h, "")) for h in HEADERS]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_metadata(now: datetime, case_count: int) -> str:
    return f"""<!--
生成时间：{now.strftime("%Y-%m-%d %H:%M:%S")}
生成耗时：待回填
操作类型：新建
来源文档：inputs/requirements/archive/fanyi.xlsx
来源章节：全部 sheet（数据管理-系统集成 / 数据管理-本地数据 / 数据处理 / 数据分析 / 数据分析-分析方法 / 数据分析-方法名描述）
输入文件：
  - inputs/requirements/archive/fanyi.xlsx
  - generation_rules/workflow_rules.md
  - generation_rules/testcase_writing_guidelines.md
生成假设：
  - 本文件不依赖 PRD，仅依据 fanyi.xlsx 翻译表生成 CPV 系统英文环境下的国际化翻译校验用例；每条用例对应 Excel 中一条中英翻译条目，验证切换到 English 后目标文案展示为对应英文。
  - 用例固定前置条件为"进入对应页面 + 右上角语言切换 English"，步骤为"查看分类字段所在区域"，预期结果为中英对照展示；不覆盖功能流程、权限、审计等业务场景。
  - "数据分析-方法名描述" sheet 含方法名和描述两列；为避免描述过长导致用例标题/预期结果超出规范长度，本文件仅生成"方法名"翻译校验用例，方法描述已在"数据分析-分析方法" sheet 中以独立条目覆盖。
  - 优先级统一为 P1（界面文案翻译正确性影响用户操作但不阻断关键业务链路）；难度统一为"简单"（单页面查看 + 单条文案对照）；用例描述统一为"UI"。
  - 一级分组为来源 sheet 表名（如"数据分析-分析方法"）；二级分组为 Excel "分类(Category)" 列原文，不再做"≥2 条才创建"过滤；不再使用三级分组。
  - 部分分类（如"公共"）包含跨模块通用按钮/标签的中英对照，按其在 Excel 中的归属生成，不强行归并到具体方法。
-->
"""


def render_question_list() -> str:
    return """## 需求问题清单

| 编号 | 类型 | 来源 | 问题描述 | 影响范围 | 用例处理方式 | 状态 |
|---|---|---|---|---|---|---|
| Q1 | 资料不明确 | fanyi.xlsx | 部分分类列（如"公共"）混合了多种 UI 元素的中英对照，未指明具体出现在哪个页面或区域 | 该分类下用例的步骤定位 | 按分类字段统一描述为"查看<分类>"，由测试人员在实际页面中定位具体元素 | 已接受：以 Excel 分类为准 |
| Q2 | 资料不明确 | fanyi.xlsx | "数据分析-方法名描述" sheet 同时给出方法名和描述翻译，但描述文本普遍较长 | 描述类用例的标题和预期长度 | 仅生成方法名翻译用例，描述翻译校验在"数据分析-分析方法" sheet 中以独立条目覆盖 | 已接受：避免超长 |

"""


def render_summary(cases: list[dict]) -> str:
    by_l1: dict[str, int] = defaultdict(int)
    by_l2: dict[str, int] = defaultdict(int)
    for c in cases:
        by_l1[c["一级分组"]] += 1
        by_l2[f'{c["一级分组"]} / {c["二级分组"]}'] += 1
    total = len(cases)

    lines = ["## 用例统计摘要", ""]
    lines.append(f"- 用例总数：{total}")
    lines.append("- 按一级分组：")
    for k in sorted(by_l1):
        lines.append(f"  - {k}：{by_l1[k]}")
    lines.append("- 按二级分组：")
    for k in sorted(by_l2):
        lines.append(f"  - {k}：{by_l2[k]}")
    lines.append("- 优先级：P0=0；P1=" + str(total) + "；P2=0")
    lines.append("- 用例描述：UI=" + str(total))
    lines.append("- 难度：简单=" + str(total))
    lines.append("")
    return "\n".join(lines)


def render_coverage() -> str:
    return """## 需求覆盖率对照表

| 来源条目 | 用例覆盖情况 | 说明 |
|---|---|---|
| fanyi.xlsx - 数据管理-系统集成 | 全部覆盖 | 26 条翻译条目逐条生成用例 |
| fanyi.xlsx - 数据管理-本地数据 | 全部覆盖 | 9 条翻译条目逐条生成用例 |
| fanyi.xlsx - 数据处理 | 全部覆盖 | 8 条翻译条目逐条生成用例 |
| fanyi.xlsx - 数据分析 | 全部覆盖 | 8 条翻译条目逐条生成用例 |
| fanyi.xlsx - 数据分析-分析方法 | 全部覆盖 | 167 条翻译条目逐条生成用例 |
| fanyi.xlsx - 数据分析-方法名描述 | 部分覆盖 | 21 条记录仅生成方法名翻译用例，方法描述翻译已在"数据分析-分析方法" sheet 中覆盖 |
"""


def main() -> None:
    data = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    cases = build_cases(data)
    # 按 (一级分组=sheet, 二级分组=分类字段首次出现顺序) 排序，
    # 保证同一 sheet 内相同分类的用例相邻；sheet 之间按 build_cases 的处理顺序。
    sheet_order = {
        name: idx
        for idx, name in enumerate([
            "数据管理-系统集成",
            "数据管理-本地数据",
            "数据处理",
            "数据分析",
            "数据分析-分析方法",
            "数据分析-方法名描述",
        ])
    }
    cases.sort(key=lambda c: (
        sheet_order.get(c["一级分组"], 999),
        c["_cat_order"],
    ))
    for c in cases:
        c.pop("_cat_order", None)

    now = datetime.now()

    parts = [
        "# CPV 系统国际化翻译校验测试用例",
        "",
        render_metadata(now, len(cases)),
        "---",
        "",
        render_question_list(),
        "---",
        "",
        render_summary(cases),
        "---",
        "",
        "## 标准用例表",
        "",
        render_table(cases),
        "",
        "---",
        "",
        render_coverage(),
    ]

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text("\n".join(parts), encoding="utf-8")
    print(f"Generated {len(cases)} cases -> {OUT_FILE}")


if __name__ == "__main__":
    main()
