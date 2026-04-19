"""Notifications API - User notifications with SSE support."""

import asyncio
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.core.exceptions import NotFoundException
from app.services.sse_manager import sse_manager

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List notifications for the authenticated user."""
    result = await session.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(desc(Notification.created_at))
        .offset(skip)
        .limit(limit)
    )
    notifications = result.scalars().all()

    unread_result = await session.execute(
        select(Notification.id).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    unread_count = len(unread_result.scalars().all())

    return {
        "count": len(notifications),
        "unread_count": unread_count,
        "notifications": [
            {
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "notification_type": n.notification_type,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
    }


@router.get("/stream")
async def notification_stream(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    SSE endpoint for real-time notifications.

    Clients connect to this endpoint and receive notifications
    as Server-Sent Events.
    """
    user_id = str(current_user.id)
    queue = sse_manager.connect(user_id)

    async def event_generator():
        try:
            yield f": connected\n\n"

            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"

        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        finally:
            sse_manager.disconnect(user_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Mark notification as read."""
    result = await session.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise NotFoundException("Notification not found")

    notification.is_read = True
    await session.commit()

    return {"success": True}


@router.post("/read-all")
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Mark all notifications as read."""
    result = await session.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
        .values(is_read=True)
    )
    await session.commit()

    return {"success": True, "marked_count": result.rowcount}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a notification."""
    result = await session.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise NotFoundException("Notification not found")

    await session.delete(notification)
    await session.commit()

    return {"success": True}
