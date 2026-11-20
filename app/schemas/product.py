# app/schemas/product.py
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ==================== دسته‌بندی ====================

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    parent_id: Optional[int] = None

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    parent_id: Optional[int] = None  # ✅ باید Optional باشد

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    parent_id: Optional[int] = None

class CategoryResponse(CategoryBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    children: List['CategoryResponse'] = []

    model_config = ConfigDict(from_attributes=True)

class CategoryListResponse(BaseModel):
    total: int
    categories: List[CategoryResponse]

# ==================== محصول ====================

class ProductBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    barcode: Optional[str] = Field(None, max_length=100)
    name: str = Field(..., min_length=2, max_length=200)
    category_id: Optional[int] = None
    unit: str = Field(default="عدد", max_length=20)

    # قیمت‌ها
    cost_price: Decimal = Field(default=0, ge=0)
    retail_price: Decimal = Field(default=0, ge=0)
    wholesale_price: Decimal = Field(default=0, ge=0)
    min_wholesale_qty: int = Field(default=10, ge=1)
    corporate_price: Decimal = Field(default=0, ge=0)

    # موجودی
    stock_qty: Decimal = Field(default=0, ge=0)
    min_stock: Decimal = Field(default=0, ge=0)

    description: Optional[str] = None
    is_active: bool = True

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    barcode: Optional[str] = Field(None, max_length=100)
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    category_id: Optional[int] = None
    unit: Optional[str] = Field(None, max_length=20)

    cost_price: Optional[Decimal] = Field(None, ge=0)
    retail_price: Optional[Decimal] = Field(None, ge=0)
    wholesale_price: Optional[Decimal] = Field(None, ge=0)
    min_wholesale_qty: Optional[int] = Field(None, ge=1)
    corporate_price: Optional[Decimal] = Field(None, ge=0)

    stock_qty: Optional[Decimal] = Field(None, ge=0)
    min_stock: Optional[Decimal] = Field(None, ge=0)

    description: Optional[str] = None
    is_active: Optional[bool] = None

class ProductResponse(ProductBase):
    id: int
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    category: Optional[CategoryResponse] = None

    model_config = ConfigDict(from_attributes=True)

class ProductListResponse(BaseModel):
    total: int
    products: List[ProductResponse]

# برای آپلود تصویر
class ProductImageResponse(BaseModel):
    image_url: str
