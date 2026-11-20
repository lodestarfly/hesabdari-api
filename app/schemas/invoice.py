# app/schemas/invoice.py
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from app.schemas.payment import PaymentResponse
from pydantic import BaseModel, ConfigDict, Field

# ==================== آیتم فاکتور ====================

class InvoiceItemBase(BaseModel):
    product_id: int
    description: Optional[str] = Field(None, max_length=500)
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    discount_amount: Decimal = Field(default=0, ge=0)
    discount_percent: Decimal = Field(default=0, ge=0, le=100)
    row_number: int

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceItemResponse(InvoiceItemBase):
    id: int
    total_price: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ==================== فاکتور ====================

class InvoiceBase(BaseModel):
    invoice_type: str = Field(..., pattern="^(sale|purchase|proforma)$")
    customer_id: Optional[int] = None
    supplier_id: Optional[int] = None
    due_date: Optional[datetime] = None
    discount_amount: Decimal = Field(default=0, ge=0)
    discount_percent: Decimal = Field(default=0, ge=0, le=100)
    tax_percent: Decimal = Field(default=9, ge=0, le=100)
    is_official: bool = False
    notes: Optional[str] = None

class InvoiceCreate(InvoiceBase):
    items: List[InvoiceItemCreate] = Field(..., min_length=1)

class InvoiceUpdate(BaseModel):
    customer_id: Optional[int] = None
    supplier_id: Optional[int] = None
    due_date: Optional[datetime] = None
    discount_amount: Optional[Decimal] = Field(None, ge=0)
    discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    tax_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    notes: Optional[str] = None
    items: Optional[List[InvoiceItemCreate]] = None

class InvoiceResponse(InvoiceBase):
    id: int
    invoice_number: str
    serial_number: Optional[str] = None
    status: str
    user_id: int
    issue_date: datetime

    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal

    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None

    items: List[InvoiceItemResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class InvoiceListResponse(BaseModel):
    total: int
    invoices: List[InvoiceResponse]

# ==================== پرداخت ====================

class PaymentCreate(BaseModel):
    invoice_id: Optional[int] = Field(None, gt=0, description="شناسه فاکتور (اختیاری - از URL هم می‌آید)")
    amount: Decimal = Field(..., gt=0)
    payment_method: str = Field(..., pattern="^(cash|card|check|transfer)$")
    reference_number: Optional[str] = Field(None, max_length=100)
    payment_type: str = Field(..., pattern="^(receipt|payment)$")
    notes: Optional[str] = None

class PaymentResponse(BaseModel):
    id: int
    invoice_id: int
    invoice_number: Optional[str] = None
    amount: Decimal
    payment_method: str
    payment_type: str
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
