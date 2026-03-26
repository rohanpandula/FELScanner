"""
Scan API Endpoints
Trigger scans, get status, view scan history
"""
import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, get_session_factory
from app.core.logging import get_logger
from app.schemas.scan import (
    ScanHistoryListResponse,
    ScanHistoryResponse,
    ScanStatusResponse,
    ScanTriggerRequest,
)
from app.services.scan_service import ScanService

router = APIRouter()
logger = get_logger(__name__)


@router.post("/trigger", response_model=ScanHistoryResponse)
async def trigger_scan(
    request: ScanTriggerRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a library scan

    Starts a full scan of the Plex library with DV profile detection.
    Returns immediately with scan record. Use /scan/status to monitor progress.
    """
    service = ScanService(db)

    try:
        scan_record = await service.trigger_full_scan(
            trigger=request.trigger,
            triggered_by=request.triggered_by,
        )
        return scan_record
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("scan.trigger_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to trigger scan")


@router.get("/trigger/stream")
async def trigger_scan_stream():
    """
    Trigger a library scan with SSE streaming progress

    Returns a Server-Sent Events stream with real-time progress updates.
    Use this for manual scans to see live progress in the UI.
    """
    logger.info("scan.stream_triggered")

    async def generate_events() -> AsyncGenerator[bytes, None]:
        # Use a queue to collect progress updates
        progress_queue: asyncio.Queue = asyncio.Queue()

        def on_progress(message: str, scanned: int, total: int, current_movie: str | None):
            """Callback that puts progress updates into the queue"""
            event = {
                "type": "log",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": message,
                "scanned": scanned,
                "total": total,
                "current_movie": current_movie,
                "progress": int((scanned / total * 100)) if total > 0 else 0,
            }
            # Use call_soon_threadsafe in case called from different context
            try:
                progress_queue.put_nowait(event)
            except Exception:
                pass

        async def run_scan():
            """Run the scan in the background"""
            session_factory = get_session_factory()
            async with session_factory() as db:
                service = ScanService(db)
                try:
                    result = await service.trigger_full_scan(
                        trigger="manual",
                        triggered_by="web_ui",
                        on_progress=on_progress,
                    )
                    # Send completion event
                    await progress_queue.put({
                        "type": "complete",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": "Scan complete!",
                        "results": {
                            "movies_scanned": result.movies_scanned,
                            "dv_discovered": result.dv_discovered,
                            "fel_discovered": result.fel_discovered,
                            "atmos_discovered": result.atmos_discovered,
                        },
                    })
                except RuntimeError as e:
                    await progress_queue.put({
                        "type": "error",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": str(e),
                    })
                except Exception as e:
                    await progress_queue.put({
                        "type": "error",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": f"Scan failed: {str(e)}",
                    })
                finally:
                    # Signal end of stream
                    await progress_queue.put(None)

        # Start the scan task
        scan_task = asyncio.create_task(run_scan())

        try:
            # Stream events from the queue
            while True:
                try:
                    event = await asyncio.wait_for(progress_queue.get(), timeout=120.0)
                    if event is None:
                        break
                    yield f"data: {json.dumps(event)}\n\n".encode()
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n".encode()
        finally:
            if not scan_task.done():
                scan_task.cancel()

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/status", response_model=ScanStatusResponse)
async def get_scan_status(db: AsyncSession = Depends(get_db)):
    """
    Get current scan status

    Returns information about any running scan and the most recent completed scan.
    """
    from datetime import datetime, timezone

    service = ScanService(db)

    is_running = await service.is_scan_running()
    current_scan = await service.get_current_scan()

    # Get last completed scan
    scans, _ = await service.get_scan_history(limit=1)
    last_scan = scans[0] if scans else None

    # Determine state
    if is_running and current_scan:
        if current_scan.scan_type == "verify":
            state = "verifying"
        else:
            state = "scanning"
    elif last_scan and last_scan.status == "failed":
        state = "idle"  # Still idle, just last scan failed
    else:
        state = "idle"

    # Calculate elapsed time
    elapsed_time = 0
    if current_scan and current_scan.started_at:
        started = current_scan.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        elapsed_time = int((now - started).total_seconds())

    response = ScanStatusResponse(
        state=state,
        progress=0,  # TODO: Add real-time progress tracking
        current_movie=None,  # TODO: Track current movie
        total_movies=current_scan.movies_scanned if current_scan else 0,
        scanned_count=current_scan.movies_scanned if current_scan else 0,
        message=None,
        start_time=current_scan.started_at if current_scan else None,
        elapsed_time=elapsed_time,
        is_running=is_running,
        scan_id=current_scan.id if current_scan else None,
        scan_type=current_scan.scan_type if current_scan else None,
        last_scan=last_scan,
    )

    return response


@router.get("/history", response_model=ScanHistoryListResponse)
async def get_scan_history(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    Get scan history with pagination

    Returns list of all scan operations with statistics and performance metrics.
    """
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="page_size must be between 1 and 100")

    service = ScanService(db)
    offset = (page - 1) * page_size

    scans, total = await service.get_scan_history(limit=page_size, offset=offset)

    return ScanHistoryListResponse(
        total=total,
        page=page,
        page_size=page_size,
        scans=scans,
    )


@router.get("/history/{scan_id}", response_model=ScanHistoryResponse)
async def get_scan_by_id(
    scan_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get details of a specific scan

    Returns full scan record including all statistics and metadata.
    """
    service = ScanService(db)
    scan = await service.get_scan_by_id(scan_id)

    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    return scan
