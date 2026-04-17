# 🚀 Quick Start — Kashap Backend

## ✅ Flujo definitivo (Windows + uv + logs + OCR obligatorio)

Desde `backend/`:

```powershell
.\scripts\dev.ps1
```

Este comando único:
- valida puerto `8000`,
- corre `uv sync --dev`,
- valida OCR obligatorio (`paddle`, `paddleocr`, `chardet`),
- levanta FastAPI con `--access-log --log-level debug`.

Si falla OCR, el backend no arranca (comportamiento esperado).

---

## ⚡ Opción A: Docker (Recomendado — 1 comando)

```bash
cd ..
docker-compose up
```

**Esto crea:**
- ✅ PostgreSQL 16 (`localhost:5432`)
- ✅ Backend FastAPI (`localhost:8000`)
- ✅ Base de datos `prestamos_db`
- ✅ Tablas automáticas (via SQLAlchemy)

**Luego en otro terminal:**
```bash
# Ver logs del backend
docker-compose logs -f backend

# Acceder a la API
curl http://localhost:8000/api/v1/app-config
```

---

## 🖥️ Opción B: Local (Sin Docker)

### Requisitos
- Python 3.11+
- PostgreSQL 16 corriendo (local o docker)
- uv (gestor paquetes)

### Pasos

**1. Instalar dependencias**
```bash
cd backend
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

**2. Crear/Asegurar PostgreSQL**
```bash
# Opción A: Con Docker (sin instalar PostgreSQL)
docker run -d \
  --name postgres-kashap \
  -e POSTGRES_USER=prestamos_user \
  -e POSTGRES_PASSWORD=prestamos_pass \
  -e POSTGRES_DB=prestamos_db \
  -p 5432:5432 \
  postgres:16-alpine

# Opción B: PostgreSQL ya instalado
createdb -U postgres prestamos_db
```

**3. Crear tablas**
```bash
python run_migrations.py
# Output: "✅ Database tables created successfully!"
```

**4. Correr backend**
```bash
uvicorn app.main:app --reload --port 8000
```

**Output esperado:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

**5. Probar la API**
```bash
# En otra terminal
curl http://localhost:8000/api/v1/app-config

# Esperado:
# {"app_name":"Kashap","version":"0.1.0",...}
```

---

## 🧪 Opción C: Tests (Sin correr servidor)

```bash
cd backend
uv pip install -r requirements-dev.txt
pytest tests/ -v
pytest --cov=app tests/  # Con coverage
```

---

## 📡 API Endpoints Principales

### Auth
```bash
POST   /api/v1/auth/login
POST   /api/v1/auth/register
POST   /api/v1/auth/refresh-token
GET    /api/v1/auth/me
```

### Loan Applications
```bash
POST   /api/v1/loan-applications/
GET    /api/v1/loan-applications/
GET    /api/v1/loan-applications/{id}
POST   /api/v1/loan-applications/{id}/approve
POST   /api/v1/loan-applications/{id}/reject
```

### Loans
```bash
POST   /api/v1/loans/
GET    /api/v1/loans/{id}
POST   /api/v1/loans/{id}/disburse
```

### Payments
```bash
POST   /api/v1/payments/submit
POST   /api/v1/payments/{id}/approve
POST   /api/v1/payments/{id}/vouchers/upload
GET    /api/v1/payments/{id}
```

---

## 🔧 Troubleshooting

### Error: "DATABASE_URL invalid"
✅ **Fix:** Asegurate que `.env` existe en `backend/`
```bash
cp backend/.env.example backend/.env
```

### Error: "relation 'loans' does not exist"
✅ **Fix:** Correr migraciones
```bash
python backend/run_migrations.py
```

### Error: "Connection refused" (PostgreSQL)
✅ **Fix:** Verificar PostgreSQL está corriendo
```bash
# Docker
docker ps | grep postgres

# Local
psql -U postgres -d prestamos_db
```

### Port 8000 ya está en uso
✅ **Fix:** Cambiar puerto
```bash
uvicorn app.main:app --port 8001
```

### "ModuleNotFoundError: No module named 'app'"
✅ **Fix:** Asegurate de estar en `backend/` directory
```bash
cd backend
uvicorn app.main:app --reload
```

---

## 📚 Documentación

- `SETUP_MIGRATIONS.md` — Detalles de Alembic
- `TESTING_GUIDE.md` — Guía de tests
- `TASK_LIST.md` — Estado de todas las tareas
- `docs/` — Documentación general del proyecto

---

## ✨ Características Disponibles

✅ **Auth completo** — Login, register, JWT, roles, OTP
✅ **Loan lifecycle** — Applications → Approval → Disbursement
✅ **Payments** — Submit, review, approve workflow
✅ **Vouchers + OCR** — Upload async processing
✅ **Storage** — Local + Cloudflare R2 (switchable)
✅ **Braintree** — Subscriptions + webhooks
✅ **Multi-tenant** — Lender-based isolation
✅ **Tests** — Unit tests for services

---

## 🎯 Próximo Paso

- [ ] Correr `docker-compose up`
- [ ] Acceder a `http://localhost:8000/docs` (Swagger)
- [ ] Probar endpoints con Swagger UI
- [ ] Conectar con Flutter frontend

¡Listo! 🚀
