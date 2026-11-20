# app/services/customer_service.py
from typing import Optional, List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from decimal import Decimal

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.utils.encryption import encryption_service
from app.services.audit_service import AuditService


class CustomerService:
    
    @staticmethod
    def get_customers(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        customer_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        has_balance: Optional[bool] = None
    ) -> dict:
        """دریافت لیست مشتریان با فیلتر و جستجو"""
        query = db.query(Customer).filter(Customer.is_deleted == 0)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Customer.name.ilike(search_pattern),
                    Customer.national_code.ilike(search_pattern),
                    Customer.phone.ilike(search_pattern),
                    Customer.mobile.ilike(search_pattern)
                )
            )
        
        if customer_type:
            query = query.filter(Customer.customer_type == customer_type)
        
        if is_active is not None:
            query = query.filter(Customer.is_active == is_active)
        
        if has_balance is not None:
            if has_balance:
                query = query.filter(Customer.balance != 0)
            else:
                query = query.filter(Customer.balance == 0)
        
        total = query.count()
        customers = query.order_by(Customer.created_at.desc()).offset(skip).limit(limit).all()
        
        # رمزگشایی اطلاعات بانکی برای نمایش
        result = []
        for customer in customers:
            customer_dict = {
                "id": customer.id,
                "customer_type": customer.customer_type,
                "name": customer.name,
                "national_code": customer.national_code,
                "economic_code": customer.economic_code,
                "registration_no": customer.registration_no,
                "phone": customer.phone,
                "mobile": customer.mobile,
                "email": customer.email,
                "address": customer.address,
                "postal_code": customer.postal_code,
                "credit_limit": customer.credit_limit,
                "payment_terms": customer.payment_terms,
                "balance": customer.balance,
                "bank_card_number": encryption_service.decrypt(customer.bank_card_number) if customer.bank_card_number else None,
                "bank_account": encryption_service.decrypt(customer.bank_account) if customer.bank_account else None,
                "iban": encryption_service.decrypt(customer.iban) if customer.iban else None,
                "notes": customer.notes,
                "is_active": customer.is_active,
                "created_at": customer.created_at,
                "updated_at": customer.updated_at
            }
            result.append(customer_dict)
        
        return {"total": total, "customers": result}
    
    @staticmethod
    def get_customer_by_id(db: Session, customer_id: int) -> dict:
        """دریافت مشتری بر اساس ID"""
        customer = db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.is_deleted == 0
        ).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # رمزگشایی اطلاعات بانکی
        return {
            "id": customer.id,
            "customer_type": customer.customer_type,
            "name": customer.name,
            "national_code": customer.national_code,
            "economic_code": customer.economic_code,
            "registration_no": customer.registration_no,
            "phone": customer.phone,
            "mobile": customer.mobile,
            "email": customer.email,
            "address": customer.address,
            "postal_code": customer.postal_code,
            "credit_limit": customer.credit_limit,
            "payment_terms": customer.payment_terms,
            "balance": customer.balance,
            "bank_card_number": encryption_service.decrypt(customer.bank_card_number) if customer.bank_card_number else None,
            "bank_account": encryption_service.decrypt(customer.bank_account) if customer.bank_account else None,
            "iban": encryption_service.decrypt(customer.iban) if customer.iban else None,
            "notes": customer.notes,
            "is_active": customer.is_active,
            "created_at": customer.created_at,
            "updated_at": customer.updated_at
        }
    
    @staticmethod
    def create_customer(
        db: Session,
        customer_data: CustomerCreate,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> dict:
        """ایجاد مشتری جدید"""
        # بررسی تکراری نبودن کد ملی
        if customer_data.national_code:
            existing = db.query(Customer).filter(
                Customer.national_code == customer_data.national_code,
                Customer.is_deleted == 0
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="National code already exists")
        
        # رمزنگاری اطلاعات بانکی
        encrypted_card = encryption_service.encrypt(customer_data.bank_card_number) if customer_data.bank_card_number else None
        encrypted_account = encryption_service.encrypt(customer_data.bank_account) if customer_data.bank_account else None
        encrypted_iban = encryption_service.encrypt(customer_data.iban) if customer_data.iban else None
        
        new_customer = Customer(
            customer_type=customer_data.customer_type,
            name=customer_data.name,
            national_code=customer_data.national_code,
            economic_code=customer_data.economic_code,
            registration_no=customer_data.registration_no,
            phone=customer_data.phone,
            mobile=customer_data.mobile,
            email=customer_data.email,
            address=customer_data.address,
            postal_code=customer_data.postal_code,
            credit_limit=customer_data.credit_limit,
            payment_terms=customer_data.payment_terms,
            balance=0,
            bank_card_number=encrypted_card,
            bank_account=encrypted_account,
            iban=encrypted_iban,
            notes=customer_data.notes,
            is_active=customer_data.is_active,
            created_by=user_id
        )
        
        db.add(new_customer)
        db.commit()
        db.refresh(new_customer)
        
        # ثبت لاگ (بدون اطلاعات حساس)
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="create",
            table_name="customers",
            record_id=new_customer.id,
            new_values={
                "name": new_customer.name,
                "customer_type": new_customer.customer_type,
                "national_code": new_customer.national_code
            },
            ip_address=ip,
            user_agent=ua
        )
        
        return CustomerService.get_customer_by_id(db, new_customer.id)
    
    @staticmethod
    def update_customer(
        db: Session,
        customer_id: int,
        customer_data: CustomerUpdate,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> dict:
        """ویرایش مشتری"""
        customer = db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.is_deleted == 0
        ).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # بررسی کد ملی جدید
        if customer_data.national_code and customer_data.national_code != customer.national_code:
            existing = db.query(Customer).filter(
                Customer.national_code == customer_data.national_code,
                Customer.is_deleted == 0,
                Customer.id != customer_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="National code already exists")
        
        # ذخیره مقادیر قدیمی (بدون اطلاعات حساس)
        old_values = {
            "name": customer.name,
            "customer_type": customer.customer_type,
            "balance": float(customer.balance)
        }
        
        update_data = customer_data.model_dump(exclude_unset=True)
        
        # رمزنگاری اطلاعات بانکی جدید
        if "bank_card_number" in update_data:
            update_data["bank_card_number"] = encryption_service.encrypt(update_data["bank_card_number"]) if update_data["bank_card_number"] else None
        if "bank_account" in update_data:
            update_data["bank_account"] = encryption_service.encrypt(update_data["bank_account"]) if update_data["bank_account"] else None
        if "iban" in update_data:
            update_data["iban"] = encryption_service.encrypt(update_data["iban"]) if update_data["iban"] else None
        
        for key, value in update_data.items():
            setattr(customer, key, value)
        
        customer.updated_by = user_id
        db.commit()
        db.refresh(customer)
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="update",
            table_name="customers",
            record_id=customer_id,
            old_values=old_values,
            new_values={k: float(v) if isinstance(v, Decimal) else v for k, v in update_data.items() if k not in ["bank_card_number", "bank_account", "iban"]},
            ip_address=ip,
            user_agent=ua
        )
        
        return CustomerService.get_customer_by_id(db, customer_id)
    
    @staticmethod
    def delete_customer(
        db: Session,
        customer_id: int,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> dict:
        """حذف مشتری (Soft Delete)"""
        customer = db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.is_deleted == 0
        ).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # بررسی وجود فاکتور
        invoices_count = db.query(Invoice).filter(
            Invoice.customer_id == customer_id,
            Invoice.is_deleted == 0
        ).count()
        if invoices_count > 0:
            raise HTTPException(status_code=400, detail="Cannot delete customer with existing invoices")
        
        customer.is_deleted = 1
        customer.is_active = False
        customer.updated_by = user_id
        db.commit()
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="delete",
            table_name="customers",
            record_id=customer_id,
            old_values={"name": customer.name},
            ip_address=ip,
            user_agent=ua
        )
        
        return {"message": "Customer deleted successfully"}