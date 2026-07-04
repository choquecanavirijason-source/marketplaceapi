from app.infrastructure.database.session import SessionLocal
from app.domain.entities.category import Category
from app.domain.entities.product import Product

_CATEGORIES = [
    {"name": "Pestañas",        "description": "Extensiones, volúmenes y tratamientos de pestañas"},
    {"name": "Maquillaje",      "description": "Bases, labiales, sombras y productos profesionales"},
    {"name": "Cuidado de Piel", "description": "Serums, cremas y tratamientos faciales"},
    {"name": "Herramientas",    "description": "Pinzas, anillos de gel y accesorios profesionales"},
]

_PRODUCTS = [
    # ── Pestañas ──────────────────────────────────────────────────────────────
    {
        "name": "Pegamento Premium Ultra Hold",
        "brand": "ElashPro",
        "description": "Adhesivo de larga duración para extensiones. Resistente al agua y al calor. 24-48 h de retención.",
        "price": 15.99, "original_price": 21.00,
        "category": "Pestañas", "stock": 45, "rating": 4.9, "review_count": 218,
    },
    {
        "name": "Extensiones Silk Lash Curl C",
        "brand": "LuxLash",
        "description": "Pestañas de seda sintética, curvatura C, grosor 0.07 mm. Efecto natural.",
        "price": 8.50, "original_price": None,
        "category": "Pestañas", "stock": 80, "rating": 4.8, "review_count": 135,
    },
    {
        "name": "Removedor de Pestañas sin Dolor",
        "brand": "ElashPro",
        "description": "Gel removedor de adhesivo de bajo olor. Suave con piel y párpados delicados.",
        "price": 7.99, "original_price": 10.50,
        "category": "Pestañas", "stock": 60, "rating": 4.7, "review_count": 98,
    },
    {
        "name": "Parches Hidrogel para Ojos",
        "brand": "CoolPads",
        "description": "Parches de hidrogel que protegen los párpados inferiores durante el procedimiento.",
        "price": 5.50, "original_price": None,
        "category": "Pestañas", "stock": 120, "rating": 4.6, "review_count": 74,
    },
    # ── Maquillaje ────────────────────────────────────────────────────────────
    {
        "name": "Delineador Líquido Negro Intenso",
        "brand": "GlowUp",
        "description": "Delineador de punta fina, fórmula long-lasting 12 h. Seca rápido, no corre.",
        "price": 9.99, "original_price": 13.00,
        "category": "Maquillaje", "stock": 35, "rating": 4.8, "review_count": 190,
    },
    {
        "name": "Labial Mate Terciopelo Nude",
        "brand": "VelvetLips",
        "description": "Acabado mate sin resecar. Tono nude rosado ideal para pieles morenas y claras.",
        "price": 11.00, "original_price": None,
        "category": "Maquillaje", "stock": 28, "rating": 4.5, "review_count": 62,
    },
    {
        "name": "Base Líquida SPF 30 Tono 02",
        "brand": "GlowUp",
        "description": "Cobertura media-alta, acabado satinado natural. Con protección solar SPF 30.",
        "price": 18.99, "original_price": 24.00,
        "category": "Maquillaje", "stock": 20, "rating": 4.7, "review_count": 145,
    },
    # ── Cuidado de Piel ───────────────────────────────────────────────────────
    {
        "name": "Sérum Vitamina C 20%",
        "brand": "SkinGlow",
        "description": "Sérum iluminador con vitamina C estabilizada. Reduce manchas y unifica el tono.",
        "price": 22.50, "original_price": 29.00,
        "category": "Cuidado de Piel", "stock": 15, "rating": 4.9, "review_count": 301,
    },
    {
        "name": "Crema Contorno de Ojos Antiedad",
        "brand": "SkinGlow",
        "description": "Reduce ojeras y líneas finas. Con retinol y ácido hialurónico. Uso nocturno.",
        "price": 17.00, "original_price": None,
        "category": "Cuidado de Piel", "stock": 22, "rating": 4.6, "review_count": 88,
    },
    {
        "name": "Mascarilla de Arcilla Purificante",
        "brand": "PureClay",
        "description": "Arcilla caolín + carbón activado. Limpia profundo sin irritar. 2-3 usos por semana.",
        "price": 12.00, "original_price": 15.00,
        "category": "Cuidado de Piel", "stock": 40, "rating": 4.5, "review_count": 55,
    },
    # ── Herramientas ──────────────────────────────────────────────────────────
    {
        "name": "Pinzas Curvas Profesionales Acero",
        "brand": "PrecisionTool",
        "description": "Pinzas de acero inoxidable quirúrgico, curvatura 45°. Para aplicación de extensiones.",
        "price": 13.50, "original_price": 18.00,
        "category": "Herramientas", "stock": 30, "rating": 4.8, "review_count": 112,
    },
    {
        "name": "Anillo Dosificador de Pegamento",
        "brand": "ElashPro",
        "description": "Anillo de silicona con copa para mantener el adhesivo cerca. Reutilizable.",
        "price": 3.50, "original_price": None,
        "category": "Herramientas", "stock": 100, "rating": 4.7, "review_count": 78,
    },
]


def run_seeders():
    db = SessionLocal()
    try:
        # Solo ejecutar si no hay productos aún
        if db.query(Product).count() > 0:
            return

        cat_map: dict[str, int] = {}
        for c in _CATEGORIES:
            existing = db.query(Category).filter(Category.name == c["name"]).first()
            if not existing:
                obj = Category(name=c["name"], description=c.get("description"), is_active=True)
                db.add(obj)
                db.flush()
                cat_map[c["name"]] = obj.id
            else:
                cat_map[c["name"]] = existing.id

        for p in _PRODUCTS:
            cat_id = cat_map.get(p["category"])
            obj = Product(
                name=p["name"],
                brand=p.get("brand"),
                description=p.get("description"),
                price=p["price"],
                original_price=p.get("original_price"),
                category_id=cat_id,
                stock=p["stock"],
                rating=p.get("rating", 0.0),
                review_count=p.get("review_count", 0),
                is_active=True,
            )
            db.add(obj)

        db.commit()
        print(f"[seeders] {len(_PRODUCTS)} productos y {len(_CATEGORIES)} categorías insertados.")
    except Exception as e:
        db.rollback()
        print(f"[seeders] Error: {e}")
    finally:
        db.close()
