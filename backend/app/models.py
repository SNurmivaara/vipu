from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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
    is_deduction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

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
            "is_deduction": self.is_deduction,
        }

    def calculate_net(self, default_tax_percentage: Decimal) -> Decimal:
        """Calculate net income after taxes or deductions.

        For deductions (is_deduction=True):
            Uses tax_percentage as deduction rate.
            net = -gross * tax_percentage/100
            Example: 280€ lunch benefit @ 75% = -210€ (deducted from pay)

        For regular taxed income (is_taxed=True):
            net = gross * (1 - default_tax_percentage/100)

        For untaxed income (is_taxed=False):
            net = gross
        """
        if self.is_deduction:
            # Deduction uses its own tax_percentage as deduction rate
            rate = (
                self.tax_percentage if self.tax_percentage is not None else Decimal(0)
            )
            return -self.gross_amount * rate / 100

        if not self.is_taxed:
            return self.gross_amount

        # Regular taxed income uses default tax rate
        return self.gross_amount * (1 - default_tax_percentage / 100)


class ExpenseItem(Base):
    """Monthly expense or savings goal."""

    __tablename__ = "expense_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    is_savings_goal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "amount": float(self.amount),
            "is_savings_goal": self.is_savings_goal,
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


class NetWorthCategory(Base):
    """User-defined net worth category (asset or liability type)."""

    __tablename__ = "networth_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "asset" or "liability"
    category_group: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "cash", "investment", "crypto", "property", "loan", "credit"
    is_personal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )  # True = personal, False = company
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    # Relationships
    entries: Mapped[list["NetWorthEntry"]] = relationship(
        "NetWorthEntry", back_populates="category"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "category_type": self.category_type,
            "category_group": self.category_group,
            "is_personal": self.is_personal,
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat(),
        }


class NetWorthSnapshot(Base):
    """Monthly net worth snapshot for tracking wealth over time."""

    __tablename__ = "networth_snapshots"
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_networth_year_month"),
        Index("ix_networth_year_month", "year", "month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    # Calculated totals (stored for historical record)
    total_assets: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    total_liabilities: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    net_worth: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    change_from_previous: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    personal_wealth: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    company_wealth: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )

    # Relationships
    entries: Mapped[list["NetWorthEntry"]] = relationship(
        "NetWorthEntry",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="NetWorthEntry.id",
    )

    def calculate_totals(self, previous_net_worth: Decimal | None = None) -> None:
        """Calculate all totals from entries.

        Must be called after entries are attached to the snapshot.
        """
        zero = Decimal(0)

        # Calculate totals from entries
        self.total_assets = zero
        self.total_liabilities = zero
        self.personal_wealth = zero
        self.company_wealth = zero

        for entry in self.entries:
            amount = entry.amount if entry.amount is not None else zero
            category = entry.category

            if category.category_type == "asset":
                self.total_assets += amount
                if category.is_personal:
                    self.personal_wealth += amount
                else:
                    self.company_wealth += amount
            else:  # liability
                self.total_liabilities += amount
                if category.is_personal:
                    self.personal_wealth += amount
                # Note: liabilities don't count toward company_wealth

        # Net worth = assets + liabilities (liabilities are negative)
        self.net_worth = self.total_assets + self.total_liabilities

        # Change from previous month
        if previous_net_worth is not None:
            self.change_from_previous = self.net_worth - previous_net_worth
        else:
            self.change_from_previous = zero

    def to_dict(self, include_entries: bool = True) -> dict:
        """Convert to dictionary."""

        def to_float(val: Decimal | None) -> float:
            return float(val) if val is not None else 0.0

        result: dict = {
            "id": self.id,
            "month": self.month,
            "year": self.year,
            "timestamp": self.timestamp.isoformat(),
            "total_assets": to_float(self.total_assets),
            "total_liabilities": to_float(self.total_liabilities),
            "net_worth": to_float(self.net_worth),
            "change_from_previous": to_float(self.change_from_previous),
            "personal_wealth": to_float(self.personal_wealth),
            "company_wealth": to_float(self.company_wealth),
        }

        if include_entries:
            result["entries"] = [e.to_dict() for e in self.entries]

            # Calculate group totals and percentages
            zero = Decimal(0)
            group_totals: dict[str, Decimal] = {}
            for entry in self.entries:
                if entry.category.category_type == "asset":
                    group = entry.category.category_group
                    amount = entry.amount if entry.amount is not None else zero
                    group_totals[group] = group_totals.get(group, zero) + amount

            result["by_group"] = {k: float(v) for k, v in group_totals.items()}

            # Percentages (avoid division by zero)
            total_assets = self.total_assets if self.total_assets else zero
            if total_assets > 0:
                result["percentages"] = {
                    f"{k}_pct": round(float(v / total_assets * 100), 2)
                    for k, v in group_totals.items()
                }
            else:
                result["percentages"] = {}

        return result


class NetWorthEntry(Base):
    """Individual entry in a net worth snapshot."""

    __tablename__ = "networth_entries"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "category_id", name="uq_entry_snapshot_category"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("networth_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("networth_categories.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    # Relationships
    snapshot: Mapped["NetWorthSnapshot"] = relationship(
        "NetWorthSnapshot", back_populates="entries"
    )
    category: Mapped["NetWorthCategory"] = relationship(
        "NetWorthCategory", back_populates="entries"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "category_id": self.category_id,
            "category": self.category.to_dict() if self.category else None,
            "amount": float(self.amount) if self.amount is not None else 0.0,
        }
