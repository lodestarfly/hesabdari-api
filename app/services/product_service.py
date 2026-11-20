# app/services/product_service.py
from typing import Optional, List
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import or_
import os
import uuid
from pathlib import Path

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.core.config import settings
from app.services.audit_service import AuditService


class ProductService:
    
    @staticmethod
    def get_products(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        low_stock: Optional[bool] = None
    ) -> dict:
        """دریافت لیست محصولات با فیلتر و جستجو"""
        query = db.query(Product).filter(Product.is_deleted == 0)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Product.name.ilike(search_pattern),
                    Product.code.ilike(search_pattern),
                    Product.barcode.ilike(search_pattern)
                )
            )
        
        if category_id:
            query = query.filter(Product.category_id == category_id)
        
        if is_active is not None:
            query = query.filter(Product.is_active == is_active)
        
        if low_stock:
            query = query.filter(Product.stock_qty <= Product.min_stock)
        
        total = query.count()
        products = query.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()
        
        return {"total": total, "products": products}
    
    @staticmethod
    def get_product_by_id(db: Session, product_id: int) -> Product:
        """دریافت محصول بر اساس ID"""
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.is_deleted == 0
        ).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    
    @staticmethod
    def create_product(
        db: Session,
        product_data: ProductCreate,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> Product:
        """ایجاد محصول جدید"""
        # بررسی تکراری نبودن کد
        existing = db.query(Product).filter(
            Product.code == product_data.code,
            Product.is_deleted == 0
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Product code already exists")
        
        # بررسی بارکد
        if product_data.barcode:
            existing_barcode = db.query(Product).filter(
                Product.barcode == product_data.barcode,
                Product.is_deleted == 0
            ).first()
            if existing_barcode:
                raise HTTPException(status_code=400, detail="Barcode already exists")
        
        new_product = Product(
            code=product_data.code,
            barcode=product_data.barcode,
            name=product_data.name,
            category_id=product_data.category_id,
            unit=product_data.unit,
            cost_price=product_data.cost_price,
            retail_price=product_data.retail_price,
            wholesale_price=product_data.wholesale_price,
            min_wholesale_qty=product_data.min_wholesale_qty,
            corporate_price=product_data.corporate_price,
            stock_qty=product_data.stock_qty,
            min_stock=product_data.min_stock,
            description=product_data.description,
            is_active=product_data.is_active,
            created_by=user_id
        )
        
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="create",
            table_name="products",
            record_id=new_product.id,
            new_values={
                "code": new_product.code,
                "name": new_product.name,
                "stock_qty": float(new_product.stock_qty)
            },
            ip_address=ip,
            user_agent=ua
        )
        
        return new_product
    
    @staticmethod
    def update_product(
        db: Session,
        product_id: int,
        product_data: ProductUpdate,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> Product:
        """ویرایش محصول"""
        product = ProductService.get_product_by_id(db, product_id)
        
        # بررسی بارکد جدید
        if product_data.barcode and product_data.barcode != product.barcode:
            existing = db.query(Product).filter(
                Product.barcode == product_data.barcode,
                Product.is_deleted == 0,
                Product.id != product_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Barcode already exists")
        
        # ذخیره مقادیر قدیمی
        old_values = {
            "name": product.name,
            "stock_qty": float(product.stock_qty),
            "retail_price": float(product.retail_price)
        }
        
        update_data = product_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)
        
        product.updated_by = user_id
        db.commit()
        db.refresh(product)
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="update",
            table_name="products",
            record_id=product_id,
            old_values=old_values,
            new_values={k: float(getattr(product, k)) if hasattr(getattr(product, k), 'real') else getattr(product, k) for k in update_data.keys()},
            ip_address=ip,
            user_agent=ua
        )
        
        return product
    
    @staticmethod
    def delete_product(
        db: Session,
        product_id: int,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> dict:
        """حذف محصول (Soft Delete)"""
        product = ProductService.get_product_by_id(db, product_id)
        
        product.is_deleted = 1
        product.is_active = False
        product.updated_by = user_id
        db.commit()
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="delete",
            table_name="products",
            record_id=product_id,
            old_values={"code": product.code, "name": product.name},
            ip_address=ip,
            user_agent=ua
        )
        
        return {"message": "Product deleted successfully"}
    
    @staticmethod
    def upload_product_image(
        db: Session,
        product_id: int,
        image: UploadFile,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> dict:
        """آپلود تصویر محصول"""
        product = ProductService.get_product_by_id(db, product_id)
        
        # بررسی نوع فایل
        allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
        if image.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Invalid image type")
        
        # بررسی حجم فایل
        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        contents = image.file.read()
        if len(contents) > max_size:
            raise HTTPException(status_code=400, detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB")
        
        # ساخت مسیر ذخیره‌سازی
        upload_dir = Path(settings.UPLOAD_DIR) / "products"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # نام فایل یکتا
        file_extension = image.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = upload_dir / unique_filename
        
        # ذخیره فایل
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # حذف تصویر قبلی
        if product.image_url:
            old_image_path = Path(settings.UPLOAD_DIR) / product.image_url
            if old_image_path.exists():
                old_image_path.unlink()
        
        # به‌روزرسانی مسیر تصویر
        product.image_url = f"products/{unique_filename}"
        product.updated_by = user_id
        db.commit()
        
        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="update",
            table_name="products",
            record_id=product_id,
            old_values={"image_url": product.image_url},
            new_values={"image_url": product.image_url},
            ip_address=ip,
            user_agent=ua
        )
        
        return {"image_url": product.image_url}