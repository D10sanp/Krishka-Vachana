"""Tiny HTML helpers for the backend's own docs/status pages.

Not part of the frontend app (that's the Frontend role's Next.js app under
frontend/). This is just enough branding on FastAPI's built-in docs and a
plain status page so anyone opening the API's own URLs during dev/demo
sees something that looks like Krishka Vachana instead of a bare default page.
Colors are taken from the repo's UI_rules.md "Color System" section so the
two stay visually consistent, not because this backend page is meant to be
a real product surface.
"""

BRAND = {
    "primary_dark": "#123524",
    "primary": "#1F6B45",
    "primary_button": "#2E8B57",
    "primary_light": "#DDF3E6",
    "bg": "#F8FAF9",
    "card_bg": "#FFFFFF",
    "text": "#17201B",
    "muted": "#68756D",
    "border": "#E5EAE7",
    "success": "#16803C",
    "success_bg": "#E8F7ED",
    "error": "#C53030",
    "error_bg": "#FDECEC",
    "warning": "#B7791F",
    "warning_bg": "#FFF6DE",
}

BASE_STYLE = f"""
  body {{
    font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: {BRAND['bg']};
    color: {BRAND['text']};
    margin: 0;
    padding: 0;
  }}
  .topbar {{
    background: {BRAND['card_bg']};
    border-bottom: 1px solid {BRAND['border']};
    padding: 16px 24px;
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .topbar .dot {{
    width: 10px; height: 10px; border-radius: 9999px; background: {BRAND['primary_button']};
  }}
  .topbar h1 {{
    font-size: 18px; font-weight: 600; margin: 0; color: {BRAND['primary_dark']};
  }}
  .container {{
    max-width: 880px;
    margin: 0 auto;
    padding: 24px;
  }}
  .card {{
    background: {BRAND['card_bg']};
    border: 1px solid {BRAND['border']};
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  }}
  .badge {{
    display: inline-block;
    border-radius: 9999px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 500;
  }}
  .badge-ok {{ background: {BRAND['success_bg']}; color: {BRAND['success']}; }}
  .badge-warn {{ background: {BRAND['warning_bg']}; color: {BRAND['text']}; }}
  .badge-error {{ background: {BRAND['error_bg']}; color: {BRAND['error']}; }}
  a.link {{ color: {BRAND['primary']}; text-decoration: none; font-weight: 500; }}
  a.link:hover {{ text-decoration: underline; }}
  code {{
    background: {BRAND['primary_light']};
    color: {BRAND['primary_dark']};
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{ text-align: left; padding: 8px 4px; border-bottom: 1px solid {BRAND['border']}; }}
  th {{ color: {BRAND['muted']}; font-weight: 600; }}
"""


def page_shell(title: str, body_html: str) -> str:
    """Wrap body HTML in a branded page shell with consistent styling."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>{BASE_STYLE}</style>
</head>
<body>
  <div class="topbar">
    <span class="dot"></span>
    <h1>Krishka Vachana API</h1>
  </div>
  <div class="container">
    {body_html}
  </div>
</body>
</html>"""
