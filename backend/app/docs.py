"""Self-hosted API documentation and route-specific CSP policies."""

from html import escape

from fastapi.responses import HTMLResponse


REACT_CSP = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; "
    "frame-ancestors 'none'; form-action 'self'; script-src 'self'; "
    "style-src 'self'; img-src 'self' data:; font-src 'self'; "
    "connect-src 'self'; manifest-src 'self'; worker-src 'self'"
)
SWAGGER_CSP = (
    "default-src 'none'; base-uri 'self'; object-src 'none'; "
    "frame-ancestors 'none'; form-action 'self'; script-src 'self'; "
    "style-src 'self'; img-src 'self' data:; font-src 'self'; "
    "connect-src 'self'"
)
JSON_CSP = "default-src 'none'; base-uri 'none'; frame-ancestors 'none'"


def swagger_ui_html(title: str) -> HTMLResponse:
    """Return Swagger UI using only local assets and no inline JavaScript."""
    safe_title = escape(title)
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <link rel="icon" href="/static/swagger-ui/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/static/swagger-ui/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="/static/swagger-ui/swagger-ui-bundle.js"></script>
  <script src="/static/swagger-ui/swagger-initializer.js"></script>
</body>
</html>""",
        headers={
            "Content-Security-Policy": SWAGGER_CSP,
            "Cache-Control": "no-store",
        },
    )
