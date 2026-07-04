import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config.settings import settings

# ── Migrations ────────────────────────────────────────────────
import app.infrastructure.database.migrations.create_categories_table   as m1
import app.infrastructure.database.migrations.create_products_table     as m2
import app.infrastructure.database.migrations.create_orders_tables      as m3
import app.infrastructure.database.migrations.create_collections_table  as m4
import app.infrastructure.database.migrations.add_product_fields        as m5
import app.infrastructure.database.migrations.add_order_address_fields  as m6
import app.infrastructure.database.migrations.create_mp_customers       as m7
import app.infrastructure.database.migrations.add_source_to_mp_customers as m8

# ── Controllers ───────────────────────────────────────────────
from app.presentation.controllers.categories_controller  import router as categories_router
from app.presentation.controllers.products_controller    import router as products_router
from app.presentation.controllers.orders_controller      import router as orders_router
from app.presentation.controllers.collections_controller import router as collections_router
from app.presentation.controllers.customers_controller   import router as customers_router
from app.presentation.controllers.auth_controller        import router as auth_router
from app.presentation.controllers.booking_controller     import router as booking_router
from app.infrastructure.database.seeders import run_seeders

# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Marketplace Backend",
    description="API para el marketplace de Elashes — productos, categorías y pedidos.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS
origins = [o.strip() for o in settings.allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Run migrations on startup ─────────────────────────────────
MIGRATIONS = [
    ("mp_categories",           m1.upgrade),
    ("mp_products",             m2.upgrade),
    ("mp_orders+items",         m3.upgrade),
    ("mp_collections+junction", m4.upgrade),
    ("mp_products:new_fields",  m5.upgrade),
    ("mp_orders:address_fields", m6.upgrade),
    ("mp_customers",            m7.upgrade),
    ("mp_customers:source",     m8.upgrade),
]

for name, fn in MIGRATIONS:
    try:
        fn()
    except Exception as exc:
        print(f"[migration:{name}] ERROR — {exc}")

run_seeders()

# ── Static media ──────────────────────────────────────────────
os.makedirs(settings.media_base_path, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_base_path), name="media")

# ── Routers ───────────────────────────────────────────────────
PREFIX = "/api"
app.include_router(auth_router)          # monta en /api/v1/auth (prefijo propio)
app.include_router(booking_router)       # monta en /api/v1/booking (prefijo propio)
app.include_router(categories_router,  prefix=PREFIX)
app.include_router(products_router,    prefix=PREFIX)
app.include_router(orders_router,      prefix=PREFIX)
app.include_router(collections_router, prefix=PREFIX)
app.include_router(customers_router,   prefix=PREFIX)


@app.get("/")
def root():
    return RedirectResponse(url="/docs")
