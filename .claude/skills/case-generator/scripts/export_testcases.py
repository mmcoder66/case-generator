#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用途：
    将 Markdown 测试用例表格导出为 Excel xlsx 文件，便于评审、归档或交付。
    脚本会解析标准表头的测试用例表格，并生成带冻结表头、列宽和自动筛选的工作簿。

默认读取：
    outputs/origin_exports/**/*_testcases.md

默认输出：
    outputs/excel_exports/<site_type>/测试用例导出_YYYYMMDD_HHMMSS.xlsx

适用场景：
    - 将 Agent 生成在 outputs/origin_exports/ 的用例导出为 Excel。
    - 使用 --source 导出指定模块或指定目录的 Markdown 用例。
    - 未指定 --output 时，按 business_constants.SITE_TYPES 分类输出。
    - 导出前自动执行完整校验；存在 ERROR 时停止导出。
    - 使用 --strict 在存在 ERROR 或 WARN 时都停止导出。
    - 使用 --started-at 在单文件导出成功后回填 Markdown 中的"生成耗时"行；
      回填只改元信息那一行，不触碰用例表格，因此不再二次校验。
    - `--started-at`（不带值，推荐）从元信息块的"生成时间"行自动读取起点，
      保证两个字段同源，避免手传错值；也可显式传入时间。

导出前校验：
    复用 validate_cases.py 的完整校验规则，避免校验失败的用例被导出。

示例：
    python scripts/export_testcases.py
    python scripts/export_testcases.py --source outputs/origin_exports/<site_type>/<module_name>_testcases.md
    python scripts/export_testcases.py --source outputs/origin_exports/<site_type>/<module_name>_testcases.md --strict -o <module_name>_testcases.xlsx
    python scripts/export_testcases.py --source outputs/origin_exports/<site_type>/<module_name>_testcases.md --started-at
    python scripts/export_testcases.py --source outputs/origin_exports/<site_type>/<module_name>_testcases.md --started-at "YYYY-MM-DD HH:MM:SS"

本脚本只使用 Python 标准库，不需要额外安装依赖。

改动本文件后，请运行 `python -m pytest scripts/tests/ -v` 确认无回归。
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from business_constants import (
    COLUMN_WIDTH_BY_HEADER,
    CREATOR_NAME,
    SHEET_NAME,
    SITE_TYPES,
)
from case_utils import (
    EXPECTED_HEADERS,
    apply_difficulty_tags,
    build_source_path,
    configure_output_encoding,
    discover_case_files,
    ensure_under,
    expected_headers_for,
    group_headers_for_count,
    group_headers_from_case,
    parse_case_file,
    project_root,
    read_text_file,
    windows_long_path,
    write_text_file,
)
from validate_cases import (
    format_issue,
    has_blocking_issues,
    run_all_validations,
)

INVALID_XML_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")

# Excel 样式索引（对应 styles_xml 中 cellXfs 的顺序）
_STYLE_HEADER = 1    # 表头：加粗、绿色背景、居中
_STYLE_DATA = 2      # 数据行：带边框、顶部对齐、自动换行

DURATION_LINE_RE = re.compile(r"^(生成耗时：).*$", re.MULTILINE)
DURATION_PLACEHOLDER_RE = re.compile(r"生成耗时：(?:待回填|约|预计)")
GENERATION_TIME_RE = re.compile(
    r"^生成时间：(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)",
    re.MULTILINE,
)

# 每列固定列宽集中在 business_constants.COLUMN_WIDTH_BY_HEADER；
# 动态分组列未显式配置时使用 GROUP_COLUMN_WIDTH 兜底。
GROUP_COLUMN_WIDTH = 16


def column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def safe_xml_text(value: str) -> str:
    value = INVALID_XML_CHARS.sub("", value)
    return escape(value, entities={'"': "&quot;", "'": "&apos;"})


def cell_xml(row_index: int, column_index: int, value: str, style_index: int) -> str:
    reference = f"{column_name(column_index)}{row_index}"
    text = safe_xml_text(value)
    return (
        f'<c r="{reference}" t="inlineStr" s="{style_index}">'
        f'<is><t xml:space="preserve">{text}</t></is></c>'
    )


def row_xml(row_index: int, values: list[str], style_index: int) -> str:
    cells = [
        cell_xml(row_index, column_index, value, style_index)
        for column_index, value in enumerate(values, start=1)
    ]
    height = 24 if row_index == 1 else 64
    return f'<row r="{row_index}" ht="{height}" customHeight="1">{"".join(cells)}</row>'


def headers_for_cases(cases: list[dict[str, str]]) -> list[str]:
    max_group_count = max(
        (len(group_headers_from_case(case)) for case in cases),
        default=3,
    )
    group_headers = group_headers_for_count(max_group_count)
    return expected_headers_for(group_headers)


def display_values_for_excel(
    headers: list[str], case: dict[str, str], previous_groups: tuple[str, ...] | None
) -> tuple[list[str], tuple[str, ...]]:
    """Blank repeated group names to make the exported sheet easier to scan."""
    group_headers = group_headers_from_case(case)
    current_groups = tuple(case.get(header, "") for header in group_headers)
    values: list[str] = []

    for header in headers:
        value = case.get(header, "")
        if header in group_headers and previous_groups is not None:
            group_index = group_headers.index(header)
            if current_groups[: group_index + 1] == previous_groups[: group_index + 1]:
                value = ""
        values.append(value)

    return values, current_groups


def worksheet_xml(headers: list[str], cases: list[dict[str, str]]) -> str:
    max_row = len(cases) + 1
    max_col = len(headers)
    dimension = f"A1:{column_name(max_col)}{max_row}"
    rows = [row_xml(1, headers, _STYLE_HEADER)]
    previous_groups: tuple[str, ...] | None = None
    for row_index, case in enumerate(cases, start=2):
        values, previous_groups = display_values_for_excel(headers, case, previous_groups)
        rows.append(row_xml(row_index, values, _STYLE_DATA))

    column_widths = [
        COLUMN_WIDTH_BY_HEADER.get(header, GROUP_COLUMN_WIDTH) for header in headers
    ]
    cols = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(column_widths, start=1)
    )

    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="{dimension}"/>
  <sheetViews>
    <sheetView workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
    </sheetView>
  </sheetViews>
  <cols>{cols}</cols>
  <sheetData>{"".join(rows)}</sheetData>
  <autoFilter ref="{dimension}"/>
</worksheet>'''


def styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF38761D"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFD9EAD3"/></left>
      <right style="thin"><color rgb="FFD9EAD3"/></right>
      <top style="thin"><color rgb="FFD9EAD3"/></top>
      <bottom style="thin"><color rgb="FFD9EAD3"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center" wrapText="1"/>
    </xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1">
      <alignment vertical="top" wrapText="1"/>
    </xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''


def write_xlsx(output_path: Path, cases: list[dict[str, str]]) -> None:
    headers = headers_for_cases(cases)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    files = {
        "[Content_Types].xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>''',
        "xl/workbook.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="{SHEET_NAME}" sheetId="1" r:id="rId1"/></sheets>
</workbook>''',
        "xl/_rels/workbook.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>''',
        "xl/worksheets/sheet1.xml": worksheet_xml(headers, cases),
        "xl/styles.xml": styles_xml(),
        "docProps/core.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:dcmitype="http://purl.org/dc/dcmitype/"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>{CREATOR_NAME}</dc:creator>
  <cp:lastModifiedBy>{CREATOR_NAME}</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>''',
        "docProps/app.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
    xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Python 标准库</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>工作表</vt:lpstr></vt:variant><vt:variant><vt:i4>1</vt:i4></vt:variant></vt:vector></HeadingPairs>
  <TitlesOfParts><vt:vector size="1" baseType="lpstr"><vt:lpstr>{SHEET_NAME}</vt:lpstr></vt:vector></TitlesOfParts>
</Properties>''',
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        windows_long_path(output_path), "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for archive_path, content in files.items():
            archive.writestr(archive_path, content)


def default_output_path(output_dir: Path, source_file: Path | None = None) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if source_file is not None:
        return output_dir / f"{source_file.stem}.xlsx"
    return output_dir / f"测试用例导出_{timestamp}.xlsx"


def site_type_for_case_file(case_file: Path, origin_dir: Path) -> str | None:
    try:
        relative = case_file.resolve().relative_to(origin_dir.resolve())
    except ValueError:
        return None

    if relative.parts and relative.parts[0] in SITE_TYPES:
        return relative.parts[0]
    return None


def group_case_files_by_site(
    case_files: list[Path], origin_dir: Path
) -> dict[str | None, list[Path]]:
    groups: dict[str | None, list[Path]] = {}
    for case_file in case_files:
        site_type = site_type_for_case_file(case_file, origin_dir)
        groups.setdefault(site_type, []).append(case_file)
    return groups


def parse_started_at(value: str) -> datetime | str:
    # argparse 对 nargs="?" 的 const 也会经过 type 转换，需放行 "auto" sentinel
    if value == "auto":
        return "auto"
    text = value.strip()
    if text.isdigit():
        try:
            return datetime.fromtimestamp(int(text))
        except (ValueError, OSError) as error:
            raise argparse.ArgumentTypeError(f"无效的 Unix 时间戳：{text}（{error}）") from error

    normalized = text.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            pass

    raise argparse.ArgumentTypeError(
        "开始时间格式必须为 Unix 秒级时间戳、YYYY-MM-DD HH:MM 或 YYYY-MM-DD HH:MM:SS"
    )


def format_duration(started_at: datetime, ended_at: datetime) -> str:
    elapsed_seconds = max(0, int((ended_at - started_at).total_seconds()))
    minutes, seconds = divmod(elapsed_seconds, 60)
    if minutes == 0:
        return f"{seconds} 秒"
    if seconds == 0:
        return f"{minutes} 分钟"
    return f"{minutes} 分 {seconds} 秒"


def _count_table_lines(content: str) -> int:
    return sum(1 for line in content.splitlines() if line.lstrip().startswith("|"))


def backfill_duration(source: Path, duration_text: str) -> bool:
    """回填"生成耗时"行；通过对比表格行数防止意外破坏用例表。

    回填只修改元信息块中"生成耗时"那一行，不触碰任何用例表格字段，
    因此无需重新运行 validate_cases.py。
    """
    content = read_text_file(source)
    replacement = f"生成耗时：{duration_text}（从开始读取资料到校验和 Excel 导出完成）"

    if not DURATION_LINE_RE.search(content):
        raise RuntimeError("未找到“生成耗时：”元信息行，无法回填耗时")

    table_lines_before = _count_table_lines(content)
    updated = DURATION_LINE_RE.sub(replacement, content, count=1)
    table_lines_after = _count_table_lines(updated)

    if table_lines_before != table_lines_after:
        raise RuntimeError("回填耗时后用例表格行数发生变化，已拒绝写入，请检查源文件")

    if updated == content:
        return False

    write_text_file(source, updated)
    return True


def ensure_no_duration_placeholder(source: Path) -> None:
    content = read_text_file(source)
    if DURATION_PLACEHOLDER_RE.search(content):
        raise RuntimeError("Markdown 中仍存在待回填、约或预计耗时，请检查生成耗时元信息")


def read_started_at_from_metadata(source: Path) -> datetime:
    """从元信息块的"生成时间"行读取起点，保证与标签字段同源，避免手传错值。"""
    content = read_text_file(source)
    match = GENERATION_TIME_RE.search(content)
    if not match:
        raise RuntimeError(
            "元信息中找不到 “生成时间：YYYY-MM-DD HH:MM[:SS]” 行，"
            "无法自动推断 --started-at；请改用 --started-at \"<时间>\" 显式传入"
        )
    return parse_started_at(match.group(1))


def parse_args(argv: list[str]) -> argparse.Namespace:
    root = project_root()
    parser = argparse.ArgumentParser(
        description="将 Markdown 测试用例表格导出为 xlsx 文件"
    )
    parser.add_argument(
        "--source",
        default=str(root / "outputs" / "origin_exports"),
        help="输入文件或目录，默认扫描 outputs/origin_exports/**/*_testcases.md",
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "输出文件名或路径，仅支持 --source 指向单个 Markdown 文件时使用；"
            "相对路径会保存到 source 所属站点的 outputs/excel_exports/<site_type>/"
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="发现 ERROR 或 WARN 时都停止导出；默认只在 ERROR 时停止",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="导出成功后仅清理本次输出目录下的临时汇总 Excel：测试用例导出_*.xlsx",
    )
    parser.add_argument(
        "--started-at",
        nargs="?",
        const="auto",
        default=None,
        type=parse_started_at,
        help=(
            "可选，触发导出成功后回填 Markdown 中的“生成耗时”行。"
            "不接值时（推荐，即 --started-at）从元信息块的“生成时间”行自动读取起点，"
            "保证两个字段同源，避免手传错值；"
            "也可显式传入 Unix 秒级时间戳、YYYY-MM-DD HH:MM 或 YYYY-MM-DD HH:MM:SS。"
            "仅在 --source 指向单个 Markdown 文件时可用"
        ),
    )
    return parser.parse_args(argv)


def clean_old_exports(output_dir: Path, keep: Path) -> list[Path]:
    keep = keep.resolve()
    removed: list[Path] = []
    for existing in output_dir.glob("测试用例导出_*.xlsx"):
        if existing.resolve() == keep:
            continue
        try:
            Path(windows_long_path(existing)).unlink()
            removed.append(existing)
        except OSError as exc:
            # 文件可能被 Excel 等进程占用，跳过并提示，不中断导出流程
            print(f"警告：无法删除历史文件 {existing}：{exc}", file=sys.stderr)
    return removed


def build_output_path(
    output_arg: str | None, output_dir: Path, site_type: str | None = None
) -> Path:
    if not output_arg:
        return default_output_path(output_dir)

    output_path = Path(output_arg)
    if not output_path.is_absolute():
        if output_path.parts and output_path.parts[0] in SITE_TYPES:
            output_path = output_dir / output_path
        else:
            site_output_dir = output_dir / site_type if site_type else output_dir
            output_path = site_output_dir / output_path
    if output_path.suffix.lower() != ".xlsx":
        output_path = output_path.with_suffix(".xlsx")
    return output_path


def main(argv: list[str]) -> int:
    configure_output_encoding()
    root = project_root()
    output_dir = root / "outputs" / "excel_exports"
    origin_dir = root / "outputs" / "origin_exports"
    args = parse_args(argv)

    try:
        source = ensure_under(build_source_path(args.source, root), root, "输入路径")
        case_files = discover_case_files(source)
    except (FileNotFoundError, ValueError) as error:
        print(f"导出失败：{error}", file=sys.stderr)
        return 1

    if not case_files:
        print("导出失败：未找到任何测试用例 Markdown 文件", file=sys.stderr)
        return 1

    if args.started_at is not None and len(case_files) != 1:
        print(
            "导出失败：--started-at 仅在 --source 指向单个 Markdown 文件时可用",
            file=sys.stderr,
        )
        return 1

    if args.started_at is not None:
        target = case_files[0]
        try:
            target.resolve().relative_to(origin_dir.resolve())
        except ValueError:
            print(
                "导出失败：--started-at 仅允许回填 outputs/origin_exports/ 下的 Markdown 文件，"
                "不得用于 testcase_templates 等只读目录",
                file=sys.stderr,
            )
            return 1
        if not DURATION_LINE_RE.search(read_text_file(target)):
            print(
                "导出失败：--started-at 找不到元信息中的“生成耗时：”行，"
                "请确认 Markdown 是按 SKILL.md 模板生成的",
                file=sys.stderr,
            )
            return 1

    # 解析实际起点：auto 模式从元信息块的"生成时间"行读，显式值直接用
    started_at_resolved: datetime | None = None
    if args.started_at == "auto":
        try:
            started_at_resolved = read_started_at_from_metadata(case_files[0])
        except (RuntimeError, argparse.ArgumentTypeError) as error:
            print(f"导出失败：{error}", file=sys.stderr)
            return 1
    elif args.started_at is not None:
        started_at_resolved = args.started_at

    groups = group_case_files_by_site(case_files, origin_dir)
    if args.output:
        if len(case_files) != 1:
            print(
                "导出失败：指定 -o/--output 时，--source 必须指向单个 Markdown 用例文件；"
                "批量或目录导出请不要使用 -o。",
                file=sys.stderr,
            )
            return 1
        site_type = site_type_for_case_file(case_files[0], origin_dir)
        try:
            output_path = ensure_under(
                build_output_path(args.output, output_dir, site_type),
                output_dir,
                "输出路径",
            )
        except ValueError as error:
            print(f"导出失败：{error}", file=sys.stderr)
            return 1
        export_groups = [(site_type or "未分类", case_files, output_path)]
    else:
        export_groups = []
        for site_type, files in sorted(groups.items(), key=lambda item: item[0] or ""):
            group_output_dir = output_dir / site_type if site_type else output_dir
            # 单文件时用 MD 文件名，多文件合并时用时间戳
            source_file = files[0] if len(files) == 1 else None
            export_groups.append((site_type or "未分类", files, default_output_path(group_output_dir, source_file)))

    exported_count = 0
    for group_name, group_files, output_path in export_groups:
        cases: list[dict[str, str]] = []
        parse_warnings: list[str] = []
        for case_file in group_files:
            parsed_cases, file_warnings = parse_case_file(case_file)
            cases.extend(parsed_cases)
            parse_warnings.extend(file_warnings)

        if not cases:
            print(f"导出失败：{group_name} 未解析到测试用例", file=sys.stderr)
            for warning in parse_warnings:
                print(f"- {warning}", file=sys.stderr)
            return 1

        validation_issues = run_all_validations(group_files, cases, parse_warnings)

        if validation_issues:
            print(f"导出前校验结果（{group_name}）：")
            for issue in validation_issues:
                print(f"- {format_issue(issue)}")
            if has_blocking_issues(validation_issues, strict=args.strict):
                if args.strict:
                    print(
                        "已启用 --strict，存在 ERROR 或 WARN，停止导出。",
                        file=sys.stderr,
                    )
                else:
                    print("存在 ERROR，停止导出。", file=sys.stderr)
                return 1
            print()

        cases = apply_difficulty_tags(cases)
        try:
            write_xlsx(output_path, cases)
        except OSError as error:
            print(
                f"导出失败：无法写入 {output_path}，请确认文件未被 Excel 打开且目录可写：{error}",
                file=sys.stderr,
            )
            return 1

        removed_files: list[Path] = []
        if args.clean:
            removed_files = clean_old_exports(output_path.parent, output_path)

        modules = sorted(
            {
                " / ".join(
                    group
                    for group in (
                        case.get(header, "")
                        for header in group_headers_from_case(case)
                    )
                    if group
                )
                for case in cases
                if case.get("一级分组")
            }
        )
        print("已导出测试用例 Excel：")
        print(f"- 站点分类：{group_name}")
        print(f"- 文件路径：{output_path}")
        print(f"- 用例数量：{len(cases)}")
        print(f"- 覆盖模块：{', '.join(modules)}")
        if args.clean:
            print(f"- 已清理历史文件：{len(removed_files)} 个")
        exported_count += 1

    if exported_count > 1:
        print(f"共导出 {exported_count} 个 Excel 文件。")

    if started_at_resolved is not None:
        ended_at = datetime.now()
        raw_elapsed = int((ended_at - started_at_resolved).total_seconds())
        if raw_elapsed <= 0:
            print(
                f"导出失败：生成时间 {started_at_resolved.strftime('%Y-%m-%d %H:%M:%S')} "
                f"不早于当前时间 {ended_at.strftime('%Y-%m-%d %H:%M:%S')}，"
                f"耗时计算为 {raw_elapsed} 秒，可能不是真实系统时间；"
                f"请通过 date \"+%Y-%m-%d %H:%M:%S\" 命令获取真实时间后更新元信息块",
                file=sys.stderr,
            )
            return 1
        duration_text = format_duration(started_at_resolved, ended_at)
        try:
            backfill_duration(case_files[0], duration_text)
            ensure_no_duration_placeholder(case_files[0])
        except RuntimeError as error:
            print(f"回填耗时失败：{error}", file=sys.stderr)
            return 1
        print(f"已回填生成耗时：{duration_text}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
