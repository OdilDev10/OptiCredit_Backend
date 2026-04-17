# Kashap Backend

## Desarrollo (uv + logs + OCR obligatorio)

Ejecuta desde `backend/`:

```powershell
.\scripts\dev.ps1
```

El script hace:
1. valida que el puerto `8000` esté libre,
2. sincroniza dependencias con `uv sync --dev`,
3. ejecuta preflight OCR obligatorio (`paddle`, `paddleocr`, `chardet`),
4. arranca FastAPI con logs detallados:
   `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --access-log --log-level debug`.

## Verificación rápida

En otra terminal:

```powershell
curl http://127.0.0.1:8000/health
```

Debe responder `{"status":"ok"}` y en la consola del backend verás los logs de access + middleware HTTP.

## Credenciales de seed

```text
admin@microcred.com / Admin@12345
gerente@microcred.com / Gerente@12345
agente@microcred.com / Agente@12345
```

Si faltan datos de prueba:

```powershell
uv run python seed.py
```
