"""Wiki — unified living docs and encyclopedia for Flatland (merged with /guide).

Features presets, sustainability, live API playground & full i18n (en/vi/fr).
Backend-rendered HTML at /wiki (and /guide) and JSON at /api/wiki.
Styled with Flatland's native dark theme.
"""

from __future__ import annotations

import html
import re
from typing import Any

from .config import Config
from .protocol import GodLaws
from .wiki_content_i18n import (
    CODEBASE_MAP_MD_I18N,
    CONFIG_OPS_MD_I18N,
    CURL_EXAMPLES_I18N,
    DATA_MODEL_MD_I18N,
    HOW_IT_WORKS_MD_I18N,
)
from .wiki_i18n import (
    DEFAULT_LANG,
    FLATLAND_BOOK_COMPARISON_MD_I18N,
    LAW_HINTS_I18N,
    NAV_SECTIONS,
    PERFORMANCE_MD_I18N,
    SUSTAINABILITY_MD_I18N,
    SUPPORTED_LANGS,
    UI_I18N,
    WIKI_OVERVIEW_MD_I18N,
    normalize_lang,
)

# Backward-compatibility exports
WIKI_OVERVIEW_MD = WIKI_OVERVIEW_MD_I18N["en"]
FLATLAND_BOOK_COMPARISON_MD = FLATLAND_BOOK_COMPARISON_MD_I18N["en"]
SUSTAINABILITY_MD = SUSTAINABILITY_MD_I18N["en"]
PERFORMANCE_MD = PERFORMANCE_MD_I18N["en"]
LAW_HINTS_MD = LAW_HINTS_I18N["en"]
HOW_IT_WORKS_MD = HOW_IT_WORKS_MD_I18N["en"]
CONFIG_OPS_MD = CONFIG_OPS_MD_I18N["en"]
CODEBASE_MAP_MD = CODEBASE_MAP_MD_I18N["en"]
DATA_MODEL_MD = DATA_MODEL_MD_I18N["en"]


def _md_to_html(md: str) -> str:
    """Tiny markdown → HTML: headings, bold, italic, code, links, lists, paragraphs."""
    lines = md.split("\n")
    out: list[str] = []
    in_code = False
    in_ul = False
    in_ol = False

    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", s)
        s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        return s

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                out.append("</pre>")
                in_code = False
            else:
                out.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if not line.strip():
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if in_ol:
                out.append("</ol>")
                in_ol = False
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            lvl = len(m.group(1))
            text = inline(m.group(2).strip())
            slug = re.sub(r"[^a-z0-9]+", "-", m.group(2).lower()).strip("-")
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if in_ol:
                out.append("</ol>")
                in_ol = False
            out.append(f'<h{lvl} id="{slug}">{text}</h{lvl}>')
            continue
        if re.match(r"^[-*]\s+", line):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            if in_ol:
                out.append("</ol>")
                in_ol = False
            txt = inline(re.sub(r"^[-*]\s+", "", line))
            out.append(f"<li>{txt}</li>")
            continue
        if re.match(r"^\d+\.\s+", line):
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            if in_ul:
                out.append("</ul>")
                in_ul = False
            txt = inline(re.sub(r"^\d+\.\s+", "", line))
            out.append(f"<li>{txt}</li>")
            continue
        out.append(f"<p>{inline(line)}</p>")

    if in_ul:
        out.append("</ul>")
    if in_ol:
        out.append("</ol>")
    if in_code:
        out.append("</pre>")
    return "\n".join(out)


def _god_laws_table(lang: str = "en", hints_map: dict | None = None) -> str:
    """Auto-generated table of every GodLaws field with type/range/default + hint."""
    cfg = Config()
    if hints_map is None:
        hints_map = LAW_HINTS_I18N.get(lang, LAW_HINTS_I18N.get("en", {}))
    rows = []
    for name, field in GodLaws.model_fields.items():
        ann = str(field.annotation)
        constraints = []
        for m in getattr(field, "metadata", []):
            if hasattr(m, "ge") and m.ge is not None:
                constraints.append(f"≥{m.ge}")
            if hasattr(m, "le") and m.le is not None:
                constraints.append(f"≤{m.le}")
            if hasattr(m, "gt") and m.gt is not None:
                constraints.append(f">{m.gt}")
        default = getattr(cfg, name, None) if hasattr(cfg, name) else None
        typ = ann.replace("Optional", "").replace("[", "").replace("]", "").strip(" |None")
        hint = html.escape(hints_map.get(name, "")) if hints_map else ""
        hint_cell = f'<small style="color:var(--text-muted)">{hint}</small> <a href="/docs/god-laws.md#{html.escape(name)}" style="font-size:10px">md</a>' if hint else "—"
        rows.append(
            f"<tr><td><code>{html.escape(name)}</code></td>"
            f"<td>{html.escape(typ)}</td>"
            f"<td>{html.escape(', '.join(constraints) or '—')}</td>"
            f"<td>{html.escape(str(default))}</td>"
            f"<td>{hint_cell}</td></tr>"
        )
    headers = {
        "en": "<tr><th>Law</th><th>Type</th><th>Range</th><th>Default</th><th>Hint + docs</th></tr>",
        "vi": "<tr><th>Định luật</th><th>Kiểu</th><th>Khoảng</th><th>Mặc định</th><th>Gợi ý & tài liệu</th></tr>",
        "fr": "<tr><th>Loi</th><th>Type</th><th>Plage</th><th>Défaut</th><th>Indice & docs</th></tr>",
    }
    header = headers.get(lang, headers["en"])
    return f'<div class="table-wrapper"><table><thead>{header}</thead><tbody>{"".join(rows)}</tbody></table></div>'


def _api_table(app: Any, lang: str = "en") -> str:
    """Auto-generated API table from live routes + OpenAPI schema."""
    rows = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None)
        if not path or path.startswith("/openapi") or path.startswith("/docs") or path.startswith("/redoc"):
            continue
        if methods:
            for m in sorted(methods):
                if m in ("HEAD", "OPTIONS"):
                    continue
                rows.append(f"<tr><td><code>{html.escape(m)} {html.escape(path)}</code></td>"
                            f"<td>{html.escape(getattr(route, 'name', ''))}</td></tr>")
        else:
            rows.append(f"<tr><td><code>{html.escape(path)}</code></td><td></td></tr>")
    rows = sorted(set(rows))
    headers = {
        "en": "<tr><th>Route</th><th>Name</th></tr>",
        "vi": "<tr><th>Tuyến API</th><th>Tên hàm</th></tr>",
        "fr": "<tr><th>Route API</th><th>Nom</th></tr>",
    }
    header = headers.get(lang, headers["en"])
    return f'<div class="table-wrapper"><table><thead>{header}</thead><tbody>{"".join(rows)}</tbody></table></div>'


def _presets_table(lang: str = "en") -> str:
    from .main import PRESETS, detect_current_preset
    ui = UI_I18N.get(lang, UI_I18N["en"])
    current = detect_current_preset()
    rows = []
    for name, laws in PRESETS.items():
        is_active = (name == current)
        preview = ", ".join(f"{k}={v}" for k, v in list(laws.items())[:6])
        if len(laws) > 6:
            preview += f" … +{len(laws)-6} more"
        active_badge = f' <span class="badge" style="background:#238636;color:#fff;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700;">{html.escape(ui["active_badge"])}</span>' if is_active else ''
        row_style = ' style="background:rgba(35,134,54,0.08);"' if is_active else ''
        # Presets are read-only on /wiki — applying is reserved for the app UI and TUI.
        apply_btn = f'<span style="color:var(--text-muted);font-size:11px;">{html.escape(ui["preset_via_app"])}</span>'
        rows.append(f"<tr{row_style}><td><code>{html.escape(name)}</code>{active_badge}</td><td><small style=\"color:var(--text-muted)\">{html.escape(preview)}</small></td><td>{apply_btn}</td></tr>")
    header = f"<tr><th>{html.escape(ui['preset_col_name'])}</th><th>{html.escape(ui['preset_col_laws'])}</th><th>{html.escape(ui['preset_col_apply'])}</th></tr>"
    return f'<div class="table-wrapper"><table><thead>{header}</thead><tbody>{"".join(rows)}</tbody></table></div>'


def _curl_examples(lang: str = "en") -> str:
    md = CURL_EXAMPLES_I18N.get(lang, CURL_EXAMPLES_I18N["en"])
    return _md_to_html(md)



WIKI_TEMPLATE = """<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="keywords" content="Flatland, World Simulation, Wiki, Guide, Presets, Simulation Mechanics, Long Phan, long@minhnhan.in, Artificial Life">
<meta name="author" content="Long Phan <long@minhnhan.in>">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://world.minhnhan.in/wiki?lang={lang}">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_desc}">
<meta property="og:url" content="https://world.minhnhan.in/wiki?lang={lang}">
<meta property="og:type" content="article">
<style>
:root {{
  color-scheme: dark;
  --bg-main: #0b0f14;
  --bg-sidebar: #0d1117;
  --bg-card: rgba(22, 27, 34, 0.85);
  --bg-card-hover: rgba(33, 38, 45, 0.95);
  --border-subtle: #21262d;
  --border-strong: #30363d;
  --border-active: #58a6ff;
  --text-primary: #f0f6fc;
  --text-normal: #c9d1d9;
  --text-muted: #8b949e;
  --text-dim: #6e7681;
  --accent-blue: #58a6ff;
  --accent-green: #3fb950;
  --accent-amber: #d29922;
  --accent-orange: #ffa657;
  --accent-red: #f85149;
  --accent-purple: #d2a8ff;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
}}

* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  font-family: var(--font-sans);
  margin: 0;
  color: var(--text-normal);
  background: var(--bg-main);
  line-height: 1.65;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
}}

/* Scrollbars */
::-webkit-scrollbar {{ width: 7px; height: 7px; }}
::-webkit-scrollbar-track {{ background: var(--bg-sidebar); }}
::-webkit-scrollbar-thumb {{ background: var(--border-strong); border-radius: 4px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--text-muted); }}

/* Layout */
.wiki-layout {{
  display: flex;
  min-height: 100vh;
}}

/* Sidebar */
.wiki-sidebar {{
  width: 310px;
  min-width: 310px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-subtle);
  height: 100vh;
  position: sticky;
  top: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: 16px 14px;
  gap: 12px;
  z-index: 20;
}}

/* Header & Brand */
.wiki-brand {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-subtle);
}}
.wiki-brand h2 {{
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.04em;
  display: flex;
  align-items: center;
  gap: 6px;
}}
.wiki-brand .version-tag {{
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 12px;
  background: rgba(88, 166, 255, 0.15);
  color: var(--accent-blue);
  border: 1px solid rgba(88, 166, 255, 0.3);
}}

/* Language Switcher */
.lang-switcher {{
  display: flex;
  gap: 3px;
  background: #161b22;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  padding: 3px;
}}
.lang-btn {{
  flex: 1;
  text-align: center;
  padding: 5px 6px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-decoration: none;
  color: var(--text-muted);
  transition: all 0.15s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}}
.lang-btn:hover {{ color: var(--text-primary); background: rgba(255, 255, 255, 0.06); }}
.lang-btn.active {{
  background: #1f6feb;
  color: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}}

/* Search Box */
.search-wrapper {{
  position: relative;
  margin: 4px 0;
}}
.search-input {{
  width: 100%;
  padding: 8px 32px 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--border-strong);
  background: #161b22;
  color: var(--text-primary);
  font-size: 12.5px;
  font-family: inherit;
  transition: all 0.15s ease;
}}
.search-input:focus {{
  outline: none;
  border-color: var(--accent-blue);
  box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15);
}}
.search-shortcut {{
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 11px;
  color: var(--text-dim);
  background: var(--border-subtle);
  padding: 2px 5px;
  border-radius: 4px;
  border: 1px solid var(--border-strong);
  pointer-events: none;
}}

/* Navigation List */
.nav-group-title {{
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-dim);
  margin: 14px 6px 6px;
}}
.nav-list {{
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}}
.nav-link {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 12.5px;
  text-decoration: none;
  transition: all 0.15s ease;
}}
.nav-link:hover {{
  color: var(--text-primary);
  background: rgba(110, 118, 129, 0.12);
}}
.nav-link.active {{
  color: var(--accent-blue);
  background: rgba(56, 139, 253, 0.12);
  font-weight: 600;
  border-left: 2px solid var(--accent-blue);
  padding-left: 8px;
}}
.nav-icon {{
  font-size: 13px;
  width: 18px;
  display: inline-block;
  text-align: center;
}}

/* External Link Bar */
.external-links {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 10px 0;
  border-top: 1px solid var(--border-subtle);
  margin-top: 6px;
}}
.ext-chip {{
  font-size: 11px;
  color: var(--text-muted);
  text-decoration: none;
  background: #161b22;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 3px 8px;
  transition: all 0.15s ease;
}}
.ext-chip:hover {{
  color: var(--accent-blue);
  border-color: var(--border-strong);
}}

/* Presets & Author Cards */
.sidebar-card {{
  background: rgba(22, 27, 34, 0.7);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 12px;
}}
/* Main Content Area */
.wiki-main {{
  flex: 1;
  min-width: 0;
  padding: 0;
  overflow-y: auto;
  background: var(--bg-main);
}}

/* Top Sticky HUD */
.wiki-top-hud {{
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(13, 17, 23, 0.82);
  backdrop-filter: blur(16px) saturate(1.2);
  -webkit-backdrop-filter: blur(16px) saturate(1.2);
  border-bottom: 1px solid var(--border-subtle);
  padding: 8px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}}
.hud-stats {{
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}}
.hud-pill {{
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 20px;
  font-size: 11.5px;
  font-weight: 600;
  background: rgba(33, 38, 45, 0.7);
  border: 1px solid var(--border-subtle);
  color: var(--text-normal);
}}
.hud-pill.live-dot::before {{
  content: "";
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent-green);
  box-shadow: 0 0 6px rgba(63, 185, 80, 0.6);
}}
.hud-live-link {{
  color: var(--accent-green);
  text-decoration: none;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  background: rgba(63, 185, 80, 0.1);
  border: 1px solid rgba(63, 185, 80, 0.25);
  font-size: 12px;
  transition: all 0.15s ease;
}}
.hud-live-link:hover {{
  background: rgba(63, 185, 80, 0.2);
  border-color: var(--accent-green);
}}

/* Article Container */
.wiki-article {{
  max-width: 980px;
  margin: 0 auto;
  padding: 36px 32px 80px;
}}
.wiki-section {{
  scroll-margin-top: 70px;
  margin-bottom: 48px;
}}

/* Typography Inside Content */
h1 {{
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 18px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-subtle);
  letter-spacing: -0.01em;
}}
h2 {{
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 28px 0 14px;
  border-left: 3px solid var(--accent-blue);
  padding-left: 10px;
}}
h3 {{
  font-size: 14.5px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 20px 0 10px;
}}
h4 {{
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-normal);
  margin: 16px 0 8px;
}}
p {{
  margin: 0 0 14px;
  line-height: 1.68;
  color: var(--text-normal);
}}
blockquote {{
  margin: 16px 0;
  padding: 12px 16px;
  background: rgba(56, 139, 253, 0.08);
  border-left: 3px solid var(--accent-blue);
  border-radius: 0 8px 8px 0;
  color: var(--text-normal);
}}
blockquote p {{ margin: 0; }}
a {{ color: var(--accent-blue); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
ul, ol {{ padding-left: 22px; margin: 0 0 16px; }}
li {{ margin: 4px 0; line-height: 1.6; }}
hr {{ border: 0; border-top: 1px solid var(--border-subtle); margin: 32px 0; }}

/* Inline Code */
code {{
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: rgba(110, 118, 129, 0.18);
  color: var(--accent-orange);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid rgba(240, 246, 252, 0.08);
}}

/* Code Container with Copy Button */
.code-container {{
  position: relative;
  margin: 16px 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border-strong);
  background: #161b22;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}}
.code-container pre {{
  margin: 0;
  padding: 16px;
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: 12.5px;
  color: var(--text-primary);
  line-height: 1.55;
  background: transparent;
  border: none;
}}
.code-container pre code {{
  background: transparent;
  padding: 0;
  border: none;
  color: inherit;
}}
.copy-btn {{
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px 9px;
  font-size: 11px;
  font-family: var(--font-sans);
  background: rgba(33, 38, 45, 0.85);
  color: var(--text-muted);
  border: 1px solid var(--border-strong);
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.15s ease;
  backdrop-filter: blur(8px);
}}
.copy-btn:hover {{
  background: #30363d;
  color: #fff;
  border-color: var(--text-muted);
}}

/* Tables */
.table-wrapper {{
  margin: 16px 0;
  overflow-x: auto;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: #0d1117;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
  text-align: left;
}}
th {{
  background: #161b22;
  color: var(--text-primary);
  font-weight: 600;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-strong);
  white-space: nowrap;
}}
td {{
  padding: 9px 12px;
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-normal);
}}
tr:last-child td {{ border-bottom: none; }}
tr:hover td {{ background: rgba(56, 139, 253, 0.05); }}

/* Badges */
.badge {{
  display: inline-block;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 11px;
  border: 1px solid var(--border-strong);
  background: #161b22;
  color: var(--text-muted);
  margin: 2px;
}}

/* Toast Notifications */
#wiki-toast {{
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 10px 18px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  z-index: 100;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
  opacity: 0;
  transform: translateY(12px);
  transition: opacity 0.25s ease, transform 0.25s ease;
  pointer-events: none;
}}
#wiki-toast.toast-visible {{
  opacity: 1;
  transform: translateY(0);
}}
#wiki-toast.toast-success {{
  background: #238636;
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.2);
}}
#wiki-toast.toast-error {{
  background: #da3633;
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.2);
}}

/* Mobile Responsiveness */
.mobile-nav-toggle {{
  display: none;
  background: transparent;
  border: 1px solid var(--border-strong);
  color: var(--text-muted);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 14px;
  cursor: pointer;
}}
.mobile-overlay {{
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
  z-index: 15;
}}
@media (max-width: 860px) {{
  .wiki-layout {{ flex-direction: column; }}
  .wiki-sidebar {{
    position: fixed;
    left: -320px;
    width: 290px;
    transition: left 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 0 32px rgba(0,0,0,0.8);
  }}
  .wiki-sidebar.sidebar-open {{ left: 0; }}
  .mobile-overlay.overlay-open {{ display: block; }}
  .mobile-nav-toggle {{ display: inline-flex; align-items: center; justify-content: center; }}
  .wiki-article {{ padding: 20px 16px 60px; }}
  .wiki-top-hud {{ padding: 8px 16px; }}
}}
</style></head><body>
<div class="wiki-layout">
<div id="mobileOverlay" class="mobile-overlay" onclick="toggleSidebar()"></div>

<nav class="wiki-sidebar" id="wikiSidebar">
  <div class="wiki-brand">
    <div>
      <h2>📖 {wiki_heading}</h2>
      <div style="font-size:10.5px;color:var(--text-muted);margin-top:2px">Flatland Guide &amp; Living Encyclopedia</div>
    </div>
    <span class="version-tag">v0.1.6</span>
  </div>

  <div class="lang-switcher">
    <a href="/wiki?lang=en" class="lang-btn {btn_active_en}">🇬🇧 EN</a>
    <a href="/wiki?lang=vi" class="lang-btn {btn_active_vi}">🇻🇳 VI</a>
    <a href="/wiki?lang=fr" class="lang-btn {btn_active_fr}">🇫🇷 FR</a>
  </div>

  <div class="search-wrapper">
    <input id="q" class="search-input" placeholder="{search_placeholder}" oninput="filterWiki(this.value)">
    <span class="search-shortcut">/</span>
  </div>

  <div style="overflow-y:auto;flex:1;margin-right:-4px;padding-right:4px">
    <ul class="nav-list">
      {nav}
    </ul>

    <div class="external-links">
      <a href="/docs" class="ext-chip">📄 {swagger_docs}</a>
      <a href="/openapi.json" class="ext-chip">🌐 {openapi}</a>
      <a href="/api/wiki?lang={lang}" class="ext-chip">📦 {json_api}</a>
    </div>

    <div class="sidebar-card" style="margin-top:10px;border-color:rgba(88,166,255,0.3)">
      <div style="color:var(--text-muted);font-size:11px">{dev_by}</div>
      <strong style="color:var(--text-primary);font-size:13px">{dev_name}</strong>
      <div style="margin-top:4px;font-size:11px">
        <a href="mailto:long@minhnhan.in" style="color:var(--accent-blue)">long@minhnhan.in</a> · <a href="https://world.minhnhan.in" style="color:var(--accent-blue)">Demo</a>
      </div>
      <div style="color:var(--text-dim);font-size:10.5px;margin-top:4px">{built_with}</div>
    </div>
  </div>
</nav>

<main class="wiki-main">
  <header class="wiki-top-hud">
    <div style="display:flex;align-items:center;gap:10px">
      <button class="mobile-nav-toggle" onclick="toggleSidebar()" aria-label="Toggle menu">☰</button>
      <div class="hud-pill live-dot"><span>FLATLAND</span></div>
      <div class="hud-stats">
        <span class="hud-pill">⚖️ {badge_laws}</span>
        <span class="hud-pill">🌐 {badge_routes}</span>
        <span class="hud-pill">🎯 {badge_presets}</span>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:12px">
      <span style="font-size:12px;color:var(--text-muted)">{sphere_motto}</span>
      <a href="/docs" class="hud-pill" style="text-decoration:none;color:var(--accent-blue)">📄 Swagger /docs</a>
      <a href="/" class="hud-live-link">
        <span style="width:6px;height:6px;border-radius:50%;background:var(--accent-green);box-shadow:0 0 6px var(--accent-green)"></span>
        {live_world}
      </a>
    </div>
  </header>

  <article class="wiki-article">
    {content}
    <hr/>
    <p style="font-size:12px;color:var(--text-muted)">{footer}</p>
  </article>
</main>
</div>

<div id="wiki-toast"></div>

<script>
// Mobile Sidebar Toggle
function toggleSidebar() {{
  const sidebar = document.getElementById('wikiSidebar');
  const overlay = document.getElementById('mobileOverlay');
  sidebar.classList.toggle('sidebar-open');
  overlay.classList.toggle('overlay-open');
}}

// Search filter
function filterWiki(q){{
  q = q.toLowerCase();
  document.querySelectorAll('.wiki-section, h1, h2, table tr, p, li').forEach(el => {{
    if (!q) {{ el.style.display = ''; return; }}
    const txt = (el.textContent || '').toLowerCase();
    if (el.tagName === 'TR' || el.tagName === 'LI' || el.tagName === 'P') {{
      el.style.display = txt.includes(q) ? '' : 'none';
    }}
  }});
  document.querySelectorAll('.wiki-section').forEach(sec => {{
    const vis = [...sec.querySelectorAll('tr, li, p')].some(e => e.style.display !== 'none');
    const title = (sec.querySelector('h1, h2')?.textContent || '').toLowerCase();
    sec.style.display = (vis || title.includes(q) || !q) ? '' : 'none';
  }});
}}

// Keyboard shortcut '/' to search & Escape to clear
document.addEventListener('keydown', e => {{
  if (e.key === '/' && document.activeElement?.tagName !== 'INPUT') {{
    e.preventDefault();
    document.getElementById('q')?.focus();
  }} else if (e.key === 'Escape' && document.activeElement?.id === 'q') {{
    document.getElementById('q').value = '';
    filterWiki('');
    document.getElementById('q').blur();
  }}
}});

// Toast notification
function showToast(msg, isError = false) {{
  const toast = document.getElementById('wiki-toast');
  if (!toast) return;
  toast.innerText = msg;
  toast.className = 'toast-visible ' + (isError ? 'toast-error' : 'toast-success');
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => {{
    toast.className = '';
  }}, 3200);
}}

// Preset changes are reserved for the app UI and TUI — /wiki is read-only.
// Kept as a guidance stub so older cached pages degrade gracefully.
async function applyPreset(name) {{
  showToast('Presets can only be changed in the app UI or TUI', true);
}}

// Enhance code blocks with copy buttons
document.addEventListener('DOMContentLoaded', () => {{
  document.querySelectorAll('pre').forEach(pre => {{
    const wrapper = document.createElement('div');
    wrapper.className = 'code-container';
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(pre);

    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.innerText = 'Copy';
    copyBtn.onclick = () => {{
      navigator.clipboard.writeText(pre.innerText).then(() => {{
        copyBtn.innerText = '✓ Copied';
        copyBtn.style.color = '#3fb950';
        setTimeout(() => {{ copyBtn.innerText = 'Copy'; copyBtn.style.color = ''; }}, 1600);
      }});
    }};
    wrapper.appendChild(copyBtn);
  }});

  // Wrap tables without .table-wrapper
  document.querySelectorAll('table').forEach(tbl => {{
    if (!tbl.closest('.table-wrapper')) {{
      const wrapper = document.createElement('div');
      wrapper.className = 'table-wrapper';
      tbl.parentNode.insertBefore(wrapper, tbl);
      wrapper.appendChild(tbl);
    }}
  }});

  // Scroll spy with IntersectionObserver
  const sections = document.querySelectorAll('.wiki-section');
  const navLinks = document.querySelectorAll('.nav-link');
  const observer = new IntersectionObserver((entries) => {{
    entries.forEach(entry => {{
      if (entry.isIntersecting) {{
        const id = entry.target.getAttribute('id');
        navLinks.forEach(link => {{
          if (link.getAttribute('data-section') === id) {{
            link.classList.add('active');
          }} else {{
            link.classList.remove('active');
          }}
        }});
      }}
    }});
  }}, {{ rootMargin: '-15% 0px -70% 0px' }});

  sections.forEach(sec => observer.observe(sec));
}});

try {{ localStorage.setItem('flatland_lang', '{lang}'); }} catch(e){{}}
</script>
</body></html>
"""


def build_wiki_html(app: Any, lang: str = "en") -> str:
    from .main import PRESETS
    lang = normalize_lang(lang)
    ui = UI_I18N.get(lang, UI_I18N["en"])

    api_html = _md_to_html(ui["api_ref_title"]) + _api_table(app, lang=lang) + _curl_examples(lang=lang)
    laws_html = _md_to_html(ui["laws_title"]) + _god_laws_table(lang=lang)
    presets_html = _md_to_html(ui["presets_title"]) + _presets_table(lang=lang)

    overview_md = WIKI_OVERVIEW_MD_I18N.get(lang, WIKI_OVERVIEW_MD_I18N["en"])
    book_comp_md = FLATLAND_BOOK_COMPARISON_MD_I18N.get(lang, FLATLAND_BOOK_COMPARISON_MD_I18N["en"])
    sustainability_md = SUSTAINABILITY_MD_I18N.get(lang, SUSTAINABILITY_MD_I18N["en"])
    performance_md = PERFORMANCE_MD_I18N.get(lang, PERFORMANCE_MD_I18N["en"])

    how_it_works_md = HOW_IT_WORKS_MD_I18N.get(lang, HOW_IT_WORKS_MD_I18N["en"])
    config_ops_md = CONFIG_OPS_MD_I18N.get(lang, CONFIG_OPS_MD_I18N["en"])
    codebase_map_md = CODEBASE_MAP_MD_I18N.get(lang, CODEBASE_MAP_MD_I18N["en"])
    data_model_md = DATA_MODEL_MD_I18N.get(lang, DATA_MODEL_MD_I18N["en"])

    # Quickstart split per language
    if "## Run & deploy" in config_ops_md:
        quickstart_md = config_ops_md.split("## Run & deploy")[0]
    elif "## Khởi chạy & Vận hành" in config_ops_md:
        quickstart_md = config_ops_md.split("## Khởi chạy & Vận hành")[0]
    elif "## Exécution & Déploiement" in config_ops_md:
        quickstart_md = config_ops_md.split("## Exécution & Déploiement")[0]
    else:
        quickstart_md = config_ops_md

    section_bodies = {
        "overview": _md_to_html(overview_md),
        "book-comparison": _md_to_html(book_comp_md),
        "quickstart": _md_to_html(quickstart_md),
        "how-the-world-works": _md_to_html(how_it_works_md),
        "sustainability": _md_to_html(sustainability_md),
        "performance": _md_to_html(performance_md),
        "codebase-map": _md_to_html(codebase_map_md),
        "data-model-protocol": _md_to_html(data_model_md),
        "god-laws": laws_html,
        "presets": presets_html,
        "api-reference": api_html,
        "configuration-ops": _md_to_html(config_ops_md),
    }

    category_titles = {
        "core": ui["nav_group_core"],
        "systems": ui["nav_group_systems"],
        "reference": ui["nav_group_reference"],
    }

    nav_items = []
    content_parts = []
    current_category = None

    for slug, titles, cat, icon in NAV_SECTIONS:
        title = titles.get(lang, titles["en"])
        if cat != current_category:
            current_category = cat
            cat_label = category_titles.get(cat, cat.upper())
            nav_items.append(f'<li class="nav-group-title">{html.escape(cat_label)}</li>')

        nav_items.append(
            f'<li><a href="#{slug}" class="nav-link" data-section="{slug}">'
            f'<span class="nav-icon">{icon}</span> '
            f'<span>{html.escape(title)}</span></a></li>'
        )
        body = section_bodies.get(slug, "")
        content_parts.append(f'<section id="{slug}" class="wiki-section">{body}</section>')

    # Roadmap section at the end under reference
    roadmap_title = ui["roadmap_title"]
    roadmap_md = ui["roadmap_desc"].format(
        sections=len(NAV_SECTIONS) + 1,
        laws=len(GodLaws.model_fields),
        routes=len(app.routes),
        presets=len(PRESETS),
    )
    nav_items.append(
        f'<li><a href="#roadmap" class="nav-link" data-section="roadmap">'
        f'<span class="nav-icon">🗺️</span> '
        f'<span>{html.escape(roadmap_title)}</span></a></li>'
    )
    content_parts.append(f'<section id="roadmap" class="wiki-section">{_md_to_html(roadmap_md)}</section>')

    nav_html = "\n".join(nav_items)
    content_html = "\n<hr/>\n".join(content_parts)

    return WIKI_TEMPLATE.format(
        lang=lang,
        title=html.escape(ui["title"]),
        description=html.escape(ui["description"]),
        og_title=html.escape(ui["og_title"]),
        og_desc=html.escape(ui["og_desc"]),
        wiki_heading=html.escape(ui["wiki_heading"]),
        search_placeholder=html.escape(ui["search_placeholder"]),
        swagger_docs=html.escape(ui["swagger_docs"]),
        openapi=html.escape(ui["openapi"]),
        json_api=html.escape(ui["json_api"]),
        live_world=html.escape(ui["live_world"]),
        presets_label=html.escape(ui["presets_label"]),
        dev_by=html.escape(ui["dev_by"]),
        dev_name=html.escape(ui["dev_name"]),
        built_with=ui["built_with"],
        badge_laws=html.escape(ui["badge_laws"].format(laws=len(GodLaws.model_fields))),
        badge_routes=html.escape(ui["badge_routes"].format(routes=len(app.routes))),
        badge_presets=html.escape(ui["badge_presets"].format(presets=len(PRESETS))),
        sphere_motto=html.escape(ui["sphere_motto"]),
        footer=ui["footer"],
        btn_active_en="active" if lang == "en" else "",
        btn_active_vi="active" if lang == "vi" else "",
        btn_active_fr="active" if lang == "fr" else "",
        nav=nav_html,
        content=content_html,
    )


def get_wiki_json(app: Any, lang: str = "en") -> dict:
    from .main import PRESETS, detect_current_preset
    lang = normalize_lang(lang)
    hints = LAW_HINTS_I18N.get(lang, LAW_HINTS_I18N["en"])
    return {
        "lang": lang,
        "overview": WIKI_OVERVIEW_MD_I18N.get(lang, WIKI_OVERVIEW_MD_I18N["en"]),
        "book_comparison": FLATLAND_BOOK_COMPARISON_MD_I18N.get(lang, FLATLAND_BOOK_COMPARISON_MD_I18N["en"]),
        "sustainability": SUSTAINABILITY_MD_I18N.get(lang, SUSTAINABILITY_MD_I18N["en"]),
        "performance": PERFORMANCE_MD_I18N.get(lang, PERFORMANCE_MD_I18N["en"]),
        "how_it_works": HOW_IT_WORKS_MD_I18N.get(lang, HOW_IT_WORKS_MD_I18N["en"]),
        "codebase_map": CODEBASE_MAP_MD_I18N.get(lang, CODEBASE_MAP_MD_I18N["en"]),
        "data_model": DATA_MODEL_MD_I18N.get(lang, DATA_MODEL_MD_I18N["en"]),
        "config_ops": CONFIG_OPS_MD_I18N.get(lang, CONFIG_OPS_MD_I18N["en"]),
        "laws": list(GodLaws.model_fields.keys()),
        "routes": [getattr(r, "path", "") for r in app.routes],
        "presets": PRESETS,
        "current_preset": detect_current_preset(),
        "law_details": {
            name: {
                "type": str(f.annotation),
                "default": getattr(Config(), name, None) if hasattr(Config(), name) else None,
                "hint": hints.get(name, LAW_HINTS_I18N["en"].get(name, "")),
            }
            for name, f in GodLaws.model_fields.items()
        },
    }
