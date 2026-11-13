"""Unit tests for the sed-style scenario rewriter (src/main/python/scenario.py)."""

import pytest

from scenario import ScenarioRewriter


class TestApply:
    @pytest.mark.parametrize(
        "spec, scenario, expected",
        [
            # first match only is the default (sed-like), unless the `g` flag is given
            (";a;X;", "aaa", "Xaa"),
            (";a;X;g", "aaa", "XXX"),
            # `i` flag makes matching case-insensitive
            (";abc;X;i", "ABC", "X"),
            # replacement supports backreferences
            (r";^(\w+)/.*;\1;", "crowdsecurity/ssh-bf", "crowdsecurity"),
            # non-matching input is returned unchanged
            (";^update : .*;capi-update;", "crowdsecurity/vpatch-env-access", "crowdsecurity/vpatch-env-access"),
            # the first character of the rule is the delimiter, so any (non-'#') delimiter works
            ("@foo@bar@", "foo", "bar"),
            # a backslash-escaped delimiter inside a field is treated as a literal delimiter
            (r";a\;b;Z;", "a;b", "Z"),
        ],
    )
    def test_single_rule(self, spec: str, scenario: str, expected: str):
        rewriter = ScenarioRewriter.parse(spec)
        assert rewriter is not None
        assert rewriter.apply(scenario) == expected

    def test_rules_are_applied_in_sequence(self):
        # the output of the first rule feeds the second
        rewriter = ScenarioRewriter.parse(";^update : .*;tmp;\n;tmp;final;")
        assert rewriter is not None
        assert rewriter.apply("update : +14999/-0 IPs") == "final"

    @pytest.mark.parametrize(
        "scenario",
        [
            "anomaly score out-of-band: lfi: 5, anomaly: 5,",
            "anomaly score out-of-band: sql_injection: 10, rce: 35, anomaly: 45,",
            "anomaly score out-of-band:",
        ],
    )
    def test_collapses_dynamic_anomaly_scores(self, scenario: str):
        # the high-cardinality example from the README
        rewriter = ScenarioRewriter.parse(";^anomaly score out-of-band:.*;anomaly score out-of-band;")
        assert rewriter is not None
        assert rewriter.apply(scenario) == "anomaly score out-of-band"

    @pytest.mark.parametrize("spec", ["", "   ", "\n\n", "  \n \t\n"])
    def test_blank_spec_returns_none(self, spec: str):
        # an empty/whitespace-only spec means "no rewriting configured"
        assert ScenarioRewriter.parse(spec) is None

    def test_comment_lines_are_ignored(self):
        # lines starting with '#' are comments
        rewriter = ScenarioRewriter.parse("# normalize CAPI updates\n;^update : .*;capi-update;")
        assert rewriter is not None
        assert rewriter.apply("update : +14999/-0 IPs") == "capi-update"

    def test_blank_lines_are_ignored(self):
        rewriter = ScenarioRewriter.parse("\n   \n;a;b;\n\n")
        assert rewriter is not None
        assert rewriter.apply("a") == "b"


class TestParseErrors:
    @pytest.mark.parametrize(
        "spec, expected_message_fragment",
        [
            (";only;two", "expected 3"),        # too few delimited fields
            (";a;b;zz", "unknown flag"),        # unsupported flag
            (";(unclosed;x;", "invalid regex"), # pattern does not compile
        ],
    )
    def test_malformed_rule_raises(self, spec: str, expected_message_fragment: str):
        with pytest.raises(ValueError) as excinfo:
            ScenarioRewriter.parse(spec)
        assert expected_message_fragment in str(excinfo.value)

    def test_error_reports_the_offending_line_number(self):
        spec = ";ok;good;\n;bad;flag;qq"  # the second rule has an unknown flag
        with pytest.raises(ValueError) as excinfo:
            ScenarioRewriter.parse(spec)
        assert "line 2" in str(excinfo.value)
