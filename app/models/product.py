# app/models/product.py
from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Category(BaseModel):
    __tablename__ = "categories"
    
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    
    # Self-referential relationship با استفاده از string
    parent = relationship("Category", remote_side="Category.id", back_populates="children")
    children = relationship("Category", back_populates="parent")
    
    products = relationship("Product", back_populates="category")

class Product(BaseModel):
    __tablename__ = "products"
    
    code = Column(String(50), unique=True, index=True, nullable=False)
    barcode = Column(String(100), unique=True, index=True, nullable=True)
    name = Column(String(200), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    
    unit = Column(String(20), nullable=False, default="عدد")
    
    cost_price = Column(Numeric(18, 2), default=0, nullable=False)
    retail_price = Column(Numeric(18, 2), default=0, nullable=False)
    wholesale_price = Column(Numeric(18, 2), default=0, nullable=False)
    min_wholesale_qty = Column(Integer, default=10, nullable=False)
    corporate_price = Column(Numeric(18, 2), default=0, nullable=False)
    
    stock_qty = Column(Numeric(18, 3), default=0, nullable=False)
    min_stock = Column(Numeric(18, 3), default=0, nullable=False)
    
    image_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    category = relationship("Category", back_populates="products")
    invoice_items = relationship("InvoiceItem", back_populates="product")