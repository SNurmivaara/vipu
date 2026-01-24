from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Account(Base):
    """Bank account or credit card."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    is_credit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "balance": float(self.balance),
            "is_credit": self.is_credit,
            "updated_at": self.updated_at.isoformat(),
        }


class IncomeItem(Base):
    """Monthly income source."""

    __tablename__ = "income_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    is_taxed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tax_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "gross_amount": float(self.gross_amount),
            "is_taxed": self.is_taxed,
            "tax_percentage": (
                float(self.tax_percentage) if self.tax_percentage is not None else None
            ),
        }

    def calculate_net(self, default_tax_percentage: Decimal) -> Decimal:
        """Calculate net income after taxes."""
        if not self.is_taxed:
            return self.gross_amount

        tax_rate = (
            self.tax_percentage
            if self.tax_percentage is not None
            else default_tax_percentage
        )
        return self.gross_amount * (1 - tax_rate / 100)


class ExpenseItem(Base):
    """Monthly expense."""

    __tablename__ = "expense_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "amount": float(self.amount),
        }


class BudgetSettings(Base):
    """Budget settings (singleton row)."""

    __tablename__ = "budget_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tax_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("25.0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "tax_percentage": float(self.tax_percentage),
            "updated_at": self.updated_at.isoformat(),
        }
