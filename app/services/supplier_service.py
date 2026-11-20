# app/services/supplier_service.py
from typing import Optional, List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from decimal import Decimal

from app.models.customer import Supplier
from app.models.invoice import Invoice
from app.schemas.customer import SupplierCreate, SupplierUpdate
from app.utils.encryption import encryption_service
from app.services.audit_service import AuditService


class SupplierService:
    
    @staticmethod
    def get_suppliers(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        has_balance: Optional[bool] = None
    ) -> dict:
        """دریافت لیست تامین‌کنندگان با فیلتر و جستجو"""
        query = db.query(Supplier).filter(Supplier.is_deleted == 0)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Supplier.name.ilike(search_pattern),
                    Supplier.national_code.ilike(search_pattern),
                    Supplier.phone.ilike(search_pattern),
                    Supplier.mobile.ilike(search_pattern)
                )
            )
        
        if is_active is not None:
            query = query.filter(Supplier.is_active == is_active)
        
        if has_balance is not None:
            if has_balance:
                query = query.filter(Supplier.balance != 0)
            else:
                query = query.filter(Supplier.balance == 0)
        
        total = query.count()
        suppliers = query.order_by(Supplier.created_at.desc()).offset(skip).limit(limit).all()
        
        # رمزگشایی اطلاعات بانکی
        result = []
        for supplier in suppliers:
            supplier_dict = {
                "id": supplier.id,
                "name": supplier.name,
                "national_code": supplier.national_code,
                "phone": supplier.phone,
                "mobile": supplier.mobile,
                "email": supplier.email,
                "address": supplier.address,
                "contact_person": supplier.contact_person,
                "balance": supplier.balance,
                "bank_card_number": encryption_service.decrypt(supplier.bank_card_number) if supplier.bank_card_number else None,
                "bank_account": encryption_service.decrypt(supplier.bank_account) if supplier.bank_account else None,
                "iban": encryption_service.decrypt(supplier.iban) if supplier.iban else None,
                "notes": supplier.notes,
                "is_active": supplier.is_active,
                "created_at": supplier.created_at,
                "updated_at": supplier.updated_at
            }
            result.append(supplier_dict)
        
        return {"total": total, "suppliers": result}
    
    @staticmethod
    def get_supplier_by_id(db: Session, supplier_id: int) -> dict:
        """دریافت تامین‌کننده بر اساس ID"""
        supplier = db.query(Supplier).filter(
            Supplier.id == supplier_id,
            Supplier.is_deleted == 0
        ).first()
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")
        
        return {
            "id": supplier.id,
            "name": supplier.name,
            "national_code": supplier.national_code,
            "phone": supplier.phone,
            "mobile": supplier.mobile,
            "email": supplier.email,
            "address": supplier.address,
            "contact_person": supplier.contact_person,
            "balance": supplier.balance,
            "bank_card_number": encryption_service.decrypt(supplier.bank_card_number) if supplier.bank_card_number else None,
            "bank_account": encryption_service.decrypt(supplier.bank_account) if supplier.bank_account else None,
            "iban": encryption_service.decrypt(supplier.iban) if supplier.iban else None,
            "notes": supplier.notes,
            "is_active": supplier.is_active,
            "created_at": supplier.created_at,
            "updated_at": supplier.updated_at
        }
    
    @staticmethod
    def create_supplier(
        db: Session,
        supplier_data: SupplierCreate,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> dict:
        """ایجاد تامین‌کننده جدید"""
        # رمزنگاری اطلاعات بانکی
        encrypted_card = encryption_service.encrypt(supplier_data.bank_card_number) if supplier_data.bank_card_number else None
        encrypted_account = encryption_service.encrypt(supplier_data.bank_account) if supplier_data.bank_account else None
        encrypted_iban = encryption_service.encrypt(supplier_data.iban) if supplier_data.iban else None
        
        new_supplier = Supplier(
            name=supplier_data.name,
            national_code=supplier_data.national_code,
            phone=supplier_data.phone,
            mobile=supplier_data.mobile,
            email=supplier_data.email,
            address=supplier_data.address,
            contact_person=supplier_data.contact_person,
            balance=0,
            bank_card_number=encrypted_card,
            bank_account=encrypted_account,
            iban=encrypted_iban,
            notes=supplier_data.notes,
            is_active=supplier_data.is_active,
            created_by=user_id
        )
        
        db.add(new_supplier)
        db.commit()
        db.refresh(new_supplier)
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="create",
            table_name="suppliers",
            record_id=new_supplier.id,
            new_values={
                "name": new_supplier.name,
                "national_code": new_supplier.national_code
            },
            ip_address=ip,
            user_agent=ua
        )
        
        return SupplierService.get_supplier_by_id(db, new_supplier.id)
    
    @staticmethod
    def update_supplier(
        db: Session,
        supplier_id: int,
        supplier_data: SupplierUpdate,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> dict:
        """ویرایش تامین‌کننده"""
        supplier = db.query(Supplier).filter(
            Supplier.id == supplier_id,
            Supplier.is_deleted == 0
        ).first()
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")
        
        # ذخیره مقادیر قدیمی
        old_values = {
            "name": supplier.name,
            "balance": float(supplier.balance)
        }
        
        update_data = supplier_data.model_dump(exclude_unset=True)
        
        # رمزنگاری اطلاعات بانکی جدید
        if "bank_card_number" in update_data:
            update_data["bank_card_number"] = encryption_service.encrypt(update_data["bank_card_number"]) if update_data["bank_card_number"] else None
        if "bank_account" in update_data:
            update_data["bank_account"] = encryption_service.encrypt(update_data["bank_account"]) if update_data["bank_account"] else None
        if "iban" in update_data:
            update_data["iban"] = encryption_service.encrypt(update_data["iban"]) if update_data["iban"] else None
        
        for key, value in update_data.items():
            setattr(supplier, key, value)
        
        supplier.updated_by = user_id
        db.commit()
        db.refresh(supplier)
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="update",
            table_name="suppliers",
            record_id=supplier_id,
            old_values=old_values,
            new_values={k: float(v) if isinstance(v, Decimal) else v for k, v in update_data.items() if k not in ["bank_card_number", "bank_account", "iban"]},
            ip_address=ip,
            user_agent=ua
        )
        
        return SupplierService.get_supplier_by_id(db, supplier_id)
    
    @staticmethod
    def delete_supplier(
        db: Session,
        supplier_id: int,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> dict:
        """حذف تامین‌کننده (Soft Delete)"""
        supplier = db.query(Supplier).filter(
            Supplier.id == supplier_id,
            Supplier.is_deleted == 0
        ).first()
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")
        
        # بررسی وجود فاکتور خرید
        invoices_count = db.query(Invoice).filter(
            Invoice.supplier_id == supplier_id,
            Invoice.is_deleted == 0
        ).count()
        if invoices_count > 0:
            raise HTTPException(status_code=400, detail="Cannot delete supplier with existing invoices")
        
        supplier.is_deleted = 1
        supplier.is_active = False
        supplier.updated_by = user_id
        db.commit()
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="delete",
            table_name="suppliers",
            record_id=supplier_id,
            old_values={"name": supplier.name},
            ip_address=ip,
            user_agent=ua
        )
        
        return {"message": "Supplier deleted successfully"}