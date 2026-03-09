"""Tests for database query utilities (Lucene escaping, query building, normalization)."""

from app.utils.database_utils.query_utils import (
    escape_lucene,
    build_lucene_query,
    normalize_query_for_index,
)


class TestEscapeLucene:
    def test_plain_text_unchanged(self):
        assert escape_lucene("hello") == "hello"

    def test_escapes_plus(self):
        assert escape_lucene("a+b") == r"a\+b"

    def test_escapes_colon(self):
        assert escape_lucene("field:value") == r"field\:value"

    def test_escapes_parentheses(self):
        assert escape_lucene("(test)") == r"\(test\)"

    def test_escapes_brackets(self):
        assert escape_lucene("[1 TO 5]") == r"\[1 TO 5\]"

    def test_escapes_asterisk_and_question(self):
        assert escape_lucene("te*t?") == r"te\*t\?"

    def test_escapes_double_quotes(self):
        assert escape_lucene('"quoted"') == r'\"quoted\"'

    def test_escapes_backslash(self):
        assert escape_lucene("a\\b") == "a\\\\b"

    def test_escapes_multiple_special_chars(self):
        result = escape_lucene("a+b-c&d|e")
        assert result == r"a\+b\-c\&d\|e"

    def test_empty_string(self):
        assert escape_lucene("") == ""


class TestBuildLuceneQuery:
    def test_single_keyword(self):
        assert build_lucene_query(["henk"]) == "henk*"

    def test_multiple_keywords_and_joined(self):
        assert build_lucene_query(["henk", "boer"]) == "henk* AND boer*"

    def test_three_keywords(self):
        assert build_lucene_query(["a", "b", "c"]) == "a* AND b* AND c*"

    def test_special_chars_escaped_in_keywords(self):
        result = build_lucene_query(["o'brien"])
        # apostrophe is not a Lucene special char, should pass through
        assert result == "o'brien*"

    def test_keyword_with_colon(self):
        result = build_lucene_query(["field:val"])
        assert result == r"field\:val*"


class TestNormalizeQueryForIndex:
    def test_removes_punctuation(self):
        assert normalize_query_for_index("hello, world!") == "hello  world "

    def test_keeps_alphanumeric_and_spaces(self):
        assert normalize_query_for_index("henk boer") == "henk boer"

    def test_removes_special_chars(self):
        assert normalize_query_for_index("o'brien-smith") == "o brien smith"

    def test_preserves_underscores(self):
        # \w includes underscores
        assert normalize_query_for_index("some_name") == "some_name"

    def test_empty_string(self):
        assert normalize_query_for_index("") == ""
