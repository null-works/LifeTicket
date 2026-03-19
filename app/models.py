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


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emoji = db.Column(db.String(10), default="")
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="new")  # new, action_required, awaiting_reply, on_hold, done, cancelled
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
