# app/models/customer.py
from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Customer(BaseModel):
    __tablename__ = "customers"
    
    customer_type = Column(String(10), nullable=False, default='real')
    
    name = Column(String(200), nullable=False)
    national_code = Column(String(20), nullable=True)
    economic_code = Column(String(20), nullable=True)
    registration_no = Column(String(50), nullable=True)
    
    phone = Column(String(20), nullable=True)
    mobile = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    
    address = Column(Text, nullable=True)
    postal_code = Column(String(20), nullable=True)
    
    credit_limit = Column(Numeric(18, 2), default=0, nullable=False)
    payment_terms = Column(Integer, default=0, nullable=False)
    balance = Column(Numeric(18, 2), default=0, nullable=False)
    
    # اطلاعات بانکی (رمزنگاری شده)
    bank_card_number = Column(String(500), nullable=True)
    bank_account = Column(String(500), nullable=True)
    iban = Column(String(500), nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    
    invoices = relationship("Invoice", back_populates="customer")

class Supplier(BaseModel):
    __tablename__ = "suppliers"
    
    name = Column(String(200), nullable=False)
    national_code = Column(String(20), nullable=True)
    phone = Column(String(20), nullable=True)
    mobile = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    contact_person = Column(String(100), nullable=True)
    balance = Column(Numeric(18, 2), default=0, nullable=False)
    
    # اطلاعات بانکی (رمزنگاری شده) - این بخش اضافه شد
    bank_card_number = Column(String(500), nullable=True)
    bank_account = Column(String(500), nullable=True)
    iban = Column(String(500), nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)