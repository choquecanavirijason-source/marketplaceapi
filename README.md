# Marketplace Microservice 🏪

Backend FastAPI para marketplace Elashes — gestión de productos, categorías y pedidos.

## 🚀 Deploy en VM Ubuntu (Google Cloud)

Este servicio corre en el puerto 8001 y debe desplegarse en /opt/elashes/marketplaceapi con un unit de systemd llamado marketplace.service.

### Archivo de servicio
- [deploy/gcp/marketplace-api.service](deploy/gcp/marketplace-api.service)

### Comandos recomendados
```bash
sudo cp /opt/elashes/marketplaceapi/deploy/gcp/marketplace-api.service /etc/systemd/system/marketplace.service
sudo systemctl daemon-reload
sudo systemctl enable marketplace
sudo systemctl restart marketplace
```

### Variable de entorno recomendada para la VM
```env
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080,http://34.55.150.142,https://34.55.150.142
```

## 🚀 Quick Start con Docker

### Requisitos
- Docker
- Docker Compose

### 1️⃣ Configurar variables de entorno
```bash
copy .env.example .env
# Edita .env si es necesario
```

### 2️⃣ Ejecutar con Docker Compose
```bash
# Construcción e inicio de servicios
docker-compose up -d

# Ver logs
docker-compose logs -f marketplace-api

# Detener servicios
docker-compose down
```

### 3️⃣ Acceder a la API
- **API**: http://localhost:8001
- **Documentación Swagger**: http://localhost:8001/docs
- **Documentación ReDoc**: http://localhost:8001/redoc

---

## 🏗️ Arquitectura

```
app/
├── config/          # Configuración (settings)
├── core/            # Utilidades comunes (dependencias, media)
├── domain/          # Entidades del negocio
├── infrastructure/  # Base de datos y migraciones
└── presentation/    # Controladores (routers)
```

---

## 🗄️ Base de Datos

PostgreSQL 16 con migraciones automáticas al iniciar.

**PostgreSQL en Docker Compose**:
- Imagen: `postgres:16-alpine`
- Host dentro de Compose: `postgres`
- Usuario: `marketplace`
- Contraseña: `marketplace`
- Database: `marketplace`
- URL usada por el backend: `postgresql+psycopg://marketplace:marketplace@postgres:5432/marketplace`

---

## 📦 Dependencias Principales

- **FastAPI** 0.104.1 — Framework web
- **SQLAlchemy** 2.0.45 — ORM
- **Pydantic** 2.5.0 — Validación de datos
- **Uvicorn** 0.24.0 — Servidor ASGI

---

## 🛠️ Comandos útiles

```bash
# Ver estado de contenedores
docker-compose ps

# Ejecutar comandos dentro del contenedor
docker-compose exec marketplace-api bash

# Rebuild de la imagen
docker-compose up -d --build

# Limpiar todo
docker-compose down -v
```

---

## 📝 Variables de Entorno

Ver [.env.example](.env.example) para todas las opciones disponibles.

**Avisos de citas** (`/api/v1/avisos/*`, y `device_token` en login, registro y `POST /api/v1/auth/device`):
- `INTERNAL_API_KEY`: secreto compartido con elashesbackend; debe tener **el mismo valor** que su `INTERNAL_API_KEY`. Vacío = no se registran dispositivos ni se vinculan cuentas.
- En elashesbackend además debe estar `CLIENT_NOTICES_ENABLED=true`; si no, sus rutas de avisos no existen.

**Vínculo con la ficha del salón** (`mp_customers.salon_client_id`): en login, registro, reserva y `POST /api/v1/auth/device`, si la cuenta no lo tiene se consulta `POST /clients/link-marketplace` del salón (por email, luego teléfono; el email todavía no se verifica) y se guarda solo si hay una única coincidencia. Si no hay ninguna, se guarda el `client_id` de la ficha que crea el salón en la primera reserva. Con varias fichas para el mismo email (`ambiguous`) la cuenta queda sin vincular hasta que un admin lo resuelva.

---

## 👨‍💻 Desarrollo local (sin Docker)

```bash
# Crear venv
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
uvicorn main:app --reload --port 8001
```

**Tests** (SQLite en memoria y salón simulado; no tocan PostgreSQL ni elashesbackend):

```bash
pip install -r requirements-dev.txt
pytest tests
```

---

## 📧 Contacto

Elashes Marketplace Backend
