import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_client = None
_calendar = None


def _reset_client():
    """Reset cached client/calendar so next call re-reads settings."""
    global _client, _calendar
    _client = None
    _calendar = None


def _get_settings():
    """Read CalDAV settings from AppSettings, falling back to env vars."""
    from app.models import AppSettings
    s = AppSettings.get()
    return {
        "enabled": s.caldav_enabled if s.caldav_enabled is not None else False,
        "url": s.caldav_url or os.environ.get("RADICALE_URL", ""),
        "username": s.caldav_username or os.environ.get("RADICALE_USER", "lifeticket"),
        "password": s.caldav_password or os.environ.get("RADICALE_PASSWORD", "lifeticket"),
    }


def _get_calendar():
    """Return the CalDAV calendar object, creating it if needed."""
    global _client, _calendar
    if _calendar is not None:
        return _calendar

    from caldav import DAVClient
    settings = _get_settings()
    if not settings["url"]:
        return None

    _client = DAVClient(
        url=settings["url"],
        username=settings["username"],
        password=settings["password"],
        timeout=2,
    )
    principal = _client.principal()
    for cal in principal.calendars():
        if "lifeticket" in str(cal.url):
            _calendar = cal
            return _calendar
    _calendar = principal.make_calendar(name="LifeTicket", cal_id="lifeticket")
    return _calendar


def _event_uid(event_id):
    return f"event-{event_id}@lifeticket"


def _ticket_uid(ticket_id):
    return f"ticket-{ticket_id}@lifeticket"


def _build_vevent(uid, summary, dtstart, dtend=None, description="", all_day=True):
    """Build an iCalendar VEVENT string."""
    from icalendar import Calendar, Event as VEvent
    cal = Calendar()
    cal.add("prodid", "-//LifeTicket//EN")
    cal.add("version", "2.0")
    vevent = VEvent()
    vevent.add("uid", uid)
    vevent.add("summary", summary)
    vevent.add("dtstamp", datetime.utcnow())
    if all_day:
        vevent.add("dtstart", dtstart)
        vevent.add("dtend", dtstart + timedelta(days=1))
    else:
        vevent.add("dtstart", dtstart)
        vevent.add("dtend", dtend or (dtstart + timedelta(hours=1)))
    if description:
        vevent.add("description", description)
    cal.add_component(vevent)
    return cal.to_ical()


def _is_enabled():
    """Check if CalDAV sync is enabled."""
    settings = _get_settings()
    return settings["enabled"] and bool(settings["url"])


def sync_calendar_event(event):
    """Create or update a CalendarEvent in Radicale."""
    if not _is_enabled():
        return
    try:
        cal = _get_calendar()
        if not cal:
            return
        uid = _event_uid(event.id)
        if event.all_day:
            dtstart = event.date
            dtend = None
        else:
            dtstart = datetime.combine(event.date, event.start_time) if event.start_time else datetime.combine(event.date, datetime.min.time())
            dtend = datetime.combine(event.date, event.end_time) if event.end_time else None
        ical_data = _build_vevent(
            uid=uid,
            summary=event.title,
            dtstart=dtstart,
            dtend=dtend,
            description=event.description or "",
            all_day=event.all_day,
        )
        cal.save_event(ical_data)
        logger.info(f"CalDAV: synced event {uid}")
    except Exception:
        logger.exception(f"CalDAV: failed to sync event {event.id}")
        _reset_client()


def delete_calendar_event(event_id):
    """Delete a CalendarEvent from Radicale."""
    if not _is_enabled():
        return
    try:
        cal = _get_calendar()
        if not cal:
            return
        uid = _event_uid(event_id)
        event = cal.event_by_uid(uid)
        event.delete()
        logger.info(f"CalDAV: deleted event {uid}")
    except Exception:
        logger.exception(f"CalDAV: failed to delete event {event_id}")
        _reset_client()


def sync_ticket(ticket):
    """Sync a ticket's due date as a CalDAV event. Remove if no due date or closed."""
    if not _is_enabled():
        return
    try:
        from app.models import Status
        uid = _ticket_uid(ticket.id)
        closed_names = [s.name for s in Status.query.filter_by(is_closed=True).all()]
        if not ticket.due_date or ticket.status in closed_names:
            delete_ticket_event(ticket.id)
            return
        ical_data = _build_vevent(
            uid=uid,
            summary=f"[Ticket] {ticket.emoji + ' ' if ticket.emoji else ''}{ticket.title}",
            dtstart=ticket.due_date,
            description=ticket.description or "",
            all_day=True,
        )
        cal = _get_calendar()
        if not cal:
            return
        cal.save_event(ical_data)
        logger.info(f"CalDAV: synced ticket {uid}")
    except Exception:
        logger.exception(f"CalDAV: failed to sync ticket {ticket.id}")
        _reset_client()


def delete_ticket_event(ticket_id):
    """Delete a ticket due-date event from Radicale."""
    if not _is_enabled():
        return
    try:
        cal = _get_calendar()
        if not cal:
            return
        uid = _ticket_uid(ticket_id)
        event = cal.event_by_uid(uid)
        event.delete()
        logger.info(f"CalDAV: deleted ticket event {uid}")
    except Exception:
        logger.exception(f"CalDAV: failed to delete ticket event {ticket_id}")
        _reset_client()


def init_calendar():
    """Called on app startup to ensure the calendar collection exists."""
    if not _is_enabled():
        logger.info("CalDAV: sync disabled (not configured or not enabled)")
        return
    try:
        _get_calendar()
        logger.info("CalDAV: calendar collection ready")
    except Exception:
        logger.exception("CalDAV: failed to initialize (Radicale may not be running yet)")
        _reset_client()
