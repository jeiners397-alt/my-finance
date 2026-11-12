"""Explicit synthetic fixtures for an empty local database; never run on a live DB."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import sin
from sqlalchemy import select
from app.database import SessionFactory, engine
from app.models import (
    Account,
    Bot,
    Strategy,
    Trade,
    Execution,
    CashLedger,
    EquitySnapshot,
    TradeSample,
    ServerMetric,
)


async def main():
    async with SessionFactory() as s, s.begin():
        if await s.scalar(select(Account.id).limit(1)):
            raise RuntimeError("La base ya tiene cuentas. No se modificaron sus datos.")
        account = Account(
            name="A13 Demo local",
            platform="BINANCE_FUTURES",
            mode="DEMO",
            external_account_ref="synthetic-local",
            currency="USDT",
        )
        s.add(account)
        await s.flush()
        bot = Bot(
            account_id=account.id, name="Precision Scalper Demo", code_version="demo-v1"
        )
        strategies = [
            Strategy(name=n, version="demo-v1")
            for n in [
                "Extreme Momentum",
                "Volatility Breakout",
                "Liquidity Sweep",
                "Exhaustion Reversal",
                "Micro Pullback",
            ]
        ]
        s.add_all([bot, *strategies])
        await s.flush()
        now = datetime.now(UTC)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        balance = Decimal("100")
        s.add(
            EquitySnapshot(
                account_id=account.id,
                snapshot_key="initial",
                observed_at=start,
                balance=balance,
                unrealized_pnl=0,
                equity=balance,
                source="synthetic",
            )
        )
        for day in range(1, now.day + 1):
            opened = start + timedelta(days=day - 1, hours=1)
            closed = opened + timedelta(minutes=4)
            if closed > now:
                continue
            gross = Decimal(str(round(sin(day * 1.7) * 2.8 + 0.55, 4)))
            trade = Trade(
                account_id=account.id,
                bot_id=bot.id,
                strategy_id=strategies[day % 5].id,
                trade_key=f"demo-{day}",
                symbol="ETHUSDT",
                side="LONG",
                quantity_unit="BASE",
                contract_size=1,
                status="CLOSED",
                opened_at=opened,
                closed_at=closed,
                initial_sl=2550,
                initial_tp=2650,
                exit_reason="MANUAL",
            )
            s.add(trade)
            await s.flush()
            exit_price = Decimal("2600") + gross / Decimal(".1")
            s.add_all(
                [
                    Execution(
                        account_id=account.id,
                        trade_id=trade.id,
                        execution_key=f"in-{day}",
                        executed_at=opened,
                        role="ENTRY",
                        price=2600,
                        quantity=Decimal(".1"),
                    ),
                    Execution(
                        account_id=account.id,
                        trade_id=trade.id,
                        execution_key=f"out-{day}",
                        executed_at=closed,
                        role="EXIT",
                        price=exit_price,
                        quantity=Decimal(".1"),
                    ),
                ]
            )
            for suffix, kind, amount, time in [
                ("in-fee", "COMMISSION", Decimal("-.02"), opened),
                ("pnl", "REALIZED_PNL", gross, closed),
                ("out-fee", "COMMISSION", Decimal("-.02"), closed),
            ]:
                s.add(
                    CashLedger(
                        account_id=account.id,
                        trade_id=trade.id,
                        entry_key=f"{day}-{suffix}",
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
            for i in range(121):
                price = Decimal("2600") + (exit_price - 2600) * Decimal(i) / 120
                s.add(
                    TradeSample(
                        trade_id=trade.id,
                        sample_key=f"{day}-{i}",
                        observed_at=opened + timedelta(seconds=i * 2),
                        observed_price=price,
                        price_type="LAST",
                        stop_loss=2550,
                        take_profit=2650,
                        source="synthetic",
                    )
                )
            balance += gross - Decimal(".04")
            s.add(
                EquitySnapshot(
                    account_id=account.id,
                    snapshot_key=f"close-{day}",
                    observed_at=closed,
                    balance=balance,
                    unrealized_pnl=0,
                    equity=balance,
                    source="synthetic",
                )
            )
        s.add(
            ServerMetric(
                host_ref="local-demo",
                bot_id=bot.id,
                observed_at=now,
                cpu_pct=11,
                ram_pct=56,
                api_latency_ms=84,
                db_status="OK",
            )
        )
        print(
            f"Datos SINTÉTICOS creados. Account ID: {account.id}. Configura ACCOUNT_TOKENS para este ID."
        )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
