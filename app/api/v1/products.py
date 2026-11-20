import os
import uuid
from decimal import Decimal
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.invoice import Invoice, InvoiceItem
from app.models.product import Product
from app.models.user import User
from app.schemas.product import (ProductCreate, ProductListResponse,
                                 ProductResponse, ProductUpdate)
from app.utils.request_utils import get_client_ip, get_user_agent
from fastapi import (APIRouter, Depends, File, Form, HTTPException, Query,
                     Request, UploadFile)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/", response_model=ProductListResponse)
def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=1),
    category_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    low_stock: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت لیست محصولات با فیلتر و جستجو"""
    query = db.query(Product).filter(Product.is_deleted == 0)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Product.name.ilike(search_pattern)) |
            (Product.code.ilike(search_pattern)) |
            (Product.barcode.ilike(search_pattern))
        )

    if category_id is not None:
        query = query.filter(Product.category_id == category_id)

    if is_active is not None:
        query = query.filter(Product.is_active == is_active)

    if low_stock:
        query = query.filter(Product.stock_qty <= Product.min_stock)

    total = query.count()
    products = query.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "products": products
    }


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت جزئیات یک محصول"""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.is_deleted == 0
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="محصول یافت نشد")

    return product


@router.post("/", status_code=201)
def create_product(
    code: str = Form(...),
    name: str = Form(...),
    unit: str = Form("عدد"),
    barcode: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    cost_price: float = Form(0),
    retail_price: float = Form(0),
    wholesale_price: float = Form(0),
    min_wholesale_qty: int = Form(10),
    corporate_price: float = Form(0),
    stock_qty: float = Form(0),
    min_stock: float = Form(0),
    description: Optional[str] = Form(None),
    is_active: bool = Form(True),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ایجاد محصول جدید"""
    from app.core.config import settings

    # بررسی یکتا بودن کد محصول
    existing_code = db.query(Product).filter(
        Product.code == code
    ).first()

    if existing_code:
        if existing_code.is_deleted == 1:
            existing_code.code = f"{code}_del_{existing_code.id}"
            db.commit()
        else:
            raise HTTPException(
                status_code=400,
                detail=f"کد محصول '{code}' قبلاً برای محصول دیگری استفاده شده است"
            )

    # بررسی یکتا بودن بارکد
    if barcode:
        existing_barcode = db.query(Product).filter(
            Product.barcode == barcode
        ).first()

        if existing_barcode:
            if existing_barcode.is_deleted == 1:
                existing_barcode.barcode = f"{barcode}_del_{existing_barcode.id}"
                db.commit()
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"بارکد '{barcode}' قبلاً برای محصول دیگری استفاده شده است"
                )

    product = Product(
        code=code,
        name=name,
        unit=unit,
        barcode=barcode,
        category_id=category_id,
        cost_price=Decimal(str(cost_price)),
        retail_price=Decimal(str(retail_price)),
        wholesale_price=Decimal(str(wholesale_price)),
        min_wholesale_qty=min_wholesale_qty,
        corporate_price=Decimal(str(corporate_price)),
        stock_qty=Decimal(str(stock_qty)),
        min_stock=Decimal(str(min_stock)),
        description=description,
        is_active=is_active,
        created_by=current_user.id
    )

    # آپلود تصویر
    if image and image.filename:
        ext = os.path.splitext(image.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        upload_dir = os.path.join(settings.UPLOAD_DIR, "products")
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            f.write(image.file.read())

        product.image_url = f"products/{filename}"

    db.add(product)
    db.commit()
    db.refresh(product)

    return {
        "id": product.id,
        "code": product.code,
        "barcode": product.barcode,
        "name": product.name,
        "category_id": product.category_id,
        "unit": product.unit,
        "cost_price": float(product.cost_price),
        "retail_price": float(product.retail_price),
        "wholesale_price": float(product.wholesale_price),
        "min_wholesale_qty": product.min_wholesale_qty,
        "corporate_price": float(product.corporate_price),
        "stock_qty": float(product.stock_qty),
        "min_stock": float(product.min_stock),
        "image_url": product.image_url,
        "description": product.description,
        "is_active": product.is_active,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }


@router.put("/{product_id}")
def update_product(
    product_id: int,
    code: str = Form(...),
    name: str = Form(...),
    unit: str = Form("عدد"),
    barcode: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    cost_price: float = Form(0),
    retail_price: float = Form(0),
    wholesale_price: float = Form(0),
    min_wholesale_qty: int = Form(10),
    corporate_price: float = Form(0),
    stock_qty: float = Form(0),
    min_stock: float = Form(0),
    description: Optional[str] = Form(None),
    is_active: bool = Form(True),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """به‌روزرسانی محصول"""
    from app.core.config import settings

    existing = db.query(Product).filter(
        Product.id == product_id,
        Product.is_deleted == 0
    ).first()

    if not existing:
        raise HTTPException(status_code=404, detail="محصول یافت نشد")

    # بررسی یکتا بودن کد
    if code != existing.code:
        duplicate = db.query(Product).filter(
            Product.code == code,
            Product.id != product_id,
            Product.is_deleted == 0
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=400,
                detail=f"کد محصول '{code}' قبلاً برای محصول دیگری استفاده شده است"
            )

    existing.code = code
    existing.name = name
    existing.unit = unit
    existing.barcode = barcode
    existing.category_id = category_id
    existing.cost_price = Decimal(str(cost_price))
    existing.retail_price = Decimal(str(retail_price))
    existing.wholesale_price = Decimal(str(wholesale_price))
    existing.min_wholesale_qty = min_wholesale_qty
    existing.corporate_price = Decimal(str(corporate_price))
    existing.stock_qty = Decimal(str(stock_qty))
    existing.min_stock = Decimal(str(min_stock))
    existing.description = description
    existing.is_active = is_active
    existing.updated_by = current_user.id

    # آپلود تصویر جدید
    if image and image.filename:
        ext = os.path.splitext(image.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        upload_dir = os.path.join(settings.UPLOAD_DIR, "products")
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            f.write(image.file.read())

        existing.image_url = f"products/{filename}"

    db.commit()
    db.refresh(existing)

    return {
        "id": existing.id,
        "code": existing.code,
        "barcode": existing.barcode,
        "name": existing.name,
        "category_id": existing.category_id,
        "unit": existing.unit,
        "cost_price": float(existing.cost_price),
        "retail_price": float(existing.retail_price),
        "wholesale_price": float(existing.wholesale_price),
        "min_wholesale_qty": existing.min_wholesale_qty,
        "corporate_price": float(existing.corporate_price),
        "stock_qty": float(existing.stock_qty),
        "min_stock": float(existing.min_stock),
        "image_url": existing.image_url,
        "description": existing.description,
        "is_active": existing.is_active,
        "created_at": existing.created_at.isoformat() if existing.created_at else None,
        "updated_at": existing.updated_at.isoformat() if existing.updated_at else None,
    }


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """حذف محصول (Soft Delete) - فقط اگر در فاکتوری استفاده نشده باشد"""
    from app.models.invoice import InvoiceItem  # ✅ import مستقیم

    product = db.query(Product).filter(
        Product.id == product_id,
        Product.is_deleted == 0
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="محصول یافت نشد")

    # ✅ بررسی استفاده در فاکتورها
    used_in_invoice = db.query(InvoiceItem).filter(
        InvoiceItem.product_id == product_id,
        InvoiceItem.is_deleted == 0
    ).first()

    if used_in_invoice:
        raise HTTPException(
            status_code=400,
            detail=f"محصول '{product.name}' در یک یا چند فاکتور استفاده شده و قابل حذف نیست"
        )

    product.is_deleted = 1
    product.updated_by = current_user.id
    db.commit()

    return None
