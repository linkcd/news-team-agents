import os

MODEL_ID = os.environ.get("MODEL_ID", "global.anthropic.claude-sonnet-4-6")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")

COLLECTOR_RUNTIME_ARN = os.environ.get(
    "COLLECTOR_RUNTIME_ARN",
    "",  # Must be set via environment variable
)
PUBLISHER_RUNTIME_ARN = os.environ.get(
    "PUBLISHER_RUNTIME_ARN",
    "",  # Must be set via environment variable
)

S3_BUCKET = os.environ.get("S3_BUCKET", "")  # Must be set via environment variable

BLOG_REPO = os.environ.get("BLOG_REPO", "")  # Must be set via environment variable (e.g., "owner/repo")
BLOG_BRANCH = "main"

NEWS_SOURCES = [
    {"url": "https://www.nrk.no/norge/toppsaker.rss", "type": "rss", "label": "NRK Norge", "category": "domestic"},
    {"url": "https://www.nrk.no/stor-oslo/toppsaker.rss", "type": "rss", "label": "NRK Oslo", "category": "domestic"},
    {"url": "https://www.vg.no/rss/feed/?categories=1069", "type": "rss", "label": "VG Innenriks", "category": "domestic"},
    {"url": "https://www.tv2.no/rss/nyheter/innenriks", "type": "rss", "label": "TV2 Innenriks", "category": "domestic"},
    {"url": "https://www.dagbladet.no/?lab_viewport=rss", "type": "rss", "label": "Dagbladet", "category": "domestic"},
    {"url": "https://www.aftenposten.no/rss/", "type": "rss", "label": "Aftenposten", "category": "domestic"},
    {"url": "https://www.dagsavisen.no/rss", "type": "rss", "label": "Dagsavisen", "category": "domestic"},
    {"url": "https://www.nrk.no/urix/toppsaker.rss", "type": "rss", "label": "NRK Urix", "category": "international"},
    {"url": "https://www.vg.no/rss/feed/?categories=1070", "type": "rss", "label": "VG Utenriks", "category": "international"},
    {"url": "https://www.tv2.no/rss/nyheter/utenriks", "type": "rss", "label": "TV2 Utenriks", "category": "international"},
    {"url": "http://e24.no/rss2/", "type": "rss", "label": "E24", "category": "business"},
]
