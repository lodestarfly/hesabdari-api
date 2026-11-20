import os
from pathlib import Path

# وارد کردن روترها
from app.api.v1 import (accounts, audit_logs, auth, categories, customers,
                        invoices, payments, products, reports, suppliers,
                        users)
from app.core.config import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Professional Accounting System API",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# سرو کردن فایل‌های آپلود شده - باید قبل از routerها تعریف شود
# ============================================================
UPLOADS_DIR = Path(settings.UPLOAD_DIR).resolve()
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
for _sub in ("products", "invoices", "users"):
    (UPLOADS_DIR / _sub).mkdir(parents=True, exist_ok=True)

# mount روی دو مسیر تا هر فرمت آدرس کار کند
# ✅ مهم: این mountها باید قبل از include_router باشند
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/api/v1/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads_api")

print(f"[BOOT] Uploads directory: {UPLOADS_DIR}")
print(f"[BOOT] Files in products: {list((UPLOADS_DIR / 'products').iterdir()) if (UPLOADS_DIR / 'products').exists() else '[]'}")


# ============================================================
# Endpoints عمومی
# ============================================================
@app.get("/")
def root():
    return {
        "message": "Accounting System API is running",
        "version": settings.APP_VERSION
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# ============================================================
# ثبت روترهای نسخه 1
# ============================================================
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(audit_logs.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(customers.router, prefix="/api/v1")
app.include_router(suppliers.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(accounts.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
