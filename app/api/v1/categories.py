from app.core.database import get_db
from app.core.security import get_current_active_superuser, get_current_user
from app.models.product import Category  # ✅ اصلاح شد
from app.models.user import User
from app.schemas.product import (CategoryCreate, CategoryResponse,
                                 CategoryUpdate)
from app.services.category_service import CategoryService
from app.utils.request_utils import get_client_ip, get_user_agent
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/tree")
def get_categories_tree(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت دسته‌بندی‌ها به صورت درختی"""
    return CategoryService.get_categories_tree(db)


@router.get("/")
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """دریافت لیست دسته‌بندی‌ها"""
    return CategoryService.get_categories_tree(db)


@router.post("/", response_model=CategoryResponse, status_code=201)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ایجاد دسته‌بندی جدید"""
    # بررسی وجود والد
    if data.parent_id is not None:
        parent = db.query(Category).filter(
            Category.id == data.parent_id,
            Category.is_deleted == 0
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="دسته‌بندی والد یافت نشد")

    category = Category(
        name=data.name,
        description=data.description,
        parent_id=data.parent_id,
        created_by=current_user.id
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """ویرایش دسته‌بندی (فقط ادمین)"""
    existing = db.query(Category).filter(
        Category.id == category_id,
        Category.is_deleted == 0
    ).first()
    if not existing:
        raise HTTPException(status_code=404, detail="دسته‌بندی یافت نشد")

    # بررسی حلقه
    if category_data.parent_id is not None and category_data.parent_id != existing.parent_id:
        def get_descendant_ids(cat_id: int, ids: list = None) -> list:
            if ids is None:
                ids = []
            ids.append(cat_id)
            children = db.query(Category).filter(
                Category.parent_id == cat_id,
                Category.is_deleted == 0
            ).all()
            for child in children:
                get_descendant_ids(child.id, ids)
            return ids

        descendant_ids = get_descendant_ids(category_id)
        if category_data.parent_id in descendant_ids:
            raise HTTPException(
                status_code=400,
                detail="نمی‌توان والد را به خودش یا فرزندانش تغییر داد"
            )

        parent = db.query(Category).filter(
            Category.id == category_data.parent_id,
            Category.is_deleted == 0
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="دسته‌بندی والد یافت نشد")

    if category_data.name is not None:
        existing.name = category_data.name
    if category_data.description is not None:
        existing.description = category_data.description
    if category_data.parent_id is not None:
        existing.parent_id = category_data.parent_id

    existing.updated_by = current_user.id

    db.commit()
    db.refresh(existing)

    return existing


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
    request: Request = None
):
    """حذف دسته‌بندی (فقط ادمین)"""
    return CategoryService.delete_category(
        db=db,
        category_id=category_id,
        user_id=current_user.id,
        ip=get_client_ip(request) if request else None,
        ua=get_user_agent(request) if request else None
    )
