from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
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
    # Credit card payment due day (1-31, null means use full balance)
    payment_due_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "balance": float(self.balance),
            "is_credit": self.is_credit,
            "updated_at": self.updated_at.isoformat(),
            "payment_due_day": self.payment_due_day,
        }


class IncomeItem(Base):
    """Income source with deadline tracking."""

    __tablename__ = "income_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    is_taxed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tax_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_deduction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Deadline fields
    due_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    frequency_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    frequency_unit: Mapped[str] = mapped_column(
        String(20), nullable=False, default="months"
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_ephemeral: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Per-occurrence overrides of the "cleared on its due day" assumption, each
    # holding a single occurrence date so only that one occurrence moves — the
    # schedule and every later occurrence (and with them the forecast) stay put.
    # settled: an upcoming occurrence already received (paid ahead of a banking
    # holiday, say), so it is skipped. pending: an occurrence whose day has come
    # and gone without the money moving, so it still counts as owed/expected.
    settled_occurrence: Mapped[date | None] = mapped_column(Date, nullable=True)
    pending_occurrence: Mapped[date | None] = mapped_column(Date, nullable=True)

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
            "due_day": self.due_day,
            "frequency_value": self.frequency_value,
            "frequency_unit": self.frequency_unit,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_ephemeral": self.is_ephemeral,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "settled_occurrence": (
                self.settled_occurrence.isoformat() if self.settled_occurrence else None
            ),
            "pending_occurrence": (
                self.pending_occurrence.isoformat() if self.pending_occurrence else None
            ),
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
    """Expense or savings goal with deadline tracking."""

    __tablename__ = "expense_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    is_savings_goal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Deadline fields
    due_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    frequency_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    frequency_unit: Mapped[str] = mapped_column(
        String(20), nullable=False, default="months"
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_ephemeral: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Per-occurrence overrides of the "cleared on its due day" assumption — see
    # IncomeItem for the full note. settled: paid early, skip it. pending: due
    # day passed but the debit hasn't landed yet, so it still counts as owed.
    settled_occurrence: Mapped[date | None] = mapped_column(Date, nullable=True)
    pending_occurrence: Mapped[date | None] = mapped_column(Date, nullable=True)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "amount": float(self.amount),
            "is_savings_goal": self.is_savings_goal,
            "due_day": self.due_day,
            "frequency_value": self.frequency_value,
            "frequency_unit": self.frequency_unit,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_ephemeral": self.is_ephemeral,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "settled_occurrence": (
                self.settled_occurrence.isoformat() if self.settled_occurrence else None
            ),
            "pending_occurrence": (
                self.pending_occurrence.isoformat() if self.pending_occurrence else None
            ),
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
    # Payday day of month (1-31) - the rollover anchor for budget calculations
    payday_day: Mapped[int] = mapped_column(Integer, nullable=False, default=25)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "tax_percentage": float(self.tax_percentage),
            "updated_at": self.updated_at.isoformat(),
            "payday_day": self.payday_day,
        }


class ForecastingSettings(Base):
    """FIRE forecasting settings (singleton row)."""

    __tablename__ = "forecasting_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inflation_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("2.0")
    )
    safe_withdrawal_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("4.0")
    )
    current_age: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    target_retirement_age: Mapped[int] = mapped_column(
        Integer, nullable=False, default=65
    )
    monthly_savings_override: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True, default=None
    )
    annual_expenses_override: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True, default=None
    )
    # Pension (TyEL)
    pension_accrued_monthly: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True, default=None
    )
    pension_monthly_salary_override: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True, default=None
    )
    pension_accrual_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("1.5")
    )
    pension_full_age: Mapped[int] = mapped_column(Integer, nullable=False, default=68)
    pension_guarantee_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    pension_guarantee_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("990.0")
    )
    life_expectancy: Mapped[int] = mapped_column(Integer, nullable=False, default=95)
    # Tax. Retirement is funded from two taxed streams and the model charged
    # neither: selling to live on realises a capital gain, and a TyEL pension
    # is taxed as earned income.
    capital_gains_tax_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("30.0")
    )
    # Share of a sale that is taxable gain rather than returned capital. 60% is
    # what the 40% hankintameno-olettama leaves taxable on a holding of ten
    # years or more, so 30% x 60% = 18% of a withdrawal.
    taxable_gain_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("60.0")
    )
    # Effective rate on pension income, after the eläketulovähennys.
    pension_tax_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("15.0")
    )
    group_return_rates: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Asset group new savings are paid into. NULL spreads them across the mix,
    # which credits them at the portfolio average rather than where they go.
    contribution_group: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default=None
    )
    # Terms per liability category name, so each loan amortises on its own
    # rate and schedule: {"Home loan": {"rate_pct": 3.108, "schedule":
    # "annuity", "end_year": 2051, "end_month": 12}}. A loan states either a
    # fixed monthly_payment or a payoff date; the other follows from it.
    liability_terms: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Asset groups that stay in net worth but do not back the withdrawal, such
    # as an owner-occupied home.
    swr_excluded_groups: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "inflation_pct": float(self.inflation_pct),
            "safe_withdrawal_rate": float(self.safe_withdrawal_rate),
            "current_age": self.current_age,
            "target_retirement_age": self.target_retirement_age,
            "monthly_savings_override": (
                float(self.monthly_savings_override)
                if self.monthly_savings_override is not None
                else None
            ),
            "annual_expenses_override": (
                float(self.annual_expenses_override)
                if self.annual_expenses_override is not None
                else None
            ),
            "pension_accrued_monthly": (
                float(self.pension_accrued_monthly)
                if self.pension_accrued_monthly is not None
                else None
            ),
            "pension_monthly_salary_override": (
                float(self.pension_monthly_salary_override)
                if self.pension_monthly_salary_override is not None
                else None
            ),
            "pension_accrual_rate": float(self.pension_accrual_rate),
            "pension_full_age": self.pension_full_age,
            "pension_guarantee_enabled": self.pension_guarantee_enabled,
            "pension_guarantee_amount": float(self.pension_guarantee_amount),
            "life_expectancy": self.life_expectancy,
            "capital_gains_tax_pct": float(self.capital_gains_tax_pct),
            "taxable_gain_pct": float(self.taxable_gain_pct),
            "pension_tax_pct": float(self.pension_tax_pct),
            "group_return_rates": self.group_return_rates or {},
            "contribution_group": self.contribution_group,
            "liability_terms": self.liability_terms or {},
            "swr_excluded_groups": self.swr_excluded_groups or [],
            "updated_at": self.updated_at.isoformat(),
        }


class BudgetSnapshot(Base):
    """Point-in-time snapshot of budget state for tracking over time.

    Stores the total balance across all accounts and the net change
    from the previous snapshot. Individual account balances are stored
    in BudgetBalanceEntry for drill-down.
    """

    __tablename__ = "budget_snapshots"
    __table_args__ = (
        UniqueConstraint("date", name="uq_budget_snapshot_date"),
        Index("ix_budget_snapshots_date", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    # Sum of all account balances at snapshot time
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    # Net change in current_balance vs previous snapshot
    change_from_previous: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    entries: Mapped[list["BudgetBalanceEntry"]] = relationship(
        "BudgetBalanceEntry",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="BudgetBalanceEntry.id",
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "timestamp": self.timestamp.isoformat(),
            "current_balance": float(self.current_balance),
            "change_from_previous": float(self.change_from_previous),
            "notes": self.notes,
            "entries": [e.to_dict() for e in self.entries],
        }


class BudgetBalanceEntry(Base):
    """Individual account balance in a budget snapshot."""

    __tablename__ = "budget_balance_entries"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "account_id", name="uq_budget_entry_snapshot_account"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("budget_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    is_credit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    snapshot: Mapped["BudgetSnapshot"] = relationship(
        "BudgetSnapshot", back_populates="entries"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "account_name": self.account_name,
            "balance": float(self.balance),
            "is_credit": self.is_credit,
        }


class NetWorthGroup(Base):
    """User-defined group for categorizing net worth items."""

    __tablename__ = "networth_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "asset" or "liability"
    color: Mapped[str] = mapped_column(
        String(7), nullable=False, default="#6b7280"
    )  # Hex color for charts
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    # Relationships
    categories: Mapped[list["NetWorthCategory"]] = relationship(
        "NetWorthCategory", back_populates="group"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "group_type": self.group_type,
            "color": self.color,
            "display_order": self.display_order,
            "created_at": self.created_at.isoformat(),
        }


class NetWorthCategory(Base):
    """User-defined net worth category (asset or liability type)."""

    __tablename__ = "networth_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("networth_groups.id"), nullable=False
    )
    is_personal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )  # True = personal, False = company
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    # Relationships
    group: Mapped["NetWorthGroup"] = relationship(
        "NetWorthGroup", back_populates="categories"
    )
    entries: Mapped[list["NetWorthEntry"]] = relationship(
        "NetWorthEntry", back_populates="category"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "group_id": self.group_id,
            "group": self.group.to_dict() if self.group else None,
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
            group = category.group

            if group.group_type == "asset":
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

        # Month-over-month change as a percentage of the previous net worth.
        # 0 when there is no previous value to compare against.
        change = self.change_from_previous or Decimal(0)
        previous_net_worth = (self.net_worth or Decimal(0)) - change
        change_percent = (
            round(float(change / previous_net_worth * 100), 2)
            if previous_net_worth != 0
            else 0.0
        )

        result: dict = {
            "id": self.id,
            "month": self.month,
            "year": self.year,
            "timestamp": self.timestamp.isoformat(),
            "total_assets": to_float(self.total_assets),
            "total_liabilities": to_float(self.total_liabilities),
            "net_worth": to_float(self.net_worth),
            "change_from_previous": to_float(self.change_from_previous),
            "change_percent": change_percent,
            "personal_wealth": to_float(self.personal_wealth),
            "company_wealth": to_float(self.company_wealth),
        }

        if include_entries:
            result["entries"] = [e.to_dict() for e in self.entries]

            # Calculate group totals and percentages (for assets only)
            zero = Decimal(0)
            group_totals: dict[int, Decimal] = {}  # group_id -> total
            group_names: dict[int, str] = {}  # group_id -> name
            liability_totals: dict[int, Decimal] = {}
            # One entry per loan, since two loans in the same group rarely share
            # an interest rate or a maturity.
            loan_totals: dict[str, Decimal] = {}
            loan_groups: dict[str, str] = {}
            loan_order: dict[str, tuple[int, int]] = {}
            for entry in self.entries:
                group = entry.category.group
                amount = entry.amount if entry.amount is not None else zero
                if group.group_type == "asset":
                    group_totals[group.id] = group_totals.get(group.id, zero) + amount
                    group_names[group.id] = group.name
                else:
                    liability_totals[group.id] = (
                        liability_totals.get(group.id, zero) + amount
                    )
                    group_names[group.id] = group.name
                    name = entry.category.name
                    loan_totals[name] = loan_totals.get(name, zero) + amount
                    loan_groups[name] = group.name
                    loan_order[name] = (
                        group.display_order,
                        entry.category.display_order,
                    )

            result["by_group"] = {
                group_names[gid]: float(total) for gid, total in group_totals.items()
            }

            # Amounts owed, as positive magnitudes. Liability entries are stored
            # negative, but a forecast reads these as balances to pay down.
            result["liabilities_by_group"] = {
                group_names[gid]: abs(float(total))
                for gid, total in liability_totals.items()
            }

            # Same amounts, one level finer, so terms can be set per loan.
            # A cleared loan is left out: there is nothing to amortise.
            result["liabilities_by_category"] = {
                name: {
                    "amount": abs(float(loan_totals[name])),
                    "group": loan_groups[name],
                }
                for name in sorted(loan_totals, key=lambda n: loan_order[n])
                if loan_totals[name] < 0
            }

            # Percentages (avoid division by zero)
            total_assets = self.total_assets if self.total_assets else zero
            if total_assets > 0:
                result["percentages"] = {
                    f"{group_names[gid]}_pct": round(
                        float(total / total_assets * 100), 2
                    )
                    for gid, total in group_totals.items()
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


class Goal(Base):
    """Financial goal for tracking progress.

    Goal types:
    - net_worth: Track total net worth against a target (Wealth page)
    - savings_goal: Save up toward a target amount (roadmap step)
    - debt_payoff: Pay off a debt of target_value (roadmap step)

    Roadmap steps (savings_goal / debt_payoff) are ordered by priority and
    funded sequentially from the monthly budget surplus. Their progress comes
    from current_amount, or from the linked net worth category's latest
    snapshot balance when category_id is set.
    """

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    goal_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "net_worth", "savings_goal", "debt_payoff"
    target_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("networth_categories.id"), nullable=True
    )
    target_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Roadmap ordering: position in the sequential plan (null for net_worth goals)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Manual progress: amount saved / paid off so far (ignored when a category
    # is linked — the snapshot balance wins)
    current_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    # Relationships
    category: Mapped["NetWorthCategory | None"] = relationship("NetWorthCategory")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "goal_type": self.goal_type,
            "target_value": float(self.target_value),
            "category_id": self.category_id,
            "category": self.category.to_dict() if self.category else None,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "is_active": self.is_active,
            "priority": self.priority,
            "current_amount": (
                float(self.current_amount) if self.current_amount is not None else None
            ),
            "created_at": self.created_at.isoformat(),
        }
