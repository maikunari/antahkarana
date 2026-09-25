"""Synthetic secrets in memory-shaped sentences, generated at test time.

Nothing here is a real credential, and no realistic key is committed: each
value is random text in a provider's format, built when the tests run, so
repository secret scanners have nothing to flag.
"""

from __future__ import annotations

import base64
import json
import random
import string
from dataclasses import dataclass

_R = random.Random(20260925)
ALNUM = string.ascii_letters + string.digits
HEX = "0123456789abcdef"
B64U = ALNUM + "-_"


def _s(n: int, alphabet: str = ALNUM) -> str:
    return "".join(_R.choice(alphabet) for _ in range(n))


def _jwt() -> str:
    def enc(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    return f"{enc({'alg': 'HS256', 'typ': 'JWT'})}.{enc({'sub': _s(8), 'iat': 1790000000})}.{_s(43, B64U)}"


@dataclass(frozen=True)
class Sample:
    label: str
    text: str
    values: tuple[str, ...]  # every secret value that must never survive a scrub


def _sample(label: str, template: str, *values: str) -> Sample:
    return Sample(label, template.format(*values), values)


def positives() -> list[Sample]:
    pem_body = "\n".join(_s(70, ALNUM + "+/") for _ in range(5))
    pem = f"-----BEGIN OPENSSH PRIVATE KEY-----\n{pem_body}\n-----END OPENSSH PRIVATE KEY-----"
    aws_id = "AKIA" + _s(16, string.ascii_uppercase + "234567")
    aws_secret = _s(40, ALNUM + "/+")
    return [
        _sample("openai", "Jozu translation uses OpenAI; key is {} for now.",
                f"sk-proj-{_s(74, B64U)}T3BlbkFJ{_s(74, B64U)}"),
        _sample("anthropic", "Set ANTHROPIC_API_KEY={} in the Jozu worker env.",
                f"sk-ant-api03-{_s(93, B64U)}AA"),
        _sample("aws-pair", "FF backups bucket creds: {} / {}", aws_id, aws_secret),
        _sample("github-pat", "Use {} to push to the partsmap repo from CI.", f"ghp_{_s(36)}"),
        _sample("github-fine-grained", "New fine-grained token {} scoped to antahkarana only.",
                f"github_pat_{_s(22)}_{_s(59)}"),
        _sample("stripe", "Friendly Fires Stripe live secret: {}", f"sk_live_{_s(99)}"),
        _sample("gemini", "GEMINI_API_KEY={} is the key the Jozu worker uses in production",
                f"AIza{_s(35, ALNUM + '-_')}"),
        _sample("slack", "Slack bot token for the ops channel is {}",
                f"xoxb-{_s(12, string.digits)}-{_s(13, string.digits)}-{_s(24)}"),
        _sample("shopify", "Shopify admin API token for FF store: {}", f"shpat_{_s(32, HEX)}"),
        _sample("jwt", "Test session JWT that works against staging: {}", _jwt()),
        _sample("private-key", "Deploy key for the VPS, keep it safe:\n{}", pem),
        _sample("postgres-url", "Prod DB is postgres://jozu_app:{}@db.jozu.internal:5432/jozu",
                _s(20)),
        _sample("prose-password", "The office wifi password is {}.", "hunter2-sakura-77"),
        _sample("credential-pair", "WP admin login for friendlyfires.ca is mike / {}",
                "Tr0ub4dor&3xyz"),
        _sample("generic-api-key", "typesafe api_key: {} works for the shadow judge",
                _s(40, string.ascii_lowercase + string.digits)),
        _sample("env-block", "TYPESAFE_API_KEY={}\nANTAHKARANA_DATA_DIR=./data for the laptop",
                _s(48)),
        _sample("curl-bearer",
                "curl -H 'Authorization: Bearer {}' https://api.typesafe.ai/v1/systemone works.",
                _s(40)),
        _sample("sendgrid", "SendGrid key {} is for KantanHealth mail.",
                f"SG.{_s(22, B64U)}.{_s(43, B64U)}"),
        _sample("npm", "npm publish token {} for the partsmap-sdk package", f"npm_{_s(36)}"),
        _sample("gcp-service-account",
                '{{"type": "service_account", "private_key": "-----BEGIN PRIVATE KEY-----\\n{}'
                '\\n-----END PRIVATE KEY-----\\n"}}',
                _s(64, ALNUM + "+/")),
    ]


def negatives() -> list[str]:
    """Memory-shaped text that looks technical but holds no secret."""
    uuid = "-".join([_s(8, HEX), _s(4, HEX), _s(4, HEX), _s(4, HEX), _s(12, HEX)])
    return [
        "We chose PostgreSQL for Jozu because of JSONB support.",
        "We tried Zvec's HNSW index with 1536 dims; it broke because the schema is fixed at 768.",
        "Mike prefers short replies in Discord.",
        "As of March 2026, Jozu runs on Gemini Flash-Lite.",
        "The Stripe live key is kept in 1Password under 'FF Stripe live'; never paste it into chat.",
        "We rotated the AWS keys on 2026-09-20 after the leak in the build log.",
        "GEMINI_API_KEY=your_key_here goes in .env, which is gitignored.",
        'Config reads os.environ.get("TYPESAFE_API_KEY", "") and treats empty as off.',
        f"Fixed in commit {_s(40, HEX)} on the fm/antahkarana-jev-shadow branch.",
        f"Memory {uuid} was superseded.",
        f"The release artifact sha256 is {_s(64, HEX)}.",
        f"Pinned image ghcr.io/maikunari/partsmap@sha256:{_s(64, HEX)}",
        f"package-lock integrity sha512-{_s(86, ALNUM + '+/')}== for zvec.",
        "Jev latency median is 214 ms; timeout 3.0 s; 1,200 requests per minute limit.",
        "The password reset flow for KantanHealth uses magic links, no passwords stored.",
        "Auth uses a Bearer token in the Authorization header; tokens expire after 1 hour.",
        "Scope /project/friendly-fires/shopify holds the FF Shopify migration decisions.",
        "Brand colours for Ellune are #1F2937 and #F59E0B.",
        "Jozu の翻訳は Gemini Flash-Lite で行う。",
        "The API base URL is https://api.typesafe.ai/v1/systemone and the model is jev-1.13.0.",
        "Tailscale host is th50.tail8ce07c.ts.net; lavish runs on port 4387.",
        "Use the AWS docs example key AKIAIOSFODNN7EXAMPLE in tests only.",
        "Token budget for Jev state plus longest question is 32k tokens.",
        f"The TypeSafe response id was req_{_s(24, HEX)} for the slow 1,795 ms call.",
        f"Cloudflare zone id {_s(32, HEX)} is the ellune.app zone.",
        "The password is stored in 1Password, never in the repo.",
        # Prose rules must not fire inside words, on paths, or on a vault pointer.
        "Fixed the password issues in the login form.",
        "The password isolation policy applies to every tenant.",
        "Store the password: 1Password item 'Staging DB'",
        "Login handler: src/auth/session.py owns the cookie refresh",
        "Credentials loader: config/credentials.yaml is read at startup",
        # Identifiers and version strings are not random-looking tokens.
        "getUserAccountBalance2024ForReport feeds the monthly statement.",
        "The dashboard calls useQueryClientV2WithRetryLogic on mount.",
        "Run MigrateOrdersToV3Schema_2026Q1 before the Shopify cutover.",
        "The image pins python3.12-Django4.2-Postgres16.1 for partsmap.",
        "Jozu evals ran on claude-opus-5-5-20260101-Preview last week.",
    ]


def a_secret_sentence() -> Sample:
    """One sentence with a secret and plenty of surrounding words."""
    return _sample(
        "stripe-in-context",
        "Stripe live key rotated on 2026-09-20 after the build-log leak; the new key is {} "
        "and lives in the FF payments service.",
        f"sk_live_{_s(40)}",
    )
