# app/models/invoice.py
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import BaseModel

class Invoice(BaseModel):
    __tablename__ = "invoices"
    
    invoice_number = Column(String(50), unique=True, index=True, nullable=False)
    serial_number = Column(String(50), nullable=True)
    
    invoice_type = Column(String(20), nullable=False)
    status = Column(String(20), default='draft', nullable=False)
    
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    issue_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    
    subtotal = Column(Numeric(18, 2), default=0, nullable=False)
    discount_amount = Column(Numeric(18, 2), default=0, nullable=False)
    discount_percent = Column(Numeric(5, 2), default=0, nullable=False)
    tax_amount = Column(Numeric(18, 2), default=0, nullable=False)
    tax_percent = Column(Numeric(5, 2), default=9, nullable=False)
    total_amount = Column(Numeric(18, 2), default=0, nullable=False)
    
    paid_amount = Column(Numeric(18, 2), default=0, nullable=False)
    remaining_amount = Column(Numeric(18, 2), default=0, nullable=False)
    
    is_official = Column(Integer, default=0, nullable=False)
    
    locked_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    
    notes = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    # Relationships - فقط به customer و items (نه به User برای جلوگیری از پیچیدگی)
    customer = relationship("Customer", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

class InvoiceItem(BaseModel):
    __tablename__ = "invoice_items"
    
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    description = Column(String(500), nullable=True)
    quantity = Column(Numeric(18, 3), nullable=False)
    unit_price = Column(Numeric(18, 2), nullable=False)
    
    discount_amount = Column(Numeric(18, 2), default=0, nullable=False)
    discount_percent = Column(Numeric(5, 2), default=0, nullable=False)
    
    total_price = Column(Numeric(18, 2), nullable=False)
    row_number = Column(Integer, nullable=False)
    
    invoice = relationship("Invoice", back_populates="items")
    product = relationship("Product", back_populates="invoice_items")