import os
import asyncio
from datetime import datetime, timedelta
from app.worker import celery_app


@celery_app.task(name="check_deadlines")
def check_deadlines():
    """Runs daily — checks for upcoming deadlines and sends alerts."""
    asyncio.run(_check())


async def _check():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.models import Alert, AlertStatus, Document, User
    from app.services.email import send_deadline_alert

    engine = create_async_engine(os.getenv("DATABASE_URL"))
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        now = datetime.utcnow()
        result = await db.execute(
            select(Alert).where(Alert.status == AlertStatus.active)
        )
        alerts = result.scalars().all()
        checked = 0
        sent = 0

        for alert in alerts:
            if not alert.deadline_date:
                continue

            days_until = (alert.deadline_date - now).days
            checked += 1

            # Send alert if within notify window
            if 0 <= days_until <= alert.notify_days_before:
                if alert.notify_email:
                    # Get creator email
                    creator = await db.get(User, alert.created_by)
                    doc = await db.get(Document, alert.document_id)
                    if creator and doc:
                        send_deadline_alert(
                            to_email=creator.email,
                            document_name=doc.filename,
                            alert_title=alert.title,
                            deadline_date=alert.deadline_date,
                            days_until=days_until,
                        )
                        sent += 1

                # Mark as triggered if deadline passed
                if days_until == 0:
                    alert.status = AlertStatus.triggered
                    alert.last_triggered_at = now

        await db.commit()
        print(f"[scheduler] Checked {checked} alerts, sent {sent} notifications")