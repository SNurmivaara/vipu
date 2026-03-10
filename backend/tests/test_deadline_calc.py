"""Tests for deadline calculation utilities."""

from datetime import UTC, date, datetime

from app.deadline_calc import (
    get_last_day_of_month,
    get_next_payday,
    get_occurrences_in_window,
    normalize_day,
)


class TestGetLastDayOfMonth:
    """Tests for get_last_day_of_month function."""

    def test_january(self):
        assert get_last_day_of_month(2026, 1) == 31

    def test_february_non_leap(self):
        assert get_last_day_of_month(2025, 2) == 28

    def test_february_leap(self):
        assert get_last_day_of_month(2024, 2) == 29

    def test_april(self):
        assert get_last_day_of_month(2026, 4) == 30


class TestNormalizeDay:
    """Tests for normalize_day function."""

    def test_normal_day(self):
        assert normalize_day(15, 2026, 3) == 15

    def test_day_31_in_30_day_month(self):
        assert normalize_day(31, 2026, 4) == 30

    def test_day_31_in_february(self):
        assert normalize_day(31, 2026, 2) == 28

    def test_day_30_in_february_leap(self):
        assert normalize_day(30, 2024, 2) == 29


class TestGetNextPayday:
    """Tests for get_next_payday function."""

    def test_payday_later_this_month(self):
        # Today is 10th, payday is 25th -> payday this month
        today = date(2026, 3, 10)
        result = get_next_payday(today, 25)
        assert result == date(2026, 3, 25)

    def test_payday_already_passed(self):
        # Today is 26th, payday is 25th -> payday next month
        today = date(2026, 3, 26)
        result = get_next_payday(today, 25)
        assert result == date(2026, 4, 25)

    def test_payday_is_today(self):
        # Today is payday -> next month
        today = date(2026, 3, 25)
        result = get_next_payday(today, 25)
        assert result == date(2026, 4, 25)

    def test_payday_december_to_january(self):
        # December 26th, payday 25th -> January next year
        today = date(2026, 12, 26)
        result = get_next_payday(today, 25)
        assert result == date(2027, 1, 25)

    def test_payday_31_in_short_month(self):
        # Payday 31st, but April only has 30 days
        today = date(2026, 4, 1)
        result = get_next_payday(today, 31)
        assert result == date(2026, 4, 30)

    def test_payday_31_next_month_february(self):
        # January 31st, payday 31st -> February 28th
        today = date(2026, 1, 31)
        result = get_next_payday(today, 31)
        assert result == date(2026, 2, 28)


class TestGetOccurrencesInWindow:
    """Tests for get_occurrences_in_window function."""

    def test_monthly_single_occurrence(self):
        # Monthly on 15th, window is March 1-31
        occurrences = get_occurrences_in_window(
            due_day=15,
            frequency_value=1,
            frequency_unit="months",
            start_date=None,
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 3, 1),
            window_end=date(2026, 3, 31),
        )
        assert occurrences == [date(2026, 3, 15)]

    def test_monthly_spans_two_months(self):
        # Monthly on 15th, window spans March 10 to April 20
        occurrences = get_occurrences_in_window(
            due_day=15,
            frequency_value=1,
            frequency_unit="months",
            start_date=None,
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 3, 10),
            window_end=date(2026, 4, 20),
        )
        assert occurrences == [date(2026, 3, 15), date(2026, 4, 15)]

    def test_bimonthly(self):
        # Every 2 months on 1st, window spans 6 months
        occurrences = get_occurrences_in_window(
            due_day=1,
            frequency_value=2,
            frequency_unit="months",
            start_date=None,
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 1, 1),
            window_end=date(2026, 6, 30),
        )
        assert occurrences == [date(2026, 1, 1), date(2026, 3, 1), date(2026, 5, 1)]

    def test_weekly(self):
        # Weekly on Mondays (let's say 3rd is Monday), window 2 weeks
        occurrences = get_occurrences_in_window(
            due_day=3,
            frequency_value=1,
            frequency_unit="weeks",
            start_date=date(2026, 3, 3),  # First occurrence
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 3, 3),
            window_end=date(2026, 3, 17),
        )
        assert occurrences == [date(2026, 3, 3), date(2026, 3, 10), date(2026, 3, 17)]

    def test_biweekly(self):
        # Every 2 weeks from March 3rd
        occurrences = get_occurrences_in_window(
            due_day=3,
            frequency_value=2,
            frequency_unit="weeks",
            start_date=date(2026, 3, 3),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 3, 1),
            window_end=date(2026, 3, 31),
        )
        assert occurrences == [date(2026, 3, 3), date(2026, 3, 17), date(2026, 3, 31)]

    def test_yearly(self):
        # Yearly on March 15th
        occurrences = get_occurrences_in_window(
            due_day=15,
            frequency_value=1,
            frequency_unit="years",
            start_date=date(2024, 3, 15),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2024, 1, 1),
            window_end=date(2026, 12, 31),
        )
        assert occurrences == [date(2024, 3, 15), date(2025, 3, 15), date(2026, 3, 15)]

    def test_ephemeral_in_window(self):
        # One-time payment on March 15th
        occurrences = get_occurrences_in_window(
            due_day=15,
            frequency_value=1,
            frequency_unit="months",
            start_date=date(2026, 3, 15),
            end_date=None,
            is_ephemeral=True,
            archived_at=None,
            window_start=date(2026, 3, 1),
            window_end=date(2026, 3, 31),
        )
        assert occurrences == [date(2026, 3, 15)]

    def test_ephemeral_outside_window(self):
        # One-time payment on April 15th, window is March
        occurrences = get_occurrences_in_window(
            due_day=15,
            frequency_value=1,
            frequency_unit="months",
            start_date=date(2026, 4, 15),
            end_date=None,
            is_ephemeral=True,
            archived_at=None,
            window_start=date(2026, 3, 1),
            window_end=date(2026, 3, 31),
        )
        assert occurrences == []

    def test_archived_item(self):
        # Archived items should return no occurrences
        occurrences = get_occurrences_in_window(
            due_day=15,
            frequency_value=1,
            frequency_unit="months",
            start_date=None,
            end_date=None,
            is_ephemeral=False,
            archived_at=datetime(2026, 2, 1, tzinfo=UTC),
            window_start=date(2026, 3, 1),
            window_end=date(2026, 3, 31),
        )
        assert occurrences == []

    def test_start_date_after_window(self):
        # Item starts in April, window is March
        occurrences = get_occurrences_in_window(
            due_day=15,
            frequency_value=1,
            frequency_unit="months",
            start_date=date(2026, 4, 1),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 3, 1),
            window_end=date(2026, 3, 31),
        )
        assert occurrences == []

    def test_end_date_before_window(self):
        # Item ends in February, window is March
        occurrences = get_occurrences_in_window(
            due_day=15,
            frequency_value=1,
            frequency_unit="months",
            start_date=None,
            end_date=date(2026, 2, 28),
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 3, 1),
            window_end=date(2026, 3, 31),
        )
        assert occurrences == []

    def test_start_date_within_window(self):
        # Monthly starting March 10th, window is March 1-31
        occurrences = get_occurrences_in_window(
            due_day=15,
            frequency_value=1,
            frequency_unit="months",
            start_date=date(2026, 3, 10),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 3, 1),
            window_end=date(2026, 3, 31),
        )
        # March 15th is after start_date (March 10th), so it counts
        assert occurrences == [date(2026, 3, 15)]

    def test_end_date_within_window(self):
        # Monthly on 15th, ends March 10th, window is March 1-31
        occurrences = get_occurrences_in_window(
            due_day=15,
            frequency_value=1,
            frequency_unit="months",
            start_date=None,
            end_date=date(2026, 3, 10),
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 3, 1),
            window_end=date(2026, 3, 31),
        )
        # March 15th is after end_date (March 10th), so it doesn't count
        assert occurrences == []

    def test_daily(self):
        # Every 3 days from March 1st
        occurrences = get_occurrences_in_window(
            due_day=1,
            frequency_value=3,
            frequency_unit="days",
            start_date=date(2026, 3, 1),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 3, 1),
            window_end=date(2026, 3, 10),
        )
        expected = [
            date(2026, 3, 1),
            date(2026, 3, 4),
            date(2026, 3, 7),
            date(2026, 3, 10),
        ]
        assert occurrences == expected

    def test_monthly_31st_normalized(self):
        # Monthly on 31st, February only has 28 days
        occurrences = get_occurrences_in_window(
            due_day=31,
            frequency_value=1,
            frequency_unit="months",
            start_date=None,
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 2, 1),
            window_end=date(2026, 2, 28),
        )
        assert occurrences == [date(2026, 2, 28)]


class TestBudgetCalculationScenario:
    """Integration-style tests for realistic budget scenarios."""

    def test_typical_month_scenario(self):
        """Test a typical scenario with payday on 25th."""
        today = date(2026, 3, 10)
        payday_day = 25
        next_payday = get_next_payday(today, payday_day)
        assert next_payday == date(2026, 3, 25)

        # Rent due on 1st (already passed)
        rent_occurrences = get_occurrences_in_window(
            due_day=1,
            frequency_value=1,
            frequency_unit="months",
            start_date=None,
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=today,
            window_end=next_payday,
        )
        assert rent_occurrences == []  # Already passed for this month

        # Utilities due on 15th (upcoming)
        utilities_occurrences = get_occurrences_in_window(
            due_day=15,
            frequency_value=1,
            frequency_unit="months",
            start_date=None,
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=today,
            window_end=next_payday,
        )
        assert utilities_occurrences == [date(2026, 3, 15)]

        # Weekly grocery budget
        grocery_occurrences = get_occurrences_in_window(
            due_day=10,
            frequency_value=1,
            frequency_unit="weeks",
            start_date=date(2026, 3, 10),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=today,
            window_end=next_payday,
        )
        # March 10, 17, 24 (all before 25th)
        expected = [date(2026, 3, 10), date(2026, 3, 17), date(2026, 3, 24)]
        assert grocery_occurrences == expected
