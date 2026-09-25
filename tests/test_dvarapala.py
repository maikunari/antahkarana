"""The secrets keeper on its own: detection, scrubbing, and its guarantees."""

from __future__ import annotations

import time

import pytest

from secret_samples import negatives, positives
from src.dvarapala.keeper import (
    Keeper,
    KeeperError,
    SecretInWrite,
    default_keeper,
)

POSITIVES = positives()
NEGATIVES = negatives()


@pytest.fixture(scope="module")
def keeper() -> Keeper:
    return default_keeper()


def test_every_rule_compiles(keeper):
    # 221 gitleaks regex rules, minus 4 scoped to file paths, plus 4 memory rules
    assert keeper.rule_count == 221


@pytest.mark.parametrize("sample", POSITIVES, ids=lambda s: s.label)
def test_a_secret_is_replaced_by_a_placeholder(keeper, sample):
    scrubbed = keeper.scrub(sample.text)

    assert scrubbed.redacted
    assert "[secret:" in scrubbed.text
    for value in sample.values:
        assert value not in scrubbed.text


@pytest.mark.parametrize("text", NEGATIVES, ids=lambda t: t[:40])
def test_text_without_a_secret_is_left_alone(keeper, text):
    scrubbed = keeper.scrub(text)

    assert scrubbed.findings == []
    assert scrubbed.text == text


@pytest.mark.parametrize("sample", POSITIVES, ids=lambda s: s.label)
def test_scrubbed_text_scans_clean(keeper, sample):
    # The Chitta write guard scans scrubbed text, so a placeholder must never look like a secret.
    once = keeper.scrub(sample.text)
    twice = keeper.scrub(once.text)

    assert twice.findings == []
    assert twice.text == once.text


def test_secret_only_means_too_few_words_are_left(keeper):
    bare = next(s for s in POSITIVES if s.label == "stripe").values[0]

    assert keeper.scrub(f"OPENROUTER_API_KEY={bare}").secret_only()
    assert keeper.scrub(bare).secret_only()
    assert not keeper.scrub(f"Use {bare} to take payments in the FF checkout").secret_only()
    assert not keeper.scrub("ok").secret_only()  # no secret, nothing to refuse


def test_kinds_name_the_rule_but_never_the_value(keeper):
    sample = next(s for s in POSITIVES if s.label == "github-pat")
    scrubbed = keeper.scrub(sample.text)

    assert scrubbed.kinds() == {"github-pat": 1}
    assert scrubbed.text == "Use [secret:github-pat] to push to the partsmap repo from CI."


def test_scrub_value_reaches_nested_strings(keeper):
    sample = POSITIVES[0]
    value = {"buddhi": {"response": {"scope": sample.text, "n": 3}}, "list": [sample.text, None]}

    scrubbed, findings = keeper.scrub_value(value)

    assert len(findings) == 2
    assert scrubbed["buddhi"]["response"]["n"] == 3
    assert scrubbed["list"][1] is None
    assert sample.values[0] not in str(scrubbed)


def test_check_refuses_a_secret_without_echoing_it(keeper):
    sample = POSITIVES[0]

    with pytest.raises(SecretInWrite) as err:
        keeper.check("memories", "clean text", {"nested": sample.text})

    assert sample.values[0] not in str(err.value)
    keeper.check("memories", "clean text", None, ["a", "b"])  # no error


def test_local_allowlist_lets_a_checked_value_through(tmp_path):
    value = next(s for s in POSITIVES if s.label == "shopify").values[0]
    (tmp_path / "dvarapala.yaml").write_text(f"allow:\n  - '^{value}$'\n")

    assert Keeper.load(tmp_path).find(f"Shopify admin API token for FF store: {value}") == []
    assert Keeper.load(None).find(f"Shopify admin API token for FF store: {value}") != []


@pytest.mark.parametrize(
    "allow",
    ["allow: '^settings$'", "allow:\n  - 42", "allow:\n  - ''", "allow:\n  - '^'",
     "allow:\n  - '.*'"],
    ids=["scalar", "non-string", "empty", "caret", "dot-star"],
)
def test_a_malformed_or_match_everything_allowlist_fails_closed(tmp_path, allow):
    (tmp_path / "dvarapala.yaml").write_text(allow + "\n")

    with pytest.raises(KeeperError):
        Keeper.load(tmp_path)


def test_a_route_after_a_login_label_is_redacted_unless_allowlisted(tmp_path):
    # Accepted trade-off: it reads like `user /password`, and a missed password costs more.
    text = "Login page: see /settings then click"

    scrubbed = Keeper.load(None).scrub(text)
    assert scrubbed.text == "Login page: see /[secret:prose-credential-pair] then click"

    (tmp_path / "dvarapala.yaml").write_text("allow:\n  - '^settings$'\n")
    assert Keeper.load(tmp_path).find(text) == []


def test_unloadable_rules_raise_keeper_error(tmp_path):
    bad = tmp_path / "rules.toml"
    bad.write_text("[[rules]]\nid = 'x'\nregex = '('\n")

    with pytest.raises(KeeperError):
        Keeper(rules_path=bad)


def test_scanning_is_fast_enough_to_sit_in_front_of_every_call(keeper):
    text = " ".join(NEGATIVES) * 20  # ~40 kB of technical prose
    started = time.perf_counter()
    keeper.find(text)
    assert time.perf_counter() - started < 0.5
