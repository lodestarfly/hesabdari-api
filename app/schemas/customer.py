# app/schemas/customer.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

# ==================== مشتری ====================

class CustomerBase(BaseModel):
    customer_type: str = Field(default="real", pattern="^(real|legal)$")
    name: str = Field(..., min_length=2, max_length=200)
    national_code: Optional[str] = Field(None, max_length=20)
    economic_code: Optional[str] = Field(None, max_length=20)
    registration_no: Optional[str] = Field(None, max_length=50)
    
    phone: Optional[str] = Field(None, max_length=20)
    mobile: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    
    address: Optional[str] = None
    postal_code: Optional[str] = Field(None, max_length=20)
    
    credit_limit: Decimal = Field(default=0, ge=0)
    payment_terms: int = Field(default=0, ge=0)
    
    # اطلاعات بانکی - بدون محدودیت سخت‌گیرانه
    bank_card_number: Optional[str] = None
    bank_account: Optional[str] = None
    iban: Optional[str] = None
    
    notes: Optional[str] = None
    is_active: bool = True

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    national_code: Optional[str] = Field(None, max_length=20)
    economic_code: Optional[str] = Field(None, max_length=20)
    registration_no: Optional[str] = Field(None, max_length=50)
    
    phone: Optional[str] = Field(None, max_length=20)
    mobile: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    
    address: Optional[str] = None
    postal_code: Optional[str] = Field(None, max_length=20)
    
    credit_limit: Optional[Decimal] = Field(None, ge=0)
    payment_terms: Optional[int] = Field(None, ge=0)
    
    bank_card_number: Optional[str] = Field(None, max_length=19)
    bank_account: Optional[str] = Field(None, max_length=50)
    iban: Optional[str] = Field(None, max_length=26)
    
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class CustomerResponse(BaseModel):
    id: int
    customer_type: str
    name: str
    national_code: Optional[str] = None
    economic_code: Optional[str] = None
    registration_no: Optional[str] = None
    
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    
    address: Optional[str] = None
    postal_code: Optional[str] = None
    
    credit_limit: Decimal
    payment_terms: int
    balance: Decimal  # مانده حساب
    
    # اطلاعات بانکی (رمزگشایی شده برای نمایش)
    bank_card_number: Optional[str] = None
    bank_account: Optional[str] = None
    iban: Optional[str] = None
    
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class CustomerListResponse(BaseModel):
    total: int
    customers: List[CustomerResponse]

# ==================== تامین‌کننده ====================

class SupplierBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    national_code: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=20)
    mobile: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = None
    contact_person: Optional[str] = Field(None, max_length=100)
    
    # اطلاعات بانکی - بدون محدودیت سخت‌گیرانه
    bank_card_number: Optional[str] = None
    bank_account: Optional[str] = None
    iban: Optional[str] = None
    
    notes: Optional[str] = None
    is_active: bool = True

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    national_code: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=20)
    mobile: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = None
    contact_person: Optional[str] = Field(None, max_length=100)
    
    bank_card_number: Optional[str] = None
    bank_account: Optional[str] = None
    iban: Optional[str] = None
    
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class SupplierResponse(BaseModel):
    id: int
    name: str
    national_code: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    
    balance: Decimal  # مانده حساب
    
    # اطلاعات بانکی (رمزگشایی شده)
    bank_card_number: Optional[str] = None
    bank_account: Optional[str] = None
    iban: Optional[str] = None
    
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class SupplierListResponse(BaseModel):
    total: int
    suppliers: List[SupplierResponse]