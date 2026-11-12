import calendar
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import engine, get_session
from app.models import (
    Account,
    Bot,
    CashLedger,
    EquitySnapshot,
    Execution,
    ServerMetric,
    Strategy,
    Trade,
    TradeSample,
)

PNL_KINDS = ("REALIZED_PNL", "COMMISSION", "FUNDING", "SWAP", "FEE")
logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)
Session = Annotated[AsyncSession, Depends(get_session)]


@asynccontextmanager
async def lifespan(app):
    yield
    await engine.dispose()


app = FastAPI(
    title="My Finance — Trading Analytics", version="1.0.0", lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(SQLAlchemyError)
async def db_error(request, exc):
    logger.error("Database failure: %s", type(exc).__name__)
    return JSONResponse(
        status_code=503,
        content={"detail": "Base de datos no disponible"},
        headers={"Retry-After": "5"},
    )


async def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
    if credentials:
        for account_id, token in get_settings().account_tokens.items():
            if secrets.compare_digest(
                credentials.credentials.encode(), token.get_secret_value().encode()
            ):
                return account_id
    raise HTTPException(
        401, "Credenciales inválidas", headers={"WWW-Authenticate": "Bearer"}
    )


Principal = Annotated[int, Depends(authenticate)]


async def account_for(session, account_id, principal):
    if account_id != principal:
        raise HTTPException(404, "Cuenta no encontrada")
    account = await session.get(Account, account_id)
    if account is None:
        raise HTTPException(404, "Cuenta no encontrada")
    return account


def bounds(start, end):
    end = end.astimezone(UTC) if end else datetime.now(UTC)
    start = start.astimezone(UTC) if start else end - timedelta(days=30)
    if start >= end or end - start > timedelta(days=366):
        raise HTTPException(422, "Intervalo inválido: start < end, máximo 366 días")
    return start, end


def num(value):
    return float(value) if value is not None else None


async def initial_equity(session, account_id):
    return await session.scalar(
        select(EquitySnapshot.equity)
        .where(EquitySnapshot.account_id == account_id)
        .order_by(EquitySnapshot.observed_at)
        .limit(1)
    )


def results_query(account_id, start, end):
    # Aggregate ledger first to prevent fill-count multiplication.
    ledger = (
        select(CashLedger.trade_id, func.sum(CashLedger.amount_account).label("net"))
        .where(CashLedger.account_id == account_id, CashLedger.kind.in_(PNL_KINDS))
        .group_by(CashLedger.trade_id)
        .subquery()
    )
    return (
        select(
            Trade.id,
            Trade.strategy_id,
            Trade.symbol,
            Trade.side,
            Trade.closed_at,
            func.coalesce(ledger.c.net, 0).label("net_pnl"),
        )
        .outerjoin(ledger, ledger.c.trade_id == Trade.id)
        .where(
            Trade.account_id == account_id,
            Trade.status == "CLOSED",
            Trade.closed_at >= start,
            Trade.closed_at < end,
        )
    )


class SampleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    trade_id: int = Field(gt=0)
    sample_key: str = Field(min_length=1, max_length=200)
    observed_at: AwareDatetime
    observed_price: Decimal = Field(
        gt=0, max_digits=38, decimal_places=18, allow_inf_nan=False
    )
    price_type: Literal["LAST", "MARK", "BID", "ASK", "MID"]
    stop_loss: Decimal | None = Field(
        None, gt=0, max_digits=38, decimal_places=18, allow_inf_nan=False
    )
    take_profit: Decimal | None = Field(
        None, gt=0, max_digits=38, decimal_places=18, allow_inf_nan=False
    )
    source: str = Field(min_length=1, max_length=100)


@app.get("/health")
async def health():
    return {"status": "ok"}  # Liveness only, not a DB readiness assertion.


@app.post("/api/v1/ingest/trade-sample", status_code=201)
async def ingest_sample(
    payload: SampleInput, response: Response, session: Session, principal: Principal
):
    values = payload.model_dump()
    values["observed_at"] = payload.observed_at.astimezone(UTC)
    async with session.begin():
        trade = await session.scalar(
            select(Trade)
            .where(Trade.id == payload.trade_id, Trade.account_id == principal)
            .with_for_update(read=True)
        )
        if trade is None:
            raise HTTPException(404, "Operación no encontrada")
        # A replay remains valid even if the trade has subsequently closed.
        existing = await session.scalar(
            select(TradeSample).where(
                TradeSample.trade_id == payload.trade_id,
                TradeSample.sample_key == payload.sample_key,
            )
        )
        if existing is None:
            observed = values["observed_at"]
            if observed < trade.opened_at or (
                trade.closed_at and observed > trade.closed_at
            ):
                raise HTTPException(422, "Muestra fuera del intervalo de la operación")
            if observed > datetime.now(UTC) + timedelta(seconds=30):
                raise HTTPException(422, "Timestamp futuro fuera de tolerancia")
            sample_id = await session.scalar(
                insert(TradeSample)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["trade_id", "sample_key"])
                .returning(TradeSample.id)
            )
            if sample_id is not None:
                return {
                    "id": sample_id,
                    "trade_id": payload.trade_id,
                    "sample_key": payload.sample_key,
                    "created": True,
                }
            existing = await session.scalar(
                select(TradeSample).where(
                    TradeSample.trade_id == payload.trade_id,
                    TradeSample.sample_key == payload.sample_key,
                )
            )
        if existing is None or any(
            getattr(existing, k) != v for k, v in values.items()
        ):
            raise HTTPException(409, "sample_key ya existe con un contenido diferente")
        response.status_code = 200
        return {
            "id": existing.id,
            "trade_id": payload.trade_id,
            "sample_key": payload.sample_key,
            "created": False,
        }


@app.get("/api/v1/accounts/{account_id}")
async def account_info(account_id: int, session: Session, principal: Principal):
    a = await account_for(session, account_id, principal)
    return {
        "id": a.id,
        "name": a.name,
        "currency": a.currency,
        "mode": a.mode,
        "platform": a.platform,
        "initial_capital": num(await initial_equity(session, account_id)),
    }


@app.get("/api/v1/analytics/equity-curve/{account_id}")
async def equity_curve(
    account_id: int,
    session: Session,
    principal: Principal,
    start: AwareDatetime | None = None,
    end: AwareDatetime | None = None,
    cursor: AwareDatetime | None = None,
    limit: int = Query(5000, ge=1, le=10000),
):
    account = await account_for(session, account_id, principal)
    start, end = bounds(start, end)
    if cursor is not None and not start <= cursor < end:
        raise HTTPException(422, "Cursor fuera del intervalo")
    prior = (
        select(func.max(EquitySnapshot.equity))
        .where(
            EquitySnapshot.account_id == account_id, EquitySnapshot.observed_at < start
        )
        .scalar_subquery()
    )
    peak = func.greatest(
        prior,
        func.max(EquitySnapshot.equity).over(
            order_by=EquitySnapshot.observed_at, rows=(None, 0)
        ),
    )
    series = (
        select(
            EquitySnapshot.observed_at.label("timestamp"),
            EquitySnapshot.equity,
            peak.label("peak_equity"),
        )
        .where(
            EquitySnapshot.account_id == account_id,
            EquitySnapshot.observed_at >= start,
            EquitySnapshot.observed_at < end,
        )
        .subquery()
    )
    stmt = select(series).order_by(series.c.timestamp)
    if cursor:
        stmt = stmt.where(series.c.timestamp > cursor)
    rows = (await session.execute(stmt.limit(limit + 1))).mappings().all()
    more = len(rows) > limit
    points = [
        {
            "timestamp": r["timestamp"],
            "equity": num(r["equity"]),
            "peak_equity": num(r["peak_equity"]),
            "drawdown_pct": num(100 * (r["equity"] / r["peak_equity"] - 1))
            if r["peak_equity"] > 0
            else None,
        }
        for r in rows[:limit]
    ]
    return {
        "account_id": account_id,
        "currency": account.currency,
        "start": start,
        "end": end,
        "drawdown_basis": "raw_equity",
        "cash_flow_adjusted": False,
        "points": points,
        "next_cursor": points[-1]["timestamp"] if more else None,
    }


@app.get("/api/v1/analytics/strategies/{account_id}")
async def strategy_results(
    account_id: int,
    session: Session,
    principal: Principal,
    start: AwareDatetime | None = None,
    end: AwareDatetime | None = None,
):
    account = await account_for(session, account_id, principal)
    start, end = bounds(start, end)
    trades = results_query(account_id, start, end).subquery()
    net = trades.c.net_pnl
    stmt = (
        select(
            Strategy.id,
            Strategy.name,
            Strategy.version,
            func.count().label("trades"),
            func.sum(net).label("net_pnl"),
            func.sum(case((net > 0, 1), else_=0)).label("wins"),
            func.sum(case((net < 0, 1), else_=0)).label("losses"),
            func.sum(case((net > 0, net), else_=0)).label("positive"),
            func.sum(case((net < 0, -net), else_=0)).label("negative"),
        )
        .join(trades, trades.c.strategy_id == Strategy.id)
        .group_by(Strategy.id)
        .order_by(func.sum(net).desc())
    )
    rows = (await session.execute(stmt)).mappings().all()
    capital = await initial_equity(session, account_id)
    return {
        "account_id": account_id,
        "currency": account.currency,
        "pnl_pct_basis": "initial_account_equity",
        "initial_capital": num(capital),
        "strategies": [
            {
                "id": r["id"],
                "name": r["name"],
                "version": r["version"],
                "net_pnl": num(r["net_pnl"]),
                "pnl_pct": num(100 * r["net_pnl"] / capital)
                if capital and capital > 0
                else None,
                "trades": r["trades"],
                "wins": r["wins"],
                "losses": r["losses"],
                "win_rate": 100 * r["wins"] / r["trades"],
                "profit_factor": num(r["positive"] / r["negative"])
                if r["negative"] > 0
                else None,
                "profit_factor_status": "defined" if r["negative"] > 0 else "no_losses",
            }
            for r in rows
        ],
    }


@app.get("/api/v1/analytics/calendar/{account_id}")
async def pnl_calendar(
    account_id: int,
    session: Session,
    principal: Principal,
    year: int = Query(..., ge=1970, le=9998),
    month: int = Query(..., ge=1, le=12),
    timezone: str = Query("UTC", max_length=100),
):
    account = await account_for(session, account_id, principal)
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Zona horaria IANA inválida") from None
    start = datetime(year, month, 1, tzinfo=zone).astimezone(UTC)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=zone).astimezone(UTC)
    day_expr = cast(func.timezone(timezone, CashLedger.occurred_at), Date)
    stmt = (
        select(
            day_expr.label("day"),
            func.sum(CashLedger.amount_account).label("pnl"),
            func.count().label("entries"),
            func.sum(
                case(
                    (CashLedger.kind == "COMMISSION", -CashLedger.amount_account),
                    else_=0,
                )
            ).label("commissions"),
        )
        .where(
            CashLedger.account_id == account_id,
            CashLedger.kind.in_(PNL_KINDS),
            CashLedger.occurred_at >= start,
            CashLedger.occurred_at < end,
        )
        .group_by(day_expr)
    )
    rows = (await session.execute(stmt)).mappings().all()
    lookup = {r["day"]: r for r in rows}
    close_day = cast(func.timezone(timezone, Trade.closed_at), Date)
    trade_rows = (
        await session.execute(
            select(close_day, func.count())
            .where(
                Trade.account_id == account_id,
                Trade.status == "CLOSED",
                Trade.closed_at >= start,
                Trade.closed_at < end,
            )
            .group_by(close_day)
        )
    ).all()
    counts = dict(trade_rows)
    today = datetime.now(zone).date()
    days = []
    for d in range(1, calendar.monthrange(year, month)[1] + 1):
        day = date(year, month, d)
        r = lookup.get(day)
        future = day > today
        days.append(
            {
                "date": day,
                "net_pnl": None if future else num(r["pnl"]) if r else 0,
                "ledger_entries": None if future else r["entries"] if r else 0,
                "trades": None if future else counts.get(day, 0),
                "is_future": future,
            }
        )
    return {
        "account_id": account_id,
        "currency": account.currency,
        "timezone": timezone,
        "year": year,
        "month": month,
        "net_pnl": num(sum((r["pnl"] for r in rows), Decimal(0))),
        "summary": {
            "commissions": num(sum((r["commissions"] for r in rows), Decimal(0))),
            "trades": sum(counts.values()),
        },
        "days": days,
    }


@app.get("/api/v1/trades")
async def list_trades(
    session: Session,
    principal: Principal,
    cursor: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    rows = (
        (
            await session.execute(
                select(
                    Trade.id,
                    Trade.symbol,
                    Trade.side,
                    Trade.status,
                    Trade.opened_at,
                    Strategy.name.label("strategy_name"),
                )
                .join(Strategy)
                .where(Trade.account_id == principal, Trade.id > cursor)
                .order_by(Trade.id)
                .limit(limit + 1)
            )
        )
        .mappings()
        .all()
    )
    return {
        "trades": [dict(r) for r in rows[:limit]],
        "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
    }


@app.get("/api/v1/trades/{trade_id}")
async def trade_detail(
    trade_id: int,
    session: Session,
    principal: Principal,
    cursor: int = Query(0, ge=0),
    limit: int = Query(5000, ge=1, le=10000),
):
    row = (
        await session.execute(
            select(Trade, Strategy.name)
            .join(Strategy)
            .where(Trade.id == trade_id, Trade.account_id == principal)
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Operación no encontrada")
    trade, strategy_name = row
    execution_rows = (
        await session.execute(
            select(
                Execution.role,
                (
                    func.sum(Execution.price * Execution.quantity)
                    / func.sum(Execution.quantity)
                ).label("price"),
            )
            .where(Execution.trade_id == trade_id)
            .group_by(Execution.role)
        )
    ).all()
    prices = dict(execution_rows)
    rows = (
        await session.scalars(
            select(TradeSample)
            .where(TradeSample.trade_id == trade_id, TradeSample.id > cursor)
            .order_by(TradeSample.id)
            .limit(limit + 1)
        )
    ).all()
    pnl = await session.scalar(
        select(func.coalesce(func.sum(CashLedger.amount_account), 0)).where(
            CashLedger.account_id == principal,
            CashLedger.trade_id == trade_id,
            CashLedger.kind.in_(PNL_KINDS),
        )
    )
    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "side": trade.side,
        "status": trade.status,
        "strategy_name": strategy_name,
        "opened_at": trade.opened_at,
        "closed_at": trade.closed_at,
        "initial_sl": num(trade.initial_sl),
        "initial_tp": num(trade.initial_tp),
        "entry_price": num(prices.get("ENTRY")),
        "exit_price": num(prices.get("EXIT")) if trade.closed_at else None,
        "exit_seconds": (trade.closed_at - trade.opened_at).total_seconds()
        if trade.closed_at
        else None,
        "exit_reason": trade.exit_reason,
        "net_pnl": num(pnl),
        "samples": [
            {
                "id": s.id,
                "observed_at": s.observed_at,
                "seconds_from_entry": (s.observed_at - trade.opened_at).total_seconds(),
                "observed_price": num(s.observed_price),
                "stop_loss": num(s.stop_loss),
                "take_profit": num(s.take_profit),
                "price_type": s.price_type,
            }
            for s in rows[:limit]
        ],
        "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
    }


@app.get("/api/v1/telemetry/latest")
async def latest_telemetry(session: Session, principal: Principal):
    # Unattributed host metrics are never exposed to account-scoped credentials.
    metric = await session.scalar(
        select(ServerMetric)
        .join(Bot, ServerMetric.bot_id == Bot.id)
        .where(Bot.account_id == principal)
        .order_by(ServerMetric.observed_at.desc(), ServerMetric.id.desc())
        .limit(1)
    )
    if metric is None:
        return {"metric": None, "stale": True}
    return {
        "metric": {
            "host_ref": metric.host_ref,
            "bot_id": metric.bot_id,
            "observed_at": metric.observed_at,
            "cpu_pct": num(metric.cpu_pct),
            "ram_pct": num(metric.ram_pct),
            "api_latency_ms": num(metric.api_latency_ms),
            "db_latency_ms": num(metric.db_latency_ms),
            "db_status": metric.db_status,
            "bot_memory_mb": num(metric.bot_memory_mb),
        },
        "stale": (datetime.now(UTC) - metric.observed_at).total_seconds() > 120,
    }
