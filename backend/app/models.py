from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


MONEY = Numeric(38, 18)
TIME = DateTime(timezone=True)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("platform IN ('BINANCE_FUTURES','MT5_EXNESS')"),
        CheckConstraint("mode IN ('PAPER','DEMO','LIVE')"),
        UniqueConstraint("platform", "mode", "external_account_ref"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text)
    external_account_ref: Mapped[str] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text)
    reporting_timezone: Mapped[str] = mapped_column(Text, server_default="UTC")
    secret_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIME, server_default=func.now())


class Strategy(Base):
    __tablename__ = "strategies"
    __table_args__ = (UniqueConstraint("name", "version"),)
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text)
    parameters: Mapped[dict] = mapped_column(JSONB, server_default="{}")


class Bot(Base):
    __tablename__ = "bots"
    __table_args__ = (
        UniqueConstraint("account_id", "name"),
        UniqueConstraint("account_id", "id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    name: Mapped[str] = mapped_column(Text)
    code_version: Mapped[str | None] = mapped_column(Text)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(TIME)


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint("account_id", "trade_key"),
        UniqueConstraint("account_id", "id"),
        ForeignKeyConstraint(["account_id", "bot_id"], ["bots.account_id", "bots.id"]),
        CheckConstraint("side IN ('LONG','SHORT')"),
        CheckConstraint("quantity_unit IN ('BASE','CONTRACT','LOT')"),
        CheckConstraint("contract_size > 0"),
        CheckConstraint("initial_risk_amount > 0"),
        CheckConstraint(
            "(status='OPEN' AND closed_at IS NULL) OR (status='CLOSED' AND closed_at >= opened_at)"
        ),
        Index("ix_trades_account_closed", "account_id", "closed_at"),
        Index("ix_trades_strategy_closed", "strategy_id", "closed_at"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    bot_id: Mapped[int] = mapped_column(BigInteger)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"))
    trade_key: Mapped[str] = mapped_column(Text)
    broker_position_ref: Mapped[str | None] = mapped_column(Text)
    symbol: Mapped[str] = mapped_column(Text)
    side: Mapped[str] = mapped_column(Text)
    quantity_unit: Mapped[str] = mapped_column(Text)
    contract_size: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(Text, server_default="OPEN")
    opened_at: Mapped[datetime] = mapped_column(TIME)
    closed_at: Mapped[datetime | None] = mapped_column(TIME)
    initial_sl: Mapped[Decimal | None] = mapped_column(MONEY)
    initial_tp: Mapped[Decimal | None] = mapped_column(MONEY)
    initial_risk_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    exit_reason: Mapped[str | None] = mapped_column(Text)


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (
        UniqueConstraint("account_id", "execution_key"),
        ForeignKeyConstraint(
            ["account_id", "trade_id"], ["trades.account_id", "trades.id"]
        ),
        CheckConstraint("role IN ('ENTRY','EXIT')"),
        CheckConstraint("price > 0"),
        CheckConstraint("quantity > 0"),
        Index("ix_executions_trade_time", "trade_id", "executed_at"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    trade_id: Mapped[int] = mapped_column(BigInteger)
    execution_key: Mapped[str] = mapped_column(Text)
    order_ref: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime] = mapped_column(TIME)
    role: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(MONEY)
    quantity: Mapped[Decimal] = mapped_column(MONEY)


class CashLedger(Base):
    __tablename__ = "cash_ledger"
    __table_args__ = (
        UniqueConstraint("account_id", "entry_key"),
        ForeignKeyConstraint(
            ["account_id", "trade_id"], ["trades.account_id", "trades.id"]
        ),
        CheckConstraint(
            "kind IN ('REALIZED_PNL','COMMISSION','FUNDING','SWAP','FEE','DEPOSIT','WITHDRAWAL','ADJUSTMENT')"
        ),
        CheckConstraint("fx_to_account > 0"),
        CheckConstraint(
            "(kind='DEPOSIT' AND amount_account>0) OR (kind='WITHDRAWAL' AND amount_account<0) OR kind NOT IN ('DEPOSIT','WITHDRAWAL')"
        ),
        Index("ix_ledger_account_time", "account_id", "occurred_at"),
        Index("ix_ledger_trade", "trade_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    trade_id: Mapped[int | None] = mapped_column(BigInteger)
    entry_key: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(TIME)
    kind: Mapped[str] = mapped_column(Text)
    amount_native: Mapped[Decimal] = mapped_column(MONEY)
    native_currency: Mapped[str] = mapped_column(Text)
    fx_to_account: Mapped[Decimal] = mapped_column(MONEY)
    amount_account: Mapped[Decimal] = mapped_column(MONEY)
    conversion_at: Mapped[datetime] = mapped_column(TIME)
    conversion_source: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(Text)


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"
    __table_args__ = (
        UniqueConstraint("account_id", "snapshot_key"),
        UniqueConstraint("account_id", "observed_at"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    snapshot_key: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(TIME)
    received_at: Mapped[datetime] = mapped_column(TIME, server_default=func.now())
    balance: Mapped[Decimal] = mapped_column(MONEY)
    unrealized_pnl: Mapped[Decimal] = mapped_column(MONEY)
    equity: Mapped[Decimal] = mapped_column(MONEY)
    used_margin: Mapped[Decimal | None] = mapped_column(MONEY)
    free_margin: Mapped[Decimal | None] = mapped_column(MONEY)
    source: Mapped[str] = mapped_column(Text)


class TradeSample(Base):
    __tablename__ = "trade_samples"
    __table_args__ = (
        UniqueConstraint("trade_id", "sample_key"),
        CheckConstraint("observed_price > 0"),
        CheckConstraint("stop_loss > 0"),
        CheckConstraint("take_profit > 0"),
        CheckConstraint("price_type IN ('LAST','MARK','BID','ASK','MID')"),
        Index("ix_samples_trade_time", "trade_id", "observed_at", "id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"))
    sample_key: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(TIME)
    observed_price: Mapped[Decimal] = mapped_column(MONEY)
    price_type: Mapped[str] = mapped_column(Text)
    stop_loss: Mapped[Decimal | None] = mapped_column(MONEY)
    take_profit: Mapped[Decimal | None] = mapped_column(MONEY)
    source: Mapped[str] = mapped_column(Text)


class ServerMetric(Base):
    __tablename__ = "server_metrics"
    __table_args__ = (
        CheckConstraint("cpu_pct BETWEEN 0 AND 100"),
        CheckConstraint("ram_pct BETWEEN 0 AND 100"),
        CheckConstraint("bot_memory_mb >= 0"),
        CheckConstraint("api_latency_ms >= 0"),
        CheckConstraint("db_latency_ms >= 0"),
        CheckConstraint("db_status IN ('OK','DEGRADED','DOWN','UNKNOWN')"),
        Index("ix_metrics_host_time", "host_ref", "observed_at"),
        Index("ix_metrics_bot_time", "bot_id", "observed_at"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    host_ref: Mapped[str] = mapped_column(Text)
    bot_id: Mapped[int | None] = mapped_column(ForeignKey("bots.id"))
    observed_at: Mapped[datetime] = mapped_column(TIME)
    cpu_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ram_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    bot_memory_mb: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    api_target: Mapped[str | None] = mapped_column(Text)
    api_latency_ms: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    db_latency_ms: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    db_status: Mapped[str] = mapped_column(Text)
