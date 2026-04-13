"""
IPT Scraper (in-process)

Python port of the Node/Puppeteer ipt-scraper microservice. Uses FlareSolverr
for Cloudflare bypass and regex/BS4 for HTML parsing. Persists known torrents
and latest results to JSON files alongside the rest of the api container data.

Public surface mirrors the old Node service so ipt_service.py's HTTP calls can
be replaced with direct method calls:
  - scan(on_log=None) -> list[dict]
  - get_latest_results() -> dict
  - get_known_torrents() -> list[dict]
  - clear_known_torrents() -> None
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_ROW_RE       = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_CELL_RE      = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
_TBODY_RE     = re.compile(r'<table\s+id="torrents"[^>]*>.*?<tbody>(.*?)</tbody>', re.DOTALL)
_TITLE_RE     = re.compile(r'<a[^>]*href="(?:https?://iptorrents\.com)?/t/\d+"[^>]*>([^<]+)<')
_ID_RE        = re.compile(r"download\.php/(\d+)")
_LINK_RE      = re.compile(r'href="((?:https?://iptorrents\.com)?/t/(\d+))"')
_SIZE_RE      = re.compile(r"([\d.]+\s*[KMGT]?B)")
_SUB_RE       = re.compile(r'<div class="sub">([^<]+)<')
_FILESAFE_RE  = re.compile(r"[^a-zA-Z0-9]")

KNOWN_LIMIT = 1000


def _settings():
    return get_settings()


def _data_dir() -> Path:
    # Lives under the api_data volume
    root = Path(os.getenv("IPT_DATA_DIR") or str(Path(_settings().DATA_DIR) / "ipt"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _known_file() -> Path:
    return _data_dir() / "known_torrents.json"


def _latest_file() -> Path:
    return _data_dir() / "latest_results.json"


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("ipt.scraper.read_failed", path=str(path), error=str(exc))
        return default


def _write_json_atomic(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _parse_torrents(html: str) -> list[dict[str, Any]]:
    tbody_match = _TBODY_RE.search(html)
    if not tbody_match:
        logger.warning("ipt.scraper.no_table_in_html")
        return []

    out: list[dict[str, Any]] = []
    for row_match in _ROW_RE.finditer(tbody_match.group(1)):
        row_html = row_match.group(1)
        cells = _CELL_RE.findall(row_html)
        if len(cells) < 9:
            continue

        name_cell = cells[1]
        title_match = _TITLE_RE.search(name_cell)
        if not title_match:
            continue
        title = title_match.group(1).strip()

        id_match = _ID_RE.search(cells[3])
        if not id_match:
            continue
        torrent_id = id_match.group(1)

        link_match = _LINK_RE.search(name_cell)
        if link_match:
            raw_link = link_match.group(1)
            link = raw_link if raw_link.startswith("http") else f"https://iptorrents.com{raw_link}"
        else:
            link = f"https://iptorrents.com/t/{torrent_id}"

        size_match = _SIZE_RE.search(cells[5])
        size = size_match.group(1).strip() if size_match else None

        try:
            seeders = int(re.sub(r"\D", "", cells[7].strip()) or 0)
        except ValueError:
            seeders = 0
        try:
            leechers = int(re.sub(r"\D", "", cells[8].strip()) or 0)
        except ValueError:
            leechers = 0

        is_new = 'class="tag">New<' in name_cell

        added = "Unknown"
        sub_match = _SUB_RE.search(name_cell)
        if sub_match:
            parts = sub_match.group(1).split("|")
            if len(parts) > 1:
                added = parts[1].strip()

        slug = _FILESAFE_RE.sub("_", title)
        out.append(
            {
                "id": torrent_id,
                "name": title,
                "link": link,
                "size": size,
                "seeders": seeders,
                "leechers": leechers,
                "added": added,
                "isNew": is_new,
                "downloadUrl": f"https://iptorrents.com/download.php/{torrent_id}/{slug}.torrent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    return out


class IPTScraper:
    """In-process IPTorrents scraper."""

    def __init__(self) -> None:
        s = _settings()
        self.flaresolverr_url: str | None = getattr(s, "FLARESOLVERR_URL", None) or os.getenv("FLARESOLVERR_URL")
        self.ipt_uid  = getattr(s, "IPT_UID", None)  or os.getenv("IPT_UID", "")
        self.ipt_pass = getattr(s, "IPT_PASS", None) or os.getenv("IPT_PASS", "")
        self.ipt_cf   = getattr(s, "IPT_CF_CLEARANCE", None) or os.getenv("IPT_CF_CLEARANCE", "")
        self.search_url = (
            getattr(s, "IPT_SEARCH_URL", None)
            or os.getenv("IPT_SEARCH_URL")
            or "https://iptorrents.com/t?q=BL%2BEL%2BRPU&qf=adv#torrents"
        )
        self.hide_cats = os.getenv("IPT_HIDE_CATS", "0")
        self.hide_top  = os.getenv("IPT_HIDE_TOP", "0")
        self.scan_pages = int(os.getenv("SCAN_PAGES", "1") or 1)

    async def _solve(self, url: str) -> str:
        if not self.flaresolverr_url:
            raise RuntimeError(
                "FLARESOLVERR_URL not configured. Set it in docker-compose env "
                "(e.g. http://flaresolverr:8191)."
            )

        cookies: list[dict[str, str]] = [
            {"name": "uid",  "value": self.ipt_uid},
            {"name": "pass", "value": self.ipt_pass},
        ]
        if self.ipt_cf:
            cookies.append({"name": "cf_clearance", "value": self.ipt_cf})
        if self.hide_cats and self.hide_cats != "0":
            cookies.append({"name": "hideCats", "value": self.hide_cats})
        if self.hide_top and self.hide_top != "0":
            cookies.append({"name": "hideTop", "value": self.hide_top})

        async with httpx.AsyncClient(timeout=65.0) as client:
            resp = await client.post(
                f"{self.flaresolverr_url}/v1",
                json={
                    "cmd": "request.get",
                    "url": url,
                    "maxTimeout": 60000,
                    "cookies": cookies,
                },
            )
            resp.raise_for_status()
            body = resp.json()

        if body.get("status") != "ok":
            raise RuntimeError(f"FlareSolverr failed: {body.get('message')}")

        return body["solution"]["response"]

    async def scan(
        self,
        on_log: Callable[[dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        def emit(message: str, **extra: Any) -> None:
            logger.info("ipt.scraper." + re.sub(r"\s+", "_", message.lower().strip())[:40], **extra)
            if on_log is not None:
                on_log(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": message,
                        **extra,
                    }
                )

        emit("Starting IPTorrents scan", search_term=os.getenv("IPT_SEARCH_TERM", "BL+EL+RPU"),
             pages=self.scan_pages)

        all_found: list[dict[str, Any]] = []
        for page in range(self.scan_pages):
            page_url = self.search_url if page == 0 else f"{self.search_url}&p={page}"
            emit(f"Fetching page {page + 1}/{self.scan_pages}...")
            emit("Solving Cloudflare challenge...")
            html = await self._solve(page_url)
            emit("Cloudflare challenge solved")
            page_torrents = _parse_torrents(html)
            emit(f"Page {page + 1} complete", torrents_found=len(page_torrents))
            all_found.extend(page_torrents)
            if page < self.scan_pages - 1:
                emit("Waiting before next page...")
                await asyncio.sleep(2.0)

        unique = list({t["id"]: t for t in all_found}.values())
        emit("Deduplication complete", unique_torrents=len(unique))

        emit("Checking for new torrents...")
        known = await asyncio.to_thread(_load_json, _known_file(), [])
        known_ids = {t["id"] for t in known}
        results = [{**t, "isNew": t["id"] not in known_ids} for t in unique]
        new_torrents = [t for t in results if t["isNew"]]

        if new_torrents:
            emit("New torrents discovered!", new_count=len(new_torrents))
            updated = known + [
                {k: v for k, v in t.items() if k != "isNew"} for t in new_torrents
            ]
            await asyncio.to_thread(_write_json_atomic, _known_file(), updated[-KNOWN_LIMIT:])
            emit("Cache updated")
        else:
            emit("No new torrents found")

        await asyncio.to_thread(
            _write_json_atomic,
            _latest_file(),
            {"timestamp": datetime.now(timezone.utc).isoformat(), "torrents": results},
        )

        emit("Scan complete!", total=len(results), new=len(new_torrents))
        return results

    async def scan_stream(self) -> AsyncIterator[dict[str, Any]]:
        """
        Async generator yielding log events then a final 'complete' event.
        Suitable for SSE endpoints.
        """
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        def _on_log(entry: dict[str, Any]) -> None:
            queue.put_nowait({"type": "log", **entry})

        async def _runner() -> None:
            try:
                results = await self.scan(on_log=_on_log)
                await queue.put(
                    {
                        "type": "complete",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "results": {
                            "total": len(results),
                            "new": sum(1 for r in results if r["isNew"]),
                        },
                    }
                )
            except Exception as exc:  # noqa: BLE001
                await queue.put(
                    {
                        "type": "error",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": str(exc),
                    }
                )
            finally:
                await queue.put({"type": "__done__"})

        task = asyncio.create_task(_runner())
        try:
            while True:
                event = await queue.get()
                if event.get("type") == "__done__":
                    break
                yield event
        finally:
            if not task.done():
                task.cancel()

    async def get_latest_results(self) -> dict[str, Any]:
        data = await asyncio.to_thread(
            _load_json, _latest_file(), {"timestamp": None, "torrents": []}
        )
        return data

    async def get_known_torrents(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(_load_json, _known_file(), [])

    async def clear_known_torrents(self) -> None:
        await asyncio.to_thread(_write_json_atomic, _known_file(), [])
        logger.info("ipt.scraper.known_cleared")


# Module-level singleton used by ipt_service.py
_default: IPTScraper | None = None


def get_scraper() -> IPTScraper:
    global _default
    if _default is None:
        _default = IPTScraper()
    return _default
