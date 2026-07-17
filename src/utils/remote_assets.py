from __future__ import annotations

from urllib.parse import urljoin

def catalog_repo_base(catalog_url: str) -> str:
    url = catalog_url.strip()
    if url.endswith("/"):
        url = url[:-1]
    if url.endswith("games.json"):
        url = url[: -len("games.json")]
    if url.endswith("data/"):
        url = url[: -len("data/")]
    elif url.endswith("data"):
        url = url[: -len("data")]
    if not url.endswith("/"):
        url += "/"
    return url

def resolve_icon_url(icon: str | None, catalog_url: str) -> str | None:
    if not icon:
        return None
    icon = icon.strip().replace("\\", "/")
    if icon.startswith("http://") or icon.startswith("https://"):
        return icon
    return urljoin(catalog_repo_base(catalog_url), icon.lstrip("/"))
