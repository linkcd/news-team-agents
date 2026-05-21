import json
import os

from jinja2 import Environment, FileSystemLoader
from strands import tool

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

SECTION_MAP = {
    "domestic": "国内新闻",
    "international": "国际新闻",
    "business": "财经新闻",
}

SECTION_ORDER = ["domestic", "international", "business"]


def _build_sections(items: list) -> list[dict]:
    """Group items by category into ordered sections."""
    grouped = {}
    for item in items:
        cat = item.get("category", "domestic")
        grouped.setdefault(cat, []).append(item)

    sections = []
    number = 1
    for cat in SECTION_ORDER:
        if cat not in grouped:
            continue
        section_items = []
        for item in grouped[cat]:
            sources = item.get("sources", [])
            sources_text = ", ".join(s["source_label"] for s in sources)
            earliest = min((s["published_at"] for s in sources), default="")
            earliest_time = earliest[11:16] if earliest else ""
            links = " | ".join(
                f"[{s['source_label']}]({s['url']})" for s in sources
            )
            section_items.append({
                "number": number,
                "title_zh": item["title_zh"],
                "summary_zh": item["summary_zh"],
                "sources_text": sources_text,
                "earliest_time": earliest,
                "links_text": links,
                "changelog": item.get("changelog", ""),
            })
            number += 1
        sections.append({"title": SECTION_MAP[cat], "entries": section_items})
    return sections


@tool
def format_post(items: str, template: str, editorial_config: str, date: str, time: str) -> dict:
    """Render a blog post from items using a Jinja2 template.

    Args:
        items: JSON string of items to include in the post
        template: Template name (e.g. "norway_daily", "generic_post")
        editorial_config: JSON string with editorial settings (day_summary, title, body, tags, etc.)
        date: Post date (YYYY-MM-DD)
        time: Post time (HH:MM:SS)

    Returns:
        Dict with status and rendered content string
    """
    try:
        env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            keep_trailing_newline=True,
        )
        template_file = f"{template}.md.j2"
        if not os.path.exists(os.path.join(TEMPLATE_DIR, template_file)):
            return {"status": "error", "error": f"Template not found: {template_file}"}

        tmpl = env.get_template(template_file)
        parsed_items = json.loads(items)
        config = json.loads(editorial_config)

        if template == "norway_daily":
            sections = _build_sections(parsed_items)
            all_sources = sorted(set(
                s["source_label"]
                for item in parsed_items
                for s in item.get("sources", [])
            ))
            rendered = tmpl.render(
                date=date,
                time=time,
                updated_time=time,
                day_summary=config.get("day_summary", ""),
                sections=sections,
                all_sources=", ".join(all_sources),
            )
        else:
            rendered = tmpl.render(date=date, **config)

        return {"status": "success", "content": rendered}
    except Exception as e:
        return {"status": "error", "error": str(e)}
