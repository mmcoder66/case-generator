# -*- coding: utf-8 -*-
"""export_testcases 核心纯函数单元测试。"""

from __future__ import annotations

from export_testcases import safe_xml_text


class TestSafeXmlText:
    def test_ampersand_escaped(self) -> None:
        assert safe_xml_text("a&b") == "a&amp;b"

    def test_less_than_escaped(self) -> None:
        assert safe_xml_text("a<b") == "a&lt;b"

    def test_greater_than_escaped(self) -> None:
        assert safe_xml_text("a>b") == "a&gt;b"

    def test_double_quote_escaped(self) -> None:
        assert safe_xml_text('a"b') == "a&quot;b"

    def test_single_quote_escaped(self) -> None:
        # 本次修复的重点回归：' 必须转义为 &apos;
        assert safe_xml_text("a'b") == "a&apos;b"

    def test_combined_markup_escaped(self) -> None:
        result = safe_xml_text('<a href="x">\'</a>')
        assert result == "&lt;a href=&quot;x&quot;&gt;&apos;&lt;/a&gt;"

    def test_control_chars_removed(self) -> None:
        assert safe_xml_text("\x00\x01\x02abc") == "abc"

    def test_chinese_text_preserved(self) -> None:
        assert safe_xml_text("你好世界") == "你好世界"
