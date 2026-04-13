"""
Visualization Proxy
Proxies chart-generation requests to AntV GPT-Vis API so the browser
can avoid CORS. Returns the hosted chart image URL.
"""
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

ANTV_ENDPOINT = "https://antv-studio.alipay.com/api/gpt-vis"


class ChartRequest(BaseModel):
    """Minimal wrapper — forwarded to AntV as-is plus our source tag."""

    type: str
    data: Any = None
    title: str | None = None
    theme: str | None = "dark"
    width: int | None = 800
    height: int | None = 400
    # Chart-specific extras (e.g. innerRadius, binNumber, orient, percent, stack,
    # group, axisXTitle, axisYTitle, nodeAlign, shape, categories, series, nodes,
    # edges…). Kept open so we don't need a schema per chart type.
    extra: dict[str, Any] | None = None


class ChartResponse(BaseModel):
    url: str


@router.post("/chart", response_model=ChartResponse)
async def generate_chart(req: ChartRequest) -> ChartResponse:
    """
    Forward a chart spec to AntV and return the hosted image URL.
    """
    payload: dict[str, Any] = {
        "type": req.type,
        "source": "chart-visualization-skills",
        "theme": req.theme or "dark",
        "width": req.width or 800,
        "height": req.height or 400,
    }
    if req.title:
        payload["title"] = req.title
    if req.data is not None:
        payload["data"] = req.data
    if req.extra:
        payload.update(req.extra)

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(ANTV_ENDPOINT, json=payload)
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("antv_chart_request_failed", error=str(exc), chart_type=req.type)
        raise HTTPException(status_code=502, detail="Chart service unavailable") from exc

    if not body.get("success"):
        logger.warning("antv_chart_error", body=body)
        raise HTTPException(status_code=502, detail=body.get("errorMessage", "Chart generation failed"))

    url = body.get("resultObj")
    if not isinstance(url, str) or not url.startswith("http"):
        raise HTTPException(status_code=502, detail="Chart service returned no URL")

    return ChartResponse(url=url)
