# My Finance — Trading Dashboard

Dashboard de monitorización para bots Binance Futures / MT5 Exness. **React + Vite + Tailwind + Recharts**, backend **FastAPI + SQLAlchemy 2 asyncio + PostgreSQL**. Interfaz en español, tema oscuro y modo demo inmediato, sin base de datos.

## Inicio rápido: frontend demo

Requisitos: Git, Node.js **20.19+** (recomendado 22/24), npm. Para el backend: Python **3.11+** y PostgreSQL **17**, o Docker Compose.

```bash
git clone https://github.com/jeiners397-alt/my-finance.git
cd my-finance
git checkout feat/trading-dashboard
cd frontend
npm ci
npm run dev
```

Abre **http://localhost:5173**. El interruptor **Modo Demo / Datos de prueba** está activo inicialmente. Los datos son sintéticos y deterministas; no representan resultados de una cuenta real. El mes y la selección de operación funcionan sin backend. No hay claves de exchange ni secretos incluidos.

## Backend local con PostgreSQL

Desde la raíz, inicia la base de datos local (puerto enlazado solo a localhost):

```bash
docker compose up -d --wait postgres
cd backend
python -m venv .venv
```

Activa el entorno:

```bash
# Linux / macOS
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Después, dentro de `backend/`:

```bash
python -m pip install -r requirements.txt
python -m app.configure_local
alembic upgrade head
python -m app.seed_demo
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

`configure_local` crea `.env` con un token aleatorio. No sobrescribe uno existente. Si ya tienes PostgreSQL, configura `DATABASE_URL` con formato `postgresql+asyncpg://usuario:contraseña@host:5432/base` en `.env` y omite Docker. Escapa los caracteres reservados de la contraseña en la URL.

`seed_demo` es **opcional** y solo permite una base sin cuentas. Crea datos sintéticos identificados como DEMO, con ejecuciones, libro contable, muestras y telemetría; muestra el ID de cuenta creado. Una base recién creada produce el ID 1. Verifica que `ACCOUNT_TOKENS` use ese ID.

La consola de OpenAPI está en **http://localhost:8000/docs**. Usa el botón Authorize con el valor del token, sin el prefijo Bearer.

Para probar el flujo completo: en la interfaz desactiva Demo, indica la cuenta y copia el valor de su token desde `backend/.env`. No pegues las llaves de Binance/Exness. El token del dashboard vive solo en memoria del navegador y se pierde al recargar.

## Frontend y backend en terminales separadas

```bash
# Terminal 1, desde backend/ con el entorno activado
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2, desde frontend/
npm ci
npm run dev
```

El frontend usa por defecto `http://localhost:8000/api/v1`. Para otro servidor copia `frontend/.env.example` a `frontend/.env` y cambia `VITE_API_BASE_URL`. Reinicia Vite después. **Nunca pongas tokens en variables `VITE_*`: se incorporan al código público.**

CORS admite `http://localhost:5173`; otras URLs requieren añadirlas a `CORS_ORIGINS` en el `.env` del backend. El frontend consulta cada 15 segundos, sin solicitudes solapadas. Cambiar filtros cancela las peticiones anteriores. Las páginas de equidad, operaciones y muestras se cargan hasta completar los resultados. Si una actualización falla, se identifica el error y se mantienen los últimos datos visibles.

## Estructura

| Ruta | Contenido |
|---|---|
| `backend/app/models.py` | Cuentas, estrategias, bots, trades, ejecuciones, libro, equidad, muestras y telemetría |
| `backend/app/main.py` | Autenticación, CORS y endpoints |
| `backend/app/database.py` | Engine asyncpg y AsyncSession |
| `backend/migrations/` | Migración inicial inmutable y configuración Alembic |
| `backend/tests/` | Pruebas HTTP con PostgreSQL aislado por esquema |
| `frontend/src/components/` | KPIs, barras, equidad/DD, trades, calendario y telemetría |
| `frontend/src/lib/api.js` | Cliente HTTP y paginación |
| `frontend/src/lib/demo.js` | Generador demo independiente de la API |
| `compose.yaml` | PostgreSQL local persistente |

## Contrato API

Todos los endpoints `/api/v1` requieren `Authorization: Bearer <token>`. El ID de cuenta proviene del token configurado: no se confía en el ID que envía el cliente para autorizar acceso. Operaciones ajenas devuelven 404. La telemetría sin bot asignado no se publica.

| Método / ruta | Parámetros / resultado |
|---|---|
| `POST /api/v1/ingest/trade-sample` | Muestra validada, idempotente por `(trade_id, sample_key)` |
| `GET /api/v1/accounts/{account_id}` | Moneda, modo y capital inicial observado |
| `GET /api/v1/analytics/equity-curve/{account_id}` | `start`, `end` ISO con zona; `cursor`, `limit`; puntos con equidad, máximo y DD |
| `GET /api/v1/analytics/strategies/{account_id}` | `start`, `end`; PnL neto, % inicial de cuenta, trades, WR, PF |
| `GET /api/v1/analytics/calendar/{account_id}` | `year`, `month`, `timezone=UTC`; días, comisiones y cierres |
| `GET /api/v1/trades` | `cursor`, `limit`; lista paginada para el selector |
| `GET /api/v1/trades/{trade_id}` | `cursor`, `limit`; operación y muestras con segundos desde entrada |
| `GET /api/v1/telemetry/latest` | Última métrica de la cuenta y bandera `stale` (>120 s) |
| `GET /health` | Liveness del proceso; no certifica disponibilidad de PostgreSQL |

Muestra de ingesta (usar una operación existente y un timestamp dentro de su intervalo):

```json
{
  "trade_id": 1,
  "sample_key": "bot-1:trade-1:tick-00001",
  "observed_at": "2026-01-02T00:00:00Z",
  "observed_price": "2600.123456",
  "price_type": "MARK",
  "stop_loss": "2550",
  "take_profit": "2650",
  "source": "bot-webhook"
}
```

Primera inserción: 201; reenvío idéntico: 200; misma clave con contenido diferente: 409. `null` en SL/TP significa nivel inactivo; el emisor debe enviar el estado vigente completo. Las muestras históricas dentro del intervalo de un trade cerrado se aceptan. No se permiten muestras futuras con más de 30 s de desviación.

## Definiciones contables

- Importes/precios en `NUMERIC(38,18)`; fechas UTC con `TIMESTAMPTZ`. La API convierte importes a números JSON para gráficos; no usar el redondeo del frontend como libro contable.
- Comisiones/costes son negativos en `cash_ledger`; depósitos positivos y retiros negativos. Funding/swap pueden tener ambos signos. `amount_account` siempre está convertido a la moneda de la cuenta; la conversión y su procedencia se conservan.
- Calendario: PnL del libro por fecha de contabilización, excluyendo depósitos/retiros/ajustes. Comisiones se muestran como coste positivo neto de reembolsos. Cuenta **trades cerrados**, no fills ni movimientos. Días futuros aparecen sin datos.
- Estrategias: trades cerrados en el periodo; todo el PnL y costes atribuidos a esos trades, incluso de otras fechas. Por eso no tiene por qué coincidir con el calendario del mismo mes. No atribuye costes sin `trade_id`.
- WR = ganadoras / trades cerrados; incluye neutras en el denominador. PF = suma de PnL netos positivos / valor absoluto de negativos; sin pérdidas es `null`, no cero ni infinito JSON.
- `% PnL` por estrategia usa la primera equidad histórica **de la cuenta**, no capital asignado por estrategia. El rótulo lo indica.
- DD conserva el máximo anterior al filtro y a las páginas: `100*(equity/peak-1)`. No está ajustado por aportaciones/retiros. Equidades máximas no positivas producen DD nulo.
- Curva y estrategias usan el mes UTC seleccionado; calendario usa la zona elegida. La interfaz identifica esta diferencia.
- Gráfico de trades: precios observados; huecos >10 s cortan la línea. Equidad real: huecos >120 s. Ajusta estas tolerancias a tu muestreo. Precio de entrada/salida es media ponderada de ejecuciones; el marcador de salida está en el cierre final y representa esa media, no necesariamente la última ejecución.

## Conectar bots reales

Este proyecto implementa el dashboard, la base y la ingesta de muestras. **No contiene todavía un conector que descargue automáticamente cuentas, operaciones o equidad desde Binance/MT5, ni ejecuta órdenes.** Tu bot/adaptador debe persistir cuentas, bots, estrategias, ejecuciones, libro, equidad y telemetría mediante un proceso confiable del servidor. Después puede enviar muestras al endpoint de ingesta. Los IDs de ejecución y movimientos deben ser estables; cantidades acumuladas y cierre deben validarse en ese adaptador.

Para crear una cuenta real utiliza una migración/script administrativo revisado; conserva sus credenciales fuera del repositorio y añade su token de dashboard a `ACCOUNT_TOKENS`. No mezcles PAPER/DEMO/LIVE ni sumes monedas diferentes sin conversión explícita.

## Pruebas

```bash
# frontend/
npm test
npm run build

# backend/ (entorno activado)
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Sin `TEST_DATABASE_URL`, solo se ejecuta la prueba de autenticación/CORS y se omiten las pruebas de PostgreSQL. Para ejecutar todo en la base local:

```bash
# Linux/macOS, backend/
TEST_DATABASE_URL=postgresql+asyncpg://dashboard:dashboard_local@localhost:5432/trading python -m pytest -q
```

```powershell
# PowerShell, backend/
$env:TEST_DATABASE_URL='postgresql+asyncpg://dashboard:dashboard_local@localhost:5432/trading'
python -m pytest -q
```

Cada prueba crea y elimina exclusivamente un esquema aleatorio `test_*`; no utiliza las tablas de la aplicación. Se requiere permiso CREATE SCHEMA. GitHub Actions verifica migraciones, tests API con PostgreSQL 17, tests frontend y build.

## Despliegue

```bash
# backend/ con entorno configurado
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2

# frontend/
npm ci
npm run build
```

Publica `frontend/dist/` con un servidor estático y un proxy HTTPS para la API. Configura CORS para el dominio exacto, contraseñas propias, copias de seguridad, límites de tamaño/tasa en el proxy y rotación de tokens. El Compose incluido es **solo para desarrollo local**. No uses `--reload`, el servidor de Vite ni las credenciales locales para producción. Los tokens actuales son de cuenta y permiten lectura + ingesta de muestras; para usuarios externos/multiusuario se requiere gestión de identidades y permisos diferenciados. No se ha realizado una auditoría de seguridad de producción ni una prueba de carga.
