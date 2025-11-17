# models/user_password_history.py
from extensions.database import db
from .mixins import TimestampMixin, COMMON_TABLE_ARGS

class UserPasswordHistory(TimestampMixin, db.Model):
    __tablename__ = "user_password_history"
    __table_args__ = (COMMON_TABLE_ARGS,)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
