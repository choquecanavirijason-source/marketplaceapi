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
cp .env.example .env
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

MySQL 8.0 con migraciones automáticas al iniciar.

**Credenciales por defecto** (modificar en .env):
- Usuario: `root`
- Contraseña: `password`
- Database: `marketplace`

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

---

## 📧 Contacto

Elashes Marketplace Backend
