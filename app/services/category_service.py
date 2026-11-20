# app/services/category_service.py
from typing import List, Optional

from app.models.product import Category
from app.schemas.product import CategoryCreate, CategoryUpdate
from app.services.audit_service import AuditService
from fastapi import HTTPException
from sqlalchemy.orm import Session


class CategoryService:

    @staticmethod
    def get_categories_tree(db: Session) -> List[dict]:
        """دریافت دسته‌بندی‌ها به صورت درختی"""
        # دریافت همه دسته‌بندی‌ها
        categories = db.query(Category).filter(Category.is_deleted == 0).all()

        # تبدیل به دیکشنری
        cat_dict = {}
        for cat in categories:
            cat_dict[cat.id] = {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "parent_id": cat.parent_id,
                "created_at": cat.created_at,
                "updated_at": cat.updated_at,
                "children": []
            }

        # ساخت درخت
        tree = []
        for cat_id, cat_data in cat_dict.items():
            if cat_data["parent_id"] and cat_data["parent_id"] in cat_dict:
                cat_dict[cat_data["parent_id"]]["children"].append(cat_data)
            else:
                tree.append(cat_data)

        return tree

    @staticmethod
    def create_category(
        db: Session,
        category_data: CategoryCreate,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> Category:
        """ایجاد دسته‌بندی جدید"""
        # بررسی وجود والد
        if category_data.parent_id:
            parent = db.query(Category).filter(
                Category.id == category_data.parent_id,
                Category.is_deleted == 0
            ).first()
            if not parent:
                raise HTTPException(status_code=404, detail="Parent category not found")

        # بررسی تکراری نبودن نام
        existing = db.query(Category).filter(
            Category.name == category_data.name,
            Category.is_deleted == 0
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Category name already exists")

        new_category = Category(
            name=category_data.name,
            description=category_data.description,
            parent_id=category_data.parent_id,
            created_by=user_id
        )

        db.add(new_category)
        db.commit()
        db.refresh(new_category)

        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="create",
            table_name="categories",
            record_id=new_category.id,
            new_values={
                "name": new_category.name,
                "parent_id": new_category.parent_id
            },
            ip_address=ip,
            user_agent=ua
        )

        return new_category

    @staticmethod
    def update_category(
        db: Session,
        category_id: int,
        category_data: CategoryUpdate,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> Category:
        """ویرایش دسته‌بندی"""
        category = db.query(Category).filter(
            Category.id == category_id,
            Category.is_deleted == 0
        ).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

        # جلوگیری از انتخاب خود به عنوان والد
        if category_data.parent_id == category_id:
            raise HTTPException(status_code=400, detail="Category cannot be its own parent")

        # ذخیره مقادیر قدیمی
        old_values = {
            "name": category.name,
            "description": category.description,
            "parent_id": category.parent_id
        }

        update_data = category_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(category, key, value)

        category.updated_by = user_id
        db.commit()
        db.refresh(category)

        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="update",
            table_name="categories",
            record_id=category_id,
            old_values=old_values,
            new_values={k: getattr(category, k) for k in update_data.keys()},
            ip_address=ip,
            user_agent=ua
        )

        return category

    @staticmethod
    def delete_category(
        db: Session,
        category_id: int,
        user_id: int,
        ip: str = None,
        ua: str = None
    ) -> dict:
        """حذف دسته‌بندی (Soft Delete)"""
        category = db.query(Category).filter(
            Category.id == category_id,
            Category.is_deleted == 0
        ).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

        # بررسی وجود زیرمجموعه
        children = db.query(Category).filter(
            Category.parent_id == category_id,
            Category.is_deleted == 0
        ).count()
        if children > 0:
            raise HTTPException(status_code=400, detail="دارای زیر مجموعه هست امکان حذف وجود ندارد")

        category.is_deleted = 1
        category.updated_by = user_id
        db.commit()

        # ثبت لاگ
        AuditService.log_action(
            db=db,
            user_id=user_id,
            action="delete",
            table_name="categories",
            record_id=category_id,
            old_values={"name": category.name},
            ip_address=ip,
            user_agent=ua
        )

        return {"message": "Category deleted successfully"}
