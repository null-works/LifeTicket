import os
from app import db
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


ticket_tags = db.Table(
    "ticket_tags",
    db.Column("ticket_id", db.Integer, db.ForeignKey("ticket.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    color = db.Column(db.String(7), default="#6366f1")  # hex color
    tickets = db.relationship("Ticket", backref="category", lazy=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "color": self.color}


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class GroceryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.String(50), default="")
    aisle = db.Column(db.String(100), default="")
    checked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "quantity": self.quantity,
            "aisle": self.aisle,
            "checked": self.checked,
        }


class CalendarEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    color = db.Column(db.String(7), default="#6366f1")
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    all_day = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "color": self.color,
            "date": self.date.isoformat(),
            "start_time": self.start_time.strftime("%H:%M") if self.start_time else None,
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else None,
            "all_day": self.all_day,
            "type": "event",
        }


class Status(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False, unique=True)  # internal key e.g. "action_required"
    label = db.Column(db.String(50), nullable=False)  # display label e.g. "Action Required"
    color = db.Column(db.String(7), default="#6366f1")  # hex color for board dot & badge
    is_closed = db.Column(db.Boolean, default=False)  # closed statuses (done, cancelled, etc.)
    position = db.Column(db.Integer, default=0)  # column ordering on board
    tickets = db.relationship(
        "Ticket", primaryjoin="Status.name == foreign(Ticket.status)",
        backref="status_obj", lazy=True,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "color": self.color,
            "is_closed": self.is_closed,
            "position": self.position,
        }


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emoji = db.Column(db.String(10), default="")
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(30), default="new")
    priority = db.Column(db.String(10), default="medium")  # low, medium, high, urgent
    due_date = db.Column(db.Date, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    tags = db.relationship("Tag", secondary=ticket_tags, backref="tickets", lazy=True)
    comments = db.relationship("TicketComment", backref="ticket", lazy=True, order_by="TicketComment.created_at.desc()", cascade="all, delete-orphan")
    attachments = db.relationship("TicketAttachment", backref="ticket", lazy=True, order_by="TicketAttachment.created_at.desc()", cascade="all, delete-orphan")
    history = db.relationship("TicketHistory", backref="ticket", lazy=True, order_by="TicketHistory.created_at.desc()", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "emoji": self.emoji or "",
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "category": self.category.to_dict() if self.category else None,
            "category_id": self.category_id,
            "tags": [t.to_dict() for t in self.tags],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class TicketComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("ticket.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class TicketAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("ticket.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    size = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def size_display(self):
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        return f"{self.size / (1024 * 1024):.1f} MB"

    @property
    def is_image(self):
        ext = os.path.splitext(self.original_name)[1].lower()
        return ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')


class TicketHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("ticket.id"), nullable=False)
    field = db.Column(db.String(50), nullable=False)
    old_value = db.Column(db.Text, default="")
    new_value = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class AppSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_prefix = db.Column(db.String(20), default="#")
    event_prefix = db.Column(db.String(20), default="EVT-")

    @staticmethod
    def get():
        """Return the singleton settings row, creating it if needed."""
        s = AppSettings.query.first()
        if not s:
            s = AppSettings()
            db.session.add(s)
            db.session.commit()
        return s


JOB_STATUSES = [
    ("bookmarked", "Bookmarked", "#6366f1"),
    ("applied", "Applied", "#3b82f6"),
    ("phone_screen", "Phone Screen", "#8b5cf6"),
    ("interview", "Interview", "#f59e0b"),
    ("offer", "Offer", "#22c55e"),
    ("rejected", "Rejected", "#ef4444"),
    ("withdrawn", "Withdrawn", "#6b7280"),
]

JOB_STATUS_MAP = {key: (label, color) for key, label, color in JOB_STATUSES}


class JobApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(200), nullable=False)
    position = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), default="")
    status = db.Column(db.String(30), default="bookmarked")
    salary = db.Column(db.String(100), default="")
    location = db.Column(db.String(200), default="")
    notes = db.Column(db.Text, default="")
    date_applied = db.Column(db.Date, nullable=True)
    date_interview = db.Column(db.Date, nullable=True)
    date_followup = db.Column(db.Date, nullable=True)
    resume_filename = db.Column(db.String(255), default="")
    resume_original_name = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def status_label(self):
        return JOB_STATUS_MAP.get(self.status, (self.status, "#6b7280"))[0]

    @property
    def status_color(self):
        return JOB_STATUS_MAP.get(self.status, (self.status, "#6b7280"))[1]

    @property
    def is_active(self):
        return self.status not in ("rejected", "withdrawn")


BILL_FREQUENCIES = [
    ("once", "One-time"),
    ("weekly", "Weekly"),
    ("biweekly", "Bi-weekly"),
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("yearly", "Yearly"),
]

BILL_FREQUENCY_MAP = {key: label for key, label in BILL_FREQUENCIES}


def _advance_date(d, frequency):
    """Compute the next due date from date d based on frequency."""
    from dateutil.relativedelta import relativedelta
    if frequency == "weekly":
        return d + relativedelta(weeks=1)
    elif frequency == "biweekly":
        return d + relativedelta(weeks=2)
    elif frequency == "monthly":
        return d + relativedelta(months=1)
    elif frequency == "quarterly":
        return d + relativedelta(months=3)
    elif frequency == "yearly":
        return d + relativedelta(years=1)
    return None  # one-time bills don't advance


class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    due_date = db.Column(db.Date, nullable=True)
    frequency = db.Column(db.String(20), default="monthly")
    category = db.Column(db.String(100), default="")
    paid = db.Column(db.Boolean, default=False)
    auto_pay = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    payments = db.relationship(
        "BillPayment", backref="bill", lazy=True,
        order_by="BillPayment.paid_date.desc()", cascade="all, delete-orphan",
    )

    @property
    def frequency_label(self):
        return BILL_FREQUENCY_MAP.get(self.frequency, self.frequency)

    @property
    def is_recurring(self):
        return self.frequency != "once"

    @property
    def is_overdue(self):
        from datetime import date as d
        return self.due_date and self.due_date < d.today() and not self.paid

    @property
    def next_due_date(self):
        """What the due date will be after paying the current cycle."""
        if not self.due_date or not self.is_recurring:
            return None
        return _advance_date(self.due_date, self.frequency)

    @property
    def days_until_due(self):
        from datetime import date as d
        if not self.due_date:
            return None
        return (self.due_date - d.today()).days

    @property
    def total_paid(self):
        return sum(p.amount for p in self.payments)

    @property
    def payment_count(self):
        return len(self.payments)

    def record_payment(self, amount=None, note=""):
        """Record a payment and advance the due date for recurring bills."""
        from datetime import date as d
        payment = BillPayment(
            bill_id=self.id,
            amount=amount if amount is not None else self.amount,
            paid_date=d.today(),
            due_date_snapshot=self.due_date,
            note=note,
        )
        db.session.add(payment)

        if self.is_recurring and self.due_date:
            self.due_date = _advance_date(self.due_date, self.frequency)
            self.paid = False  # reset for next cycle
        else:
            self.paid = True

        return payment

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "frequency": self.frequency,
            "category": self.category,
            "paid": self.paid,
            "auto_pay": self.auto_pay,
            "notes": self.notes,
            "is_recurring": self.is_recurring,
            "next_due_date": self.next_due_date.isoformat() if self.next_due_date else None,
            "payment_count": self.payment_count,
            "total_paid": self.total_paid,
        }


class BillPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey("bill.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_date = db.Column(db.Date, nullable=False)
    due_date_snapshot = db.Column(db.Date, nullable=True)  # what the due date was when paid
    note = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
