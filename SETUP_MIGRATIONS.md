# Setup & Migration Guide — OptiCredit Backend

## 🚀 Initial Setup

### 1. Install Dependencies
```bash
cd backend
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### 2. Environment Setup
```bash
cp .env.example .env
# Edit .env with your database credentials
```

### 3. Database Initialization

#### Option A: Using Alembic (Recommended)
```bash
# Generate migration from models
alembic revision --autogenerate -m "Initial schema with loans, payments, vouchers"

# Review the generated migration in app/db/migrations/versions/
# Then apply it:
alembic upgrade head
```

#### Option B: Direct SQLAlchemy (Development)
If Alembic is not yet set up, you can create all tables directly:
```python
# In a Python script or FastAPI startup:
from app.db.base import Base
from app.db.session import engine

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

### 4. Verify Setup
```bash
# Start the backend
uvicorn app.main:app --reload

# Check health endpoint
curl http://localhost:8000/api/v1/app-config

# Expected response:
# {"app_name": "OptiCredit", "version": "0.1.0", ...}
```

## 📊 Database Schema

All tables are created with relationships:

### Core Tables
- **lenders** — Financieras/prestamistas
- **users** — Empleados internos
- **customers** — Solicitantes de préstamos

### Loan Flow
- **loan_applications** — Solicitudes de préstamo
- **loans** — Préstamos aprobados
- **installments** — Cuotas (generadas automáticamente)
- **disbursements** — Desembolsos

### Payment Flow
- **payments** — Pagos enviados para revisión
- **vouchers** — Comprobantes bancarios
- **ocr_results** — Resultados de OCR
- **payment_matches** — Validación de coincidencias

### Support Tables
- **lender_bank_accounts** — Cuentas receptoras
- **customer_lender_links** — Vínculos cliente-financiera
- **lender_invitations** — Códigos de invitación
- **email_verification** — Tokens de verificación
- **password_reset** — Tokens de reset
- **otp** — Códigos OTP

## 🔄 Migration Workflow

### Adding New Models
1. Create model in `app/models/`
2. Import in `app/db/base.py`
3. Create schema in `app/schemas/`
4. Create repository in `app/repositories/`
5. Run: `alembic revision --autogenerate -m "description"`
6. Review generated migration
7. Run: `alembic upgrade head`

### Modifying Existing Tables
1. Modify model
2. Run: `alembic revision --autogenerate -m "description"`
3. Review & apply: `alembic upgrade head`

## 📝 Key Implementation Notes

### Timezone-Aware Datetimes
All datetime fields use `DateTime(timezone=True)` for proper timezone handling:
```python
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    nullable=False,
)
```

### UUID Primary Keys
All tables use PostgreSQL UUID with `uuid.uuid4()` defaults:
```python
id: Mapped[uuid.UUID] = mapped_column(
    PG_UUID(as_uuid=True),
    primary_key=True,
    default=uuid.uuid4,
)
```

### Foreign Key Constraints
Relationships use CASCADE/SET NULL/RESTRICT appropriately:
- `CASCADE` — Delete dependents (comments with post)
- `SET NULL` — Allow orphaning (soft delete)
- `RESTRICT` — Prevent deletion if children exist (audit logs)

## 🐛 Troubleshooting

### "Target database is not up to date"
```bash
alembic upgrade head
```

### "No such table: xyz"
- Check migration was applied: `alembic history`
- Check connection string in `.env`

### "Foreign key constraint failed"
- Ensure parent records exist before creating children
- Check CASCADE/SET NULL settings

### Alembic not found
```bash
uv pip install alembic
```

## 📞 Support

For issues with migrations or schema:
1. Check `app/db/migrations/versions/` for auto-generated scripts
2. Review model definitions in `app/models/`
3. Verify relationships in `app/db/base.py`
