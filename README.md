# LifeTicket

Personal ticketing system for managing chores, gig work, and life tasks.

## Deployment

### 1. DNS Setup

Add an **A record** for `calendar.kylem.cc` pointing to the `inklit.ch` server IP:

```
Type: A
Name: calendar
Value: <inklit.ch server IP>
TTL: 300
```

### 2. Install

```bash
git clone https://github.com/null-works/LifeTicket.git
cd LifeTicket
sudo ./install.sh
```

This handles everything: generates `.env`, builds the Docker container, configures Nginx, and obtains an SSL cert via Certbot.

The app will be live at **https://calendar.kylem.cc**

## Maintenance

```bash
# Pull updates and redeploy
cd LifeTicket
git pull
docker compose up -d --build

# Backup the database
docker compose cp lifeticket:/data/lifeticket.db ./backup-$(date +%Y%m%d).db

# View logs
docker compose logs -f lifeticket
```

## CalDAV Sync (Radicale)

LifeTicket can sync calendar events and ticket due dates to a built-in [Radicale](https://radicale.org/) CalDAV server. This lets you subscribe from your phone, Thunderbird, Roundcube, or any CalDAV-compatible app and see your LifeTicket events alongside your other calendars.

### How it works

When you create, edit, or delete a calendar event in LifeTicket, the change is automatically pushed to Radicale. Ticket due dates are synced too — when a ticket is resolved or closed, its calendar entry is removed.

Sync is best-effort: if Radicale is temporarily unreachable, LifeTicket continues working normally and the next operation will reconnect.

### Setup

1. **Start the stack** — Radicale runs automatically as a sidecar container:

   ```bash
   docker compose up -d --build
   ```

2. **Enable sync** — Go to **Settings** in LifeTicket and find the **CalDAV Sync** section. The connection details are pre-filled for the bundled Radicale instance. Just check **Enable CalDAV sync** and click **Save CalDAV Settings**.

3. **That's it.** New events and ticket due dates will now sync to Radicale.

### Connecting your devices

Radicale is proxied through Nginx at `/dav/`. The CalDAV URL for external clients is:

```
https://calendar.kylem.cc/dav/lifeticket/lifeticket/
```

**Android:**
1. Install a CalDAV sync app (e.g. DAVx5, ICSx5) from F-Droid or Play Store
2. Add account → Base URL: `https://calendar.kylem.cc/dav/`
3. Username: `lifeticket` / Password: `lifeticket`
4. Select the **LifeTicket** calendar to sync

**iOS:**
1. Settings → Calendar → Accounts → Add Account → Other → Add CalDAV Account
2. Server: `calendar.kylem.cc/dav/`
3. Username: `lifeticket` / Password: `lifeticket`

**Thunderbird / GNOME Calendar / other desktop apps:**
- Add a CalDAV/network calendar with the URL above and the same credentials.

### Changing the Radicale password

1. Edit `radicale/htpasswd` and change the password
2. Update the password in LifeTicket **Settings → CalDAV Sync**
3. Restart: `docker compose restart radicale`
4. Update the password in any connected CalDAV clients

### Backfilling existing events

Events created before enabling CalDAV sync won't be in Radicale automatically. To do a one-time backfill, open a Flask shell:

```bash
docker compose exec lifeticket python -c "
from app import create_app
from app.models import CalendarEvent, Ticket, Status
from app.caldav_sync import sync_calendar_event, sync_ticket

app = create_app()
with app.app_context():
    for ev in CalendarEvent.query.all():
        sync_calendar_event(ev)
        print(f'Synced event: {ev.title}')
    closed = [s.name for s in Status.query.filter_by(is_closed=True).all()]
    for t in Ticket.query.filter(Ticket.due_date.isnot(None)).all():
        if t.status not in closed:
            sync_ticket(t)
            print(f'Synced ticket: {t.title}')
"
```

## Local Development

```bash
pip install -r requirements.txt
python run.py
# Open http://localhost:5000
```
