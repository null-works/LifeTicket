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

Radicale is exposed on port **5232**. The CalDAV URL for external clients is:

```
https://calendar.kylem.cc:5232/lifeticket/lifeticket/
```

> If port 5232 isn't reachable externally, you'll need to open it in your firewall or add an Nginx proxy rule. See "Exposing Radicale" below.

**Android (DAVx5):**
1. Install [DAVx5](https://www.davx5.com/) from F-Droid or Play Store
2. Add account → **Login with URL and username**
3. Base URL: `https://calendar.kylem.cc:5232`
4. Username: `lifeticket` / Password: `lifeticket`
5. Select the **LifeTicket** calendar to sync

**iOS:**
1. Settings → Calendar → Accounts → Add Account → Other → Add CalDAV Account
2. Server: `calendar.kylem.cc:5232`
3. Username: `lifeticket` / Password: `lifeticket`

**Thunderbird / GNOME Calendar / other desktop apps:**
- Add a CalDAV/network calendar with the URL above and the same credentials.

### Exposing Radicale (optional Nginx config)

If you want to access Radicale over HTTPS through your existing Nginx setup, add a location block or a separate server block. For example, to proxy on a subpath:

```nginx
# Add to your existing calendar.kylem.cc server block
location /dav/ {
    proxy_pass http://127.0.0.1:5232/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Then use `https://calendar.kylem.cc/dav/lifeticket/lifeticket/` as the CalDAV URL in your apps.

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
