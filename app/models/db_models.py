from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text

from app.db import Base


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True)
    commodity = Column(String(80), nullable=False)
    market = Column(String(120), nullable=False)
    language = Column(String(8), nullable=False)
    quantity_qtl = Column(Float, nullable=False)
    duration_ms = Column(Float, nullable=False)
    status = Column(String(32), default="success")
    warning = Column(Text)
    response = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
