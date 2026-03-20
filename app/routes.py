import os
import uuid
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app, send_from_directory
from flask_login import login_required
from werkzeug.utils import secure_filename
from app import db
from app.models import Ticket, Category, Tag, GroceryItem, CalendarEvent, Status, TicketComment, TicketAttachment, TicketHistory, JobApplication, JOB_STATUSES
from datetime import date, datetime, time
import calendar as cal_mod

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'pdf', 'txt', 'md', 'zip', 'csv', 'doc', 'docx', 'xls', 'xlsx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

main = Blueprint("main", __name__)
api = Blueprint("api", __name__)


# --- Page Routes ---


@main.route("/")
@login_required
def home():
    today_date = date.today()
    tickets = Ticket.query.all()
    statuses = Status.query.order_by(Status.position).all()
    closed_names = {s.name for s in statuses if s.is_closed}
    open_tickets = [t for t in tickets if t.status not in closed_names]

    ticket_stats = {
        "total": len(tickets),
        "open": len(open_tickets),
        "overdue": sum(1 for t in open_tickets if t.due_date and t.due_date < today_date),
        "urgent": sum(1 for t in open_tickets if t.priority == "urgent"),
    }

    job_apps = JobApplication.query.all()
    active_jobs = [j for j in job_apps if j.is_active]
    job_stats = {
        "total": len(job_apps),
        "active": len(active_jobs),
        "interviews": sum(1 for j in active_jobs if j.date_interview and j.date_interview >= today_date),
        "offers": sum(1 for j in job_apps if j.status == "offer"),
    }

    grocery_items = GroceryItem.query.all()
    grocery_stats = {
        "total": len(grocery_items),
        "unchecked": sum(1 for g in grocery_items if not g.checked),
    }

    from app.models import CalendarEvent as CE
    upcoming_events = CE.query.filter(CE.date >= today_date).order_by(CE.date, CE.start_time).limit(5).all()

    recent_tickets = sorted(tickets, key=lambda t: t.created_at, reverse=True)[:5]
    recent_jobs = sorted(job_apps, key=lambda j: j.updated_at, reverse=True)[:5]

    return render_template(
        "home.html",
        ticket_stats=ticket_stats,
        job_stats=job_stats,
        grocery_stats=grocery_stats,
        upcoming_events=upcoming_events,
        recent_tickets=recent_tickets,
        recent_jobs=recent_jobs,
        statuses=statuses,
    )


@main.route("/tickets")
@login_required
def tickets_dashboard():
    tickets = Ticket.query.all()
    categories = Category.query.order_by(Category.name).all()
    statuses = Status.query.order_by(Status.position).all()
    today_date = date.today()

    closed_names = {s.name for s in statuses if s.is_closed}
    status_counts = {s.name: 0 for s in statuses}
    for t in tickets:
        if t.status in status_counts:
            status_counts[t.status] += 1

    stats = {
        "total": len(tickets),
        "overdue": sum(
            1
            for t in tickets
            if t.due_date and t.due_date < today_date and t.status not in closed_names
        ),
        "urgent": sum(1 for t in tickets if t.priority == "urgent" and t.status not in closed_names),
    }
    return render_template(
        "tickets_dashboard.html", stats=stats, statuses=statuses, status_counts=status_counts,
        categories=categories, tickets=tickets,
    )


@main.route("/board")
@login_required
def board():
    category_id = request.args.get("category", type=int)
    query = Ticket.query
    if category_id:
        query = query.filter_by(category_id=category_id)

    tickets = query.all()
    categories = Category.query.order_by(Category.name).all()
    statuses = Status.query.order_by(Status.position).all()
    columns = {s.name: [t for t in tickets if t.status == s.name] for s in statuses}
    return render_template(
        "board.html",
        columns=columns,
        statuses=statuses,
        categories=categories,
        selected_category=category_id,
    )


@main.route("/list")
@login_required
def ticket_list():
    status = request.args.get("status")
    priority = request.args.get("priority")
    category_id = request.args.get("category", type=int)
    sort = request.args.get("sort", "created_at")
    order = request.args.get("order", "desc")

    overdue = request.args.get("overdue")

    query = Ticket.query
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if overdue:
        closed_names = [s.name for s in Status.query.filter_by(is_closed=True).all()]
        query = query.filter(
            Ticket.due_date < date.today(),
            Ticket.status.notin_(closed_names),
        )

    sort_col = getattr(Ticket, sort, Ticket.created_at)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    tickets = query.all()
    categories = Category.query.order_by(Category.name).all()
    statuses = Status.query.order_by(Status.position).all()
    return render_template("list.html", tickets=tickets, categories=categories, statuses=statuses)


@main.route("/ticket/new", methods=["GET", "POST"])
@login_required
def ticket_new():
    if request.method == "POST":
        ticket = _save_ticket(Ticket(), request.form)
        db.session.add(ticket)
        db.session.commit()
        return redirect(url_for("main.ticket_view", ticket_id=ticket.id))

    categories = Category.query.order_by(Category.name).all()
    tags = Tag.query.order_by(Tag.name).all()
    statuses = Status.query.order_by(Status.position).all()
    return render_template("ticket_form.html", ticket=None, categories=categories, tags=tags, statuses=statuses)


@main.route("/ticket/<int:ticket_id>/edit", methods=["GET", "POST"])
@login_required
def ticket_edit(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if request.method == "POST":
        _save_ticket(ticket, request.form)
        db.session.commit()
        return redirect(url_for("main.ticket_view", ticket_id=ticket.id))

    categories = Category.query.order_by(Category.name).all()
    tags = Tag.query.order_by(Tag.name).all()
    statuses = Status.query.order_by(Status.position).all()
    return render_template("ticket_form.html", ticket=ticket, categories=categories, tags=tags, statuses=statuses)


@main.route("/ticket/<int:ticket_id>/delete", methods=["POST"])
@login_required
def ticket_delete(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    db.session.delete(ticket)
    db.session.commit()
    return redirect(url_for("main.tickets_dashboard"))


@main.route("/ticket/<int:ticket_id>")
@login_required
def ticket_view(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    statuses = Status.query.order_by(Status.position).all()
    return render_template("ticket_view.html", ticket=ticket, statuses=statuses)


@main.route("/ticket/<int:ticket_id>/comment", methods=["POST"])
@login_required
def ticket_add_comment(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    body = request.form.get("body", "").strip()
    if body:
        comment = TicketComment(ticket_id=ticket.id, body=body)
        db.session.add(comment)
        db.session.commit()
    return redirect(url_for("main.ticket_view", ticket_id=ticket.id))


@main.route("/ticket/<int:ticket_id>/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def ticket_delete_comment(ticket_id, comment_id):
    comment = TicketComment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for("main.ticket_view", ticket_id=ticket_id))


@main.route("/ticket/<int:ticket_id>/upload", methods=["POST"])
@login_required
def ticket_upload(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    file = request.files.get("file")
    if not file or not file.filename:
        return redirect(url_for("main.ticket_view", ticket_id=ticket.id))

    original = secure_filename(file.filename)
    ext = os.path.splitext(original)[1].lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        return redirect(url_for("main.ticket_view", ticket_id=ticket.id))

    upload_dir = os.path.join(current_app.root_path, "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}_{original}"
    path = os.path.join(upload_dir, unique_name)
    file.save(path)
    size = os.path.getsize(path)

    if size > MAX_FILE_SIZE:
        os.remove(path)
        return redirect(url_for("main.ticket_view", ticket_id=ticket.id))

    attachment = TicketAttachment(
        ticket_id=ticket.id,
        filename=unique_name,
        original_name=original,
        size=size,
    )
    db.session.add(attachment)
    db.session.commit()
    return redirect(url_for("main.ticket_view", ticket_id=ticket.id))


@main.route("/ticket/<int:ticket_id>/attachment/<int:att_id>/delete", methods=["POST"])
@login_required
def ticket_delete_attachment(ticket_id, att_id):
    att = TicketAttachment.query.get_or_404(att_id)
    filepath = os.path.join(current_app.root_path, "static", "uploads", att.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(att)
    db.session.commit()
    return redirect(url_for("main.ticket_view", ticket_id=ticket_id))


@main.route("/categories", methods=["GET", "POST"])
@login_required
def manage_categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        color = request.form.get("color", "#6366f1")
        if name:
            cat = Category(name=name, color=color)
            db.session.add(cat)
            db.session.commit()
        return redirect(url_for("main.manage_categories"))

    categories = Category.query.order_by(Category.name).all()
    return render_template("categories.html", categories=categories)


@main.route("/categories/<int:cat_id>/delete", methods=["POST"])
@login_required
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    db.session.delete(cat)
    db.session.commit()
    return redirect(url_for("main.manage_categories"))


@main.route("/statuses", methods=["GET", "POST"])
@login_required
def manage_statuses():
    if request.method == "POST":
        name = request.form.get("name", "").strip().lower().replace(" ", "_")
        label = request.form.get("label", "").strip()
        color = request.form.get("color", "#6366f1")
        is_closed = request.form.get("is_closed") == "on"
        if name and label and not Status.query.filter_by(name=name).first():
            max_pos = db.session.query(db.func.max(Status.position)).scalar() or 0
            s = Status(name=name, label=label, color=color, is_closed=is_closed, position=max_pos + 1)
            db.session.add(s)
            db.session.commit()
        return redirect(url_for("main.manage_statuses"))

    statuses = Status.query.order_by(Status.position).all()
    return render_template("statuses.html", statuses=statuses)


@main.route("/statuses/<int:status_id>/delete", methods=["POST"])
@login_required
def delete_status(status_id):
    status = Status.query.get_or_404(status_id)
    # Re-assign any tickets with this status to the first available status
    fallback = Status.query.filter(Status.id != status_id).order_by(Status.position).first()
    if fallback:
        Ticket.query.filter_by(status=status.name).update({"status": fallback.name})
    db.session.delete(status)
    db.session.commit()
    return redirect(url_for("main.manage_statuses"))


@main.route("/statuses/<int:status_id>/edit", methods=["POST"])
@login_required
def edit_status(status_id):
    status = Status.query.get_or_404(status_id)
    label = request.form.get("label", "").strip()
    color = request.form.get("color", status.color)
    is_closed = request.form.get("is_closed") == "on"
    if label:
        status.label = label
    status.color = color
    status.is_closed = is_closed
    db.session.commit()
    return redirect(url_for("main.manage_statuses"))


@main.route("/statuses/reorder", methods=["POST"])
@login_required
def reorder_statuses():
    order = request.get_json()
    if order and isinstance(order, list):
        for i, status_id in enumerate(order):
            s = Status.query.get(status_id)
            if s:
                s.position = i
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({"error": "Invalid data"}), 400


@main.route("/grocery", methods=["GET", "POST"])
@login_required
def grocery():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        quantity = request.form.get("quantity", "").strip()
        aisle = request.form.get("aisle", "").strip()
        if name:
            item = GroceryItem(name=name, quantity=quantity, aisle=aisle)
            db.session.add(item)
            db.session.commit()
        return redirect(url_for("main.grocery"))

    items = GroceryItem.query.order_by(GroceryItem.checked, GroceryItem.created_at.desc()).all()
    return render_template("grocery.html", items=items)


@main.route("/grocery/<int:item_id>/delete", methods=["POST"])
@login_required
def grocery_delete(item_id):
    item = GroceryItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("main.grocery"))


@main.route("/grocery/clear-checked", methods=["POST"])
@login_required
def grocery_clear_checked():
    GroceryItem.query.filter_by(checked=True).delete()
    db.session.commit()
    return redirect(url_for("main.grocery"))


@main.route("/jobs", methods=["GET", "POST"])
@login_required
def jobs():
    if request.method == "POST":
        company = request.form.get("company", "").strip()
        position = request.form.get("position", "").strip()
        if company and position:
            job = JobApplication(
                company=company,
                position=position,
                url=request.form.get("url", "").strip(),
                status=request.form.get("status", "bookmarked"),
                salary=request.form.get("salary", "").strip(),
                location=request.form.get("location", "").strip(),
                notes=request.form.get("notes", "").strip(),
            )
            da = request.form.get("date_applied")
            job.date_applied = date.fromisoformat(da) if da else None
            di = request.form.get("date_interview")
            job.date_interview = date.fromisoformat(di) if di else None
            df = request.form.get("date_followup")
            job.date_followup = date.fromisoformat(df) if df else None
            db.session.add(job)
            db.session.commit()
        return redirect(url_for("main.jobs"))

    status_filter = request.args.get("status")
    query = JobApplication.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    jobs_list = query.order_by(JobApplication.updated_at.desc()).all()
    return render_template("jobs.html", jobs=jobs_list, job_statuses=JOB_STATUSES, editing=None)


@main.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
def job_edit(job_id):
    job = JobApplication.query.get_or_404(job_id)
    if request.method == "POST":
        job.company = request.form.get("company", "").strip() or job.company
        job.position = request.form.get("position", "").strip() or job.position
        job.url = request.form.get("url", "").strip()
        job.status = request.form.get("status", job.status)
        job.salary = request.form.get("salary", "").strip()
        job.location = request.form.get("location", "").strip()
        job.notes = request.form.get("notes", "").strip()
        da = request.form.get("date_applied")
        job.date_applied = date.fromisoformat(da) if da else None
        di = request.form.get("date_interview")
        job.date_interview = date.fromisoformat(di) if di else None
        df = request.form.get("date_followup")
        job.date_followup = date.fromisoformat(df) if df else None
        db.session.commit()
        return redirect(url_for("main.jobs"))

    status_filter = request.args.get("status")
    query = JobApplication.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    jobs_list = query.order_by(JobApplication.updated_at.desc()).all()
    return render_template("jobs.html", jobs=jobs_list, job_statuses=JOB_STATUSES, editing=job)


@main.route("/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
def job_delete(job_id):
    job = JobApplication.query.get_or_404(job_id)
    db.session.delete(job)
    db.session.commit()
    return redirect(url_for("main.jobs"))


@main.route("/calendar")
@login_required
def calendar_view():
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)

    # Build calendar grid
    first_weekday, num_days = cal_mod.monthrange(year, month)
    # Monday=0, we want Sunday=0 start
    first_weekday = (first_weekday + 1) % 7

    # Dates for the visible grid
    from datetime import timedelta
    start_date = date(year, month, 1) - timedelta(days=first_weekday)
    # 6 rows * 7 days
    grid_dates = [start_date + timedelta(days=i) for i in range(42)]

    # Fetch events for the visible range
    events = CalendarEvent.query.filter(
        CalendarEvent.date >= grid_dates[0],
        CalendarEvent.date <= grid_dates[-1],
    ).order_by(CalendarEvent.start_time, CalendarEvent.created_at).all()

    # Fetch tickets with due dates in range
    tickets = Ticket.query.filter(
        Ticket.due_date >= grid_dates[0],
        Ticket.due_date <= grid_dates[-1],
        Ticket.status.notin_([s.name for s in Status.query.filter_by(is_closed=True).all()]),
    ).order_by(Ticket.due_date).all()

    # Build lookup: date -> list of items
    date_items = {}
    for ev in events:
        date_items.setdefault(ev.date, []).append({
            "id": ev.id,
            "title": ev.title,
            "color": ev.color,
            "start_time": ev.start_time.strftime("%H:%M") if ev.start_time else None,
            "type": "event",
        })
    for t in tickets:
        date_items.setdefault(t.due_date, []).append({
            "id": t.id,
            "title": (t.emoji + " " if t.emoji else "") + t.title,
            "color": t.category.color if t.category else "#f59e0b",
            "start_time": None,
            "type": "ticket",
        })

    # Fetch active job applications with dates in range
    from sqlalchemy import or_
    job_apps = JobApplication.query.filter(
        JobApplication.status.notin_(["rejected", "withdrawn"]),
        or_(
            JobApplication.date_interview.between(grid_dates[0], grid_dates[-1]),
            JobApplication.date_followup.between(grid_dates[0], grid_dates[-1]),
        ),
    ).all()
    for j in job_apps:
        if j.date_interview and grid_dates[0] <= j.date_interview <= grid_dates[-1]:
            date_items.setdefault(j.date_interview, []).append({
                "id": j.id,
                "title": f"Interview: {j.company}",
                "color": "#f59e0b",
                "start_time": None,
                "type": "job",
            })
        if j.date_followup and grid_dates[0] <= j.date_followup <= grid_dates[-1]:
            date_items.setdefault(j.date_followup, []).append({
                "id": j.id,
                "title": f"Follow-up: {j.company}",
                "color": "#8b5cf6",
                "start_time": None,
                "type": "job",
            })

    # Prev/next month
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    month_name = cal_mod.month_name[month]

    return render_template(
        "calendar.html",
        grid_dates=grid_dates,
        date_items=date_items,
        year=year,
        month=month,
        month_name=month_name,
        today=today,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
    )


# --- API Routes (for AJAX / board drag-drop) ---


@api.route("/tickets/<int:ticket_id>/status", methods=["PATCH"])
@login_required
def update_status(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    data = request.get_json()
    new_status = data.get("status")
    valid = Status.query.filter_by(name=new_status).first()
    if valid:
        old_status = ticket.status
        if old_status != new_status:
            db.session.add(TicketHistory(
                ticket_id=ticket.id,
                field="status",
                old_value=old_status,
                new_value=new_status,
            ))
        ticket.status = new_status
        ticket.updated_at = datetime.now()
        db.session.commit()
        return jsonify(ticket.to_dict())
    return jsonify({"error": "Invalid status"}), 400


@api.route("/grocery/<int:item_id>/toggle", methods=["PATCH"])
@login_required
def grocery_toggle(item_id):
    item = GroceryItem.query.get_or_404(item_id)
    item.checked = not item.checked
    db.session.commit()
    return jsonify(item.to_dict())


@api.route("/calendar/events", methods=["POST"])
@login_required
def create_event():
    data = request.get_json()
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title required"}), 400
    ev = CalendarEvent(
        title=title,
        description=(data.get("description") or "").strip(),
        color=data.get("color", "#6366f1"),
        date=date.fromisoformat(data["date"]),
        all_day=data.get("all_day", True),
    )
    if not ev.all_day:
        st = data.get("start_time")
        et = data.get("end_time")
        if st:
            ev.start_time = time.fromisoformat(st)
        if et:
            ev.end_time = time.fromisoformat(et)
    db.session.add(ev)
    db.session.commit()
    return jsonify(ev.to_dict()), 201


@api.route("/calendar/events/<int:event_id>", methods=["DELETE"])
@login_required
def delete_event(event_id):
    ev = CalendarEvent.query.get_or_404(event_id)
    db.session.delete(ev)
    db.session.commit()
    return jsonify({"ok": True})


@api.route("/tickets", methods=["GET"])
@login_required
def list_tickets():
    tickets = Ticket.query.all()
    return jsonify([t.to_dict() for t in tickets])


# --- Helpers ---


def _save_ticket(ticket, form):
    is_new = ticket.id is None

    # Capture old values for history tracking (only for existing tickets)
    if not is_new:
        old = {
            "title": ticket.title or "",
            "description": ticket.description or "",
            "status": ticket.status or "",
            "priority": ticket.priority or "",
            "due_date": ticket.due_date.isoformat() if ticket.due_date else "",
            "category": ticket.category.name if ticket.category else "",
            "emoji": ticket.emoji or "",
            "tags": ", ".join(sorted(t.name for t in ticket.tags)),
        }

    ticket.emoji = form.get("emoji", "").strip()
    ticket.title = form.get("title", "").strip()
    ticket.description = form.get("description", "").strip()
    ticket.status = form.get("status", "new")
    ticket.priority = form.get("priority", "medium")

    due = form.get("due_date")
    ticket.due_date = date.fromisoformat(due) if due else None

    cat_id = form.get("category_id")
    ticket.category_id = int(cat_id) if cat_id else None

    tag_names = [t.strip() for t in form.get("tags", "").split(",") if t.strip()]
    tags = []
    for name in tag_names:
        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
            db.session.flush()
        tags.append(tag)
    ticket.tags = tags

    # Record history for changed fields
    if not is_new:
        new = {
            "title": ticket.title or "",
            "description": ticket.description or "",
            "status": ticket.status or "",
            "priority": ticket.priority or "",
            "due_date": ticket.due_date.isoformat() if ticket.due_date else "",
            "category": Category.query.get(ticket.category_id).name if ticket.category_id else "",
            "emoji": ticket.emoji or "",
            "tags": ", ".join(sorted(t.name for t in ticket.tags)),
        }
        for field in old:
            if old[field] != new[field]:
                db.session.add(TicketHistory(
                    ticket_id=ticket.id,
                    field=field,
                    old_value=old[field],
                    new_value=new[field],
                ))

    return ticket
