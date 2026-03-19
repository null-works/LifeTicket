from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required
from app import db
from app.models import Ticket, Category, Tag
from datetime import date, datetime

main = Blueprint("main", __name__)
api = Blueprint("api", __name__)


# --- Page Routes ---


@main.route("/")
@login_required
def dashboard():
    tickets = Ticket.query.all()
    categories = Category.query.order_by(Category.name).all()
    today = date.today()

    stats = {
        "total": len(tickets),
        "todo": sum(1 for t in tickets if t.status == "todo"),
        "in_progress": sum(1 for t in tickets if t.status == "in_progress"),
        "done": sum(1 for t in tickets if t.status == "done"),
        "overdue": sum(
            1
            for t in tickets
            if t.due_date and t.due_date < today and t.status != "done"
        ),
        "urgent": sum(1 for t in tickets if t.priority == "urgent" and t.status != "done"),
    }
    return render_template(
        "dashboard.html", stats=stats, categories=categories, tickets=tickets
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
    columns = {
        "todo": [t for t in tickets if t.status == "todo"],
        "in_progress": [t for t in tickets if t.status == "in_progress"],
        "done": [t for t in tickets if t.status == "done"],
    }
    return render_template(
        "board.html",
        columns=columns,
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

    query = Ticket.query
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if category_id:
        query = query.filter_by(category_id=category_id)

    sort_col = getattr(Ticket, sort, Ticket.created_at)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    tickets = query.all()
    categories = Category.query.order_by(Category.name).all()
    return render_template("list.html", tickets=tickets, categories=categories)


@main.route("/ticket/new", methods=["GET", "POST"])
@login_required
def ticket_new():
    if request.method == "POST":
        ticket = _save_ticket(Ticket(), request.form)
        db.session.add(ticket)
        db.session.commit()
        return redirect(url_for("main.board"))

    categories = Category.query.order_by(Category.name).all()
    tags = Tag.query.order_by(Tag.name).all()
    return render_template("ticket_form.html", ticket=None, categories=categories, tags=tags)


@main.route("/ticket/<int:ticket_id>/edit", methods=["GET", "POST"])
@login_required
def ticket_edit(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if request.method == "POST":
        _save_ticket(ticket, request.form)
        db.session.commit()
        return redirect(url_for("main.board"))

    categories = Category.query.order_by(Category.name).all()
    tags = Tag.query.order_by(Tag.name).all()
    return render_template("ticket_form.html", ticket=ticket, categories=categories, tags=tags)


@main.route("/ticket/<int:ticket_id>/delete", methods=["POST"])
@login_required
def ticket_delete(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    db.session.delete(ticket)
    db.session.commit()
    return redirect(url_for("main.board"))


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


# --- API Routes (for AJAX / board drag-drop) ---


@api.route("/tickets/<int:ticket_id>/status", methods=["PATCH"])
@login_required
def update_status(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    data = request.get_json()
    new_status = data.get("status")
    if new_status in ("todo", "in_progress", "done"):
        ticket.status = new_status
        ticket.updated_at = datetime.now()
        db.session.commit()
        return jsonify(ticket.to_dict())
    return jsonify({"error": "Invalid status"}), 400


@api.route("/tickets", methods=["GET"])
@login_required
def list_tickets():
    tickets = Ticket.query.all()
    return jsonify([t.to_dict() for t in tickets])


# --- Helpers ---


def _save_ticket(ticket, form):
    ticket.title = form.get("title", "").strip()
    ticket.description = form.get("description", "").strip()
    ticket.status = form.get("status", "todo")
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

    return ticket
