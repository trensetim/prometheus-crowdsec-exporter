import re

type _Rule = tuple[re.Pattern[str], str, int]
"""A single scenario rewrite rule: (compiled pattern, replacement, count) where count=0 means replace all."""

class ScenarioRewriter:
    """
    Applies an ordered list of sed-style regex substitutions to CrowdSec scenario strings.

    Each rule is written like `sed`'s `s` command, but without the leading `s`:

        <delim>pattern<delim>replacement<delim>flags

    where <delim> is any single character (the first character of the rule) that does not
    occur unescaped inside the pattern or replacement. A literal delimiter inside a field
    can be escaped with a backslash (eg. `\\;`). Replacement supports backreferences (`\\1`).

    Empty lines and lines starting with `#` (comments) are ignored.

    Supported flags:
        g  replace all matches (default: only the first match)
        i  case-insensitive matching
        m  multi-line: ^ and $ also match at line boundaries
        s  dot matches newlines as well

    Rules are applied in order: the output of one rule is the input to the next.

    This is used to collapse high-cardinality, dynamic scenario names (eg.
    `anomaly score out-of-band: lfi: 5, anomaly: 5,` or `update : +14999/-0 IPs`)
    into a small, bounded set of labels, reducing Prometheus cardinality.
    """
    _rules: list[_Rule]
    """The sequence of rewrite-rules to apply."""

    def __init__(self, rules: list[_Rule]) -> None:
        self._rules = rules

    def apply(self, scenario: str) -> str:
        """Apply all configured substitutions to the scenario string, in order."""
        for pattern, replacement, count in self._rules:
            scenario = pattern.sub(replacement, scenario, count=count)
        return scenario

    @staticmethod
    def parse(spec: str) -> "ScenarioRewriter | None":
        """
        Build a rewriter from a newline-separated list of sed-style rules.
        Blank lines and #-leaded lines (ie. comments) are ignored.
        Raises ValueError on a malformed rule.
        """
        if spec.strip() == "":
            return None

        rules: list[_Rule] = []
        for lineno, raw_line in enumerate(spec.splitlines(), start=1):
            line = raw_line.strip()
            if line == "" or line.startswith("#"):
                continue
            try:
                rules.append(ScenarioRewriter._parse_rule(line))
            except ValueError as exc:
                raise ValueError(f"invalid scenario rewrite rule on line {lineno} ({line!r}): {exc}") from exc

        return ScenarioRewriter(rules)

    @staticmethod
    def _parse_rule(line: str) -> _Rule:
        delim = line[0]
        pattern_str, replacement, flags_str = ScenarioRewriter._split_fields(line[1:], delim)

        re_flags = 0
        count = 1
        for flag in flags_str:
            if flag == "g":
                count = 0
            elif flag == "i":
                re_flags |= re.IGNORECASE
            elif flag == "m":
                re_flags |= re.MULTILINE
            elif flag == "s":
                re_flags |= re.DOTALL
            else:
                raise ValueError(f"unknown flag {flag!r} (supported: g, i, m, s)")

        try:
            pattern = re.compile(pattern_str, re_flags)
        except re.error as exc:
            raise ValueError(f"invalid regex {pattern_str!r}: {exc}") from exc

        return (pattern, replacement, count)

    @staticmethod
    def _split_fields(body: str, delim: str) -> tuple[str, str, str]:
        """
        Split `body` into exactly three fields on unescaped occurrences of `delim`.
        A backslash-escaped delimiter (`\\<delim>`) is treated as a literal delimiter character.
        """
        fields: list[str] = [""]
        i = 0
        while i < len(body):
            char = body[i]
            if char == "\\" and i + 1 < len(body) and body[i + 1] == delim:
                fields[-1] += delim
                i += 2
                continue
            if char == delim:
                fields.append("")
                i += 1
                continue
            fields[-1] += char
            i += 1

        if len(fields) != 3:
            raise ValueError(f"expected 3 {delim!r}-delimited fields (pattern, replacement, flags), got {len(fields)}")
        return (fields[0], fields[1], fields[2])
