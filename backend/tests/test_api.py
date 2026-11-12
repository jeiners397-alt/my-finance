from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app, bounds
from app.models import (
    Account,
    Bot,
    Strategy,
    Trade,
    TradeSample,
    EquitySnapshot,
    CashLedger,
    ServerMetric,
)

T = datetime(2026, 1, 2, tzinfo=UTC)


async def seed(db):
    async with db() as s, s.begin():
        s.add_all(
            [
                Account(
                    id=i,
                    name=f"A{i}",
                    platform="BINANCE_FUTURES",
                    mode="PAPER",
                    external_account_ref=str(i),
                    currency="USDT",
                )
                for i in [1, 2]
            ]
        )
        await s.flush()
        s.add_all(
            [
                Strategy(id=1, name="Test", version="1"),
                Bot(id=1, account_id=1, name="B1"),
                Bot(id=2, account_id=2, name="B2"),
            ]
        )
        await s.flush()
        for i in [1, 2, 3]:
            s.add(
                Trade(
                    id=i,
                    account_id=2 if i == 3 else 1,
                    bot_id=2 if i == 3 else 1,
                    strategy_id=1,
                    trade_key=str(i),
                    symbol="BTCUSDT",
                    side="LONG",
                    quantity_unit="BASE",
                    contract_size=1,
                    status="CLOSED",
                    opened_at=T,
                    closed_at=T + timedelta(hours=1),
                )
            )
        await s.flush()
        for key, trade, kind, amount, time in [
            ("win", 1, "REALIZED_PNL", 12, T + timedelta(hours=1)),
            ("fee", 1, "COMMISSION", -2, T),
            ("loss", 2, "REALIZED_PNL", -5, T + timedelta(hours=1)),
            ("deposit", None, "DEPOSIT", 1000, T),
        ]:
            s.add(
                CashLedger(
                    account_id=1,
                    trade_id=trade,
                    entry_key=key,
                    occurred_at=time,
                    kind=kind,
                    amount_native=amount,
                    native_currency="USDT",
                    fx_to_account=1,
                    amount_account=amount,
                    conversion_at=time,
                    conversion_source="identity",
                )
            )
        for i, value in enumerate([120, 100, 110]):
            s.add(
                EquitySnapshot(
                    account_id=1,
                    snapshot_key=str(i),
                    observed_at=T + timedelta(hours=i - 1),
                    balance=value,
                    unrealized_pnl=0,
                    equity=value,
                    source="test",
                )
            )
        s.add(
            ServerMetric(
                bot_id=2,
                host_ref="secret-other-account",
                observed_at=T,
                cpu_pct=99,
                db_status="OK",
            )
        )


@pytest.mark.asyncio
async def test_auth_and_cors():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        assert (await c.get("/api/v1/telemetry/latest")).status_code == 401
        r = await c.options(
            "/api/v1/ingest/trade-sample",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert (
            "access-control-allow-origin"
            not in (
                await c.options(
                    "/health",
                    headers={
                        "Origin": "https://evil.test",
                        "Access-Control-Request-Method": "GET",
                    },
                )
            ).headers
        )


async def test_isolation_calendar_and_strategies(db, client):
    await seed(db)
    assert (await client.get("/api/v1/accounts/2")).status_code == 404
    assert (await client.get("/api/v1/trades/3")).status_code == 404
    assert (await client.get("/api/v1/telemetry/latest")).json()["metric"] is None
    result = (
        await client.get(
            "/api/v1/analytics/strategies/1",
            params={"start": T.isoformat(), "end": (T + timedelta(days=1)).isoformat()},
        )
    ).json()["strategies"][0]
    assert result["net_pnl"] == 5
    assert (
        result["trades"] == 2
        and result["win_rate"] == 50
        and result["profit_factor"] == 2
    )
    assert result["pnl_pct"] == pytest.approx(5 / 120 * 100)
    result = (
        await client.get(
            "/api/v1/analytics/calendar/1",
            params={"year": 2026, "month": 1, "timezone": "America/Lima"},
        )
    ).json()
    assert result["net_pnl"] == 5  # Deposit excluded, costs included.
    assert result["days"][0]["net_pnl"] == 5 and result["days"][1]["net_pnl"] == 0
    assert result["summary"] == {"commissions": 2, "trades": 2}
    assert (
        await client.get(
            "/api/v1/analytics/calendar/1",
            params={"year": 2026, "month": 1, "timezone": "invalid"},
        )
    ).status_code == 422


async def test_drawdown_pagination_uses_historical_peak(db, client):
    await seed(db)
    params = {
        "start": T.isoformat(),
        "end": (T + timedelta(days=1)).isoformat(),
        "limit": 1,
    }
    a = (await client.get("/api/v1/analytics/equity-curve/1", params=params)).json()
    assert a["points"][0]["peak_equity"] == 120
    assert a["points"][0]["drawdown_pct"] == pytest.approx(-100 / 6)
    b = (
        await client.get(
            "/api/v1/analytics/equity-curve/1",
            params={**params, "cursor": a["next_cursor"]},
        )
    ).json()
    assert b["points"][0]["equity"] == 110 and b["points"][0]["peak_equity"] == 120
    assert b["next_cursor"] is None


async def test_ingestion_idempotency_and_validation(db, client):
    await seed(db)
    sample = {
        "trade_id": 1,
        "sample_key": "same",
        "observed_at": T.isoformat(),
        "observed_price": "100.25",
        "price_type": "MARK",
        "source": "test",
        "stop_loss": "90",
        "take_profit": None,
    }
    a = await client.post("/api/v1/ingest/trade-sample", json=sample)
    assert a.status_code == 201, a.text
    b = await client.post("/api/v1/ingest/trade-sample", json=sample)
    assert b.status_code == 200 and b.json()["id"] == a.json()["id"]
    assert (
        await client.post(
            "/api/v1/ingest/trade-sample", json={**sample, "observed_price": "101"}
        )
    ).status_code == 409
    assert (
        await client.post(
            "/api/v1/ingest/trade-sample",
            json={
                **sample,
                "sample_key": "bad",
                "observed_at": (T - timedelta(seconds=1)).isoformat(),
            },
        )
    ).status_code == 422
    assert (
        await client.post("/api/v1/ingest/trade-sample", json={**sample, "trade_id": 3})
    ).status_code == 404
    detail = (await client.get("/api/v1/trades/1")).json()
    assert detail["samples"][0]["seconds_from_entry"] == 0
    assert detail["samples"][0]["take_profit"] is None
    assert detail["net_pnl"] == 10


async def test_trade_sample_pagination_and_latest_metric(db, client):
    await seed(db)
    async with db() as s, s.begin():
        s.add_all(
            [
                TradeSample(
                    trade_id=1,
                    sample_key=str(i),
                    observed_at=T + timedelta(seconds=i * 2),
                    observed_price=100 + i,
                    price_type="MARK",
                    source="test",
                )
                for i in range(3)
            ]
        )
        s.add(
            ServerMetric(
                bot_id=1, host_ref="own-host", observed_at=T, cpu_pct=10, db_status="OK"
            )
        )
    page = (await client.get("/api/v1/trades/1", params={"limit": 2})).json()
    assert len(page["samples"]) == 2
    next_page = (
        await client.get(
            "/api/v1/trades/1", params={"limit": 2, "cursor": page["next_cursor"]}
        )
    ).json()
    assert next_page["samples"][0]["seconds_from_entry"] == 4
    assert next_page["next_cursor"] is None
    assert (await client.get("/api/v1/telemetry/latest")).json()["metric"][
        "host_ref"
    ] == "own-host"
    listed = (await client.get("/api/v1/trades")).json()["trades"]
    assert [t["id"] for t in listed] == [1, 2]
