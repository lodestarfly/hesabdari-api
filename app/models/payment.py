from app.core.database import Base
from sqlalchemy import (Column, DateTime, ForeignKey, Integer, Numeric, String,
                        Text)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    payment_method = Column(String(50), nullable=False)
    payment_type = Column(String(20), nullable=False)
    reference_number = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_deleted = Column(Integer, default=0)

    invoice = relationship("Invoice", back_populates="payments")
