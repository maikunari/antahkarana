"""The secrets keeper: finds secrets in text and replaces them with typed placeholders.

Detection is local and deterministic, so nothing leaves the machine to decide
whether something is a secret:

1. gitleaks' default rule set (vendored `gitleaks.toml`, v8.30.1, MIT), compiled
   with RE2 for Go-regex parity and linear-time matching on hostile input;
2. a few rules for secrets written the way memories are written (prose
   passwords, credential pairs, URL passwords), which gitleaks does not cover;
3. an entropy backstop for long random-looking tokens no rule named.

A secret is replaced by `[secret:<rule-id>]`; the value is never logged,
returned, or stored. Scrubbing is idempotent: scrubbed text scans clean.
"""

from __future__ import annotations

import math
import re
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import re2
import yaml

RULES_PATH = Path(__file__).with_name("gitleaks.toml")

ALLOW_FILE = "dvarapala.yaml"

# Fewer words than this left beside the placeholders means the input was
# essentially just the secret, so there is nothing worth remembering.
MIN_WORDS_AFTER_REDACTION = 5

RESIDUAL_RULE_ID = "high-entropy"
RESIDUAL_MIN_ENTROPY = 4.0
# Longest digit run an identifier or version string may hold (a date: 20260101).
MAX_IDENTIFIER_NUMBER = 8

PLACEHOLDER = re.compile(r"\[secret:[a-z0-9-]+\]")

MEMORY_RULES = [
    {
        "id": "url-userinfo-password",
        "regex": r"[a-z][a-z0-9+.-]{1,20}://[^\s:/@]{1,64}:([^\s@/]{3,128})@[^\s/]+",
        "keywords": ["://"],
    },
    {
        "id": "prose-password",
        "regex": (
            r"(?i)\b(?:password|passphrase|passcode|passwd|pwd|pin)\b(?:\s+for\s+\S+)?"
            r"\s*(?:\bis\b|\bwas\b|=|:)\s*[\x60'\"]?([^\s\x60'\"]{4,128})"
        ),
        "keywords": ["pass", "pwd", "pin"],
        "allowlists": [
            {
                "regexes": [
                    r"(?i)^(?:reset|flow|manager|protected|required|stored|less|here|set"
                    r"|the|a|an|in|kept|not|never|only|always|now|still|managed|rotated"
                    r"|1password|bitwarden|lastpass|keepass(?:xc)?|dashlane|vault|keychain)$"
                ]
            }
        ],
    },
    {
        "id": "prose-credential-pair",
        "regex": (
            r"(?i)\b(?:login|credentials?|creds)\b[^\n]{0,60}?(?:\bis|:)"
            r"\s+[^\s/]{1,64}\s*/\s*([^\s/]{6,128})(?:\s|$)"
        ),
        "keywords": ["login", "cred"],
        "allowlists": [
            {
                "regexes": [
                    r"(?i)\.(?:py|pyi|js|jsx|mjs|ts|tsx|json|ya?ml|toml|ini|cfg|conf|env|md"
                    r"|txt|rst|sh|go|rs|rb|java|kt|swift|c|h|cpp|hpp|cs|php|html|css|sql"
                    r"|db|lock|log|xml|csv)[.,;:)]?$"
                ]
            }
        ],
    },
]

_TOKEN = re2.compile(r"[A-Za-z0-9+/_=.~-]{20,}")
_HASHLIKE = re2.compile(
    r"^(?:[0-9a-f]{7,128}|[0-9A-F]{7,128}|sha(?:1|256|384|512)[-:].*"
    r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$"
)
_CLASSES = (re2.compile("[a-z]"), re2.compile("[A-Z]"), re2.compile("[0-9]"))
_WORD = re.compile(r"[^\W_]+")
_SEGMENT = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|[0-9]+")
_VOWEL = re.compile(r"[aeiouy]", re.IGNORECASE)


class KeeperError(Exception):
    """The keeper could not load or run. Callers must fail closed."""


class SecretInWrite(ValueError):
    """A write to Chitta carried a secret the keeper should have removed first."""


@dataclass(frozen=True)
class Finding:
    rule_id: str
    start: int
    end: int


@dataclass
class Scrubbed:
    """Text with every secret replaced by a placeholder, and what was replaced."""

    text: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def redacted(self) -> bool:
        return bool(self.findings)

    def kinds(self) -> dict[str, int]:
        return dict(Counter(f.rule_id for f in self.findings))

    def secret_only(self) -> bool:
        """True when a secret was removed and too few words remain to be worth storing."""
        if not self.findings:
            return False
        return len(_WORD.findall(PLACEHOLDER.sub(" ", self.text))) < MIN_WORDS_AFTER_REDACTION


def _entropy(s: str) -> float:
    counts = Counter(s)
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in counts.values()) if n else 0.0


def _identifier_like(token: str) -> bool:
    """True for code identifiers and version strings: split on `-`, `_`, `.` and
    camelCase, every segment is a word-like run of letters or a short number."""
    for piece in re.split(r"[-_.]", token):
        segments = _SEGMENT.findall(piece)
        if "".join(segments) != piece:
            return False
        for i, seg in enumerate(segments):
            if seg.isdigit():
                if len(seg) > MAX_IDENTIFIER_NUMBER:
                    return False
            elif len(seg) == 1:
                # A lone letter only as a version marker: V2, Q1.
                if not (i + 1 < len(segments) and segments[i + 1].isdigit()):
                    return False
            elif not _VOWEL.search(seg):
                return False
    return True


def _compile(pattern: str) -> re2._Regexp:
    options = re2.Options()
    options.max_mem = 64 << 20
    return re2.compile(pattern, options)


class _Allowlist:
    def __init__(self, spec: dict) -> None:
        self.target = spec.get("regexTarget", "secret")
        self.regexes = [_compile(r) for r in spec.get("regexes", [])]
        self.stopwords = [s.lower() for s in spec.get("stopwords", [])]
        # Text has no file path or commit, so an AND on either can never hold.
        self.unsatisfiable = spec.get("condition") == "AND" and bool(
            spec.get("paths") or spec.get("commits")
        )

    def allows(self, secret: str, match: str, line: str) -> bool:
        if self.unsatisfiable:
            return False
        target = {"secret": secret, "match": match, "line": line}[self.target]
        lowered = secret.lower()
        return any(r.search(target) for r in self.regexes) or any(
            w in lowered for w in self.stopwords
        )


class _Rule:
    def __init__(self, spec: dict) -> None:
        self.id = spec["id"]
        self.regex = _compile(spec["regex"])
        self.secret_group = spec.get("secretGroup")
        self.entropy = spec.get("entropy")
        self.keywords = [k.lower() for k in spec.get("keywords", [])]
        self.allowlists = [_Allowlist(a) for a in spec.get("allowlists", [])]


class Keeper:
    """Finds and scrubs secrets. Build one per process; it is safe to share."""

    def __init__(self, rules_path: Path = RULES_PATH, allow_regexes: list[str] | None = None):
        try:
            with open(rules_path, "rb") as f:
                config = tomllib.load(f)
            # Rules scoped to a file path (terraform, nuget, ...) cannot apply to memory text.
            specs = [r for r in config["rules"] if "regex" in r and "path" not in r]
            self._rules = [_Rule(r) for r in specs + MEMORY_RULES]
            glob = config.get("allowlist", {})
            self._global = _Allowlist(
                {"regexes": glob.get("regexes", []) + list(allow_regexes or []),
                 "stopwords": glob.get("stopwords", [])}
            )
        except Exception as err:
            raise KeeperError(f"could not load secrets rules: {type(err).__name__}") from err

    @classmethod
    def load(cls, config_dir: str | Path | None) -> Keeper:
        """The keeper with the local allowlist from `<config_dir>/dvarapala.yaml`, if any."""
        allow: list[str] = []
        if config_dir is not None:
            path = Path(config_dir) / ALLOW_FILE
            if path.exists():
                with open(path) as f:
                    allow = list((yaml.safe_load(f) or {}).get("allow") or [])
        return cls(allow_regexes=allow)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def find(self, text: str) -> list[Finding]:
        """Every secret span in `text`, merged where they overlap."""
        if not text:
            return []
        found = self._rule_findings(text)
        found += [
            f for f in self._residual_findings(text)
            if not any(f.start < g.end and g.start < f.end for g in found)
        ]
        found.sort(key=lambda f: (f.start, -f.end))
        merged: list[Finding] = []
        for f in found:
            if merged and f.start < merged[-1].end:
                last = merged[-1]
                merged[-1] = Finding(last.rule_id, last.start, max(last.end, f.end))
            else:
                merged.append(f)
        return merged

    def scrub(self, text: str) -> Scrubbed:
        findings = self.find(text)
        parts: list[str] = []
        last = 0
        for f in findings:
            parts += [text[last:f.start], f"[secret:{f.rule_id}]"]
            last = f.end
        parts.append(text[last:])
        return Scrubbed("".join(parts), findings)

    def scrub_value(self, value: object) -> tuple[object, list[Finding]]:
        """Scrub every string inside a JSON-shaped value (dict keys included)."""
        findings: list[Finding] = []

        def walk(v: object) -> object:
            if isinstance(v, str):
                s = self.scrub(v)
                findings.extend(s.findings)
                return s.text
            if isinstance(v, dict):
                return {walk(k): walk(x) for k, x in v.items()}
            if isinstance(v, (list, tuple)):
                return [walk(x) for x in v]
            return v

        return walk(value), findings

    def check(self, where: str, *values: object) -> None:
        """Raise SecretInWrite if any string in `values` still holds a secret."""
        for value in values:
            _, findings = self.scrub_value(value)
            if findings:
                kinds = sorted({f.rule_id for f in findings})
                raise SecretInWrite(f"refused to write a secret to {where} ({', '.join(kinds)})")

    def _rule_findings(self, text: str) -> list[Finding]:
        lowered = text.lower()
        out: list[Finding] = []
        for rule in self._rules:
            if rule.keywords and not any(k in lowered for k in rule.keywords):
                continue
            for m in rule.regex.finditer(text):
                group = rule.secret_group or (1 if m.re.groups >= 1 and m.group(1) else 0)
                if not m.group(group):
                    group = 0
                secret = m.group(group)
                start, end = m.span(group)
                if "[secret:" in secret:
                    continue  # a placeholder, not a secret: keeps scrubbing idempotent
                if rule.entropy and _entropy(secret) < rule.entropy:
                    continue
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.end())
                line = text[line_start: line_end if line_end >= 0 else len(text)]
                if self._global.allows(secret, m.group(0), line):
                    continue
                if any(a.allows(secret, m.group(0), line) for a in rule.allowlists):
                    continue
                out.append(Finding(rule.id, start, end))
        return out

    @staticmethod
    def _residual_findings(text: str) -> list[Finding]:
        out = []
        for m in _TOKEN.finditer(text):
            token = m.group(0)
            if _HASHLIKE.match(token) or token.strip("/").count("/") > 2:
                continue  # digests, ids and paths
            if _identifier_like(token):
                continue
            if all(c.search(token) for c in _CLASSES) and _entropy(token) >= RESIDUAL_MIN_ENTROPY:
                out.append(Finding(RESIDUAL_RULE_ID, m.start(), m.end()))
        return out


@lru_cache(maxsize=1)
def default_keeper() -> Keeper:
    """The process-wide keeper with the repo's config, loaded once."""
    return Keeper.load(Path(__file__).resolve().parents[2] / "config")
