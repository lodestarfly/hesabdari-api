"""
Schemaهای مربوط به پرداخت
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PaymentBase(BaseModel):
    """پایه پرداخت"""
    amount: Decimal = Field(..., gt=0, description="مبلغ پرداخت باید مثبت باشد")
    payment_method: str = Field(..., max_length=50, description="روش پرداخت: cash, card, check, transfer")
    payment_type: str = Field(..., max_length=20, description="نوع: receipt (دریافت) یا payment (پرداخت)")
    reference_number: Optional[str] = Field(None, max_length=100, description="شماره مرجع / پیگیری")
    notes: Optional[str] = Field(None, description="توضیحات")


class PaymentCreate(PaymentBase):
    """Schema ایجاد پرداخت - شامل invoice_id"""
    invoice_id: int = Field(..., gt=0, description="شناسه فاکتور")


class PaymentUpdate(BaseModel):
    """Schema به‌روزرسانی پرداخت"""
    amount: Optional[Decimal] = Field(None, gt=0)
    payment_method: Optional[str] = Field(None, max_length=50)
    payment_type: Optional[str] = Field(None, max_length=20)
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class PaymentResponse(PaymentBase):
    """Schema پاسخ پرداخت"""
    id: int
    invoice_id: int
    invoice_number: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentListResponse(BaseModel):
    """لیست پرداخت‌ها"""
    total: int
    payments: list[PaymentResponse]
