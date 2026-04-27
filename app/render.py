from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
from jinja2 import Template

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def _read_template(filename: str) -> str:
    p = TEMPLATES_DIR / filename
    if not p.exists():
        return f"（テンプレートファイル {filename} が見つかりません）"
    return p.read_text(encoding="utf-8")


def render_reason(context: Dict[str, Any]) -> str:
    tpl = Template(_read_template("reason.txt.txt"))
    return tpl.render(**context)


def render_missing_documents(missing_documents: List[str]) -> str:
    tpl = Template(_read_template("documents.txt.txt"))
    missing = "\n".join([f"- {d}" for d in missing_documents]) if missing_documents else "- （なし）"
    return tpl.render(missing_documents=missing)


def render_checklist(ng_warnings: List[str]) -> str:
    tpl = Template(_read_template("flow.txt.txt"))
    warnings = "\n".join([f"- {w}" for w in ng_warnings]) if ng_warnings else "- （特記事項なし）"
    return tpl.render(ng_warnings=warnings)
