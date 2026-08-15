"""Tests for deadline calculation utilities."""

from datetime import UTC, date, datetime

from app.deadline_calc import (
    apply_occurrence_override,
    expense_window_start,
    get_checkpoint_occurrence,
    get_last_day_of_month,
    get_latest_due_occurrence,
    get_next_occurrence,
    get_next_payday,
    get_occurrences_in_window,
    get_previous_payday,
    income_window_start,
    is_occurrence_settled,
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


class TestGetPreviousPayday:
    """Tests for get_previous_payday function."""

    def test_payday_earlier_this_month(self):
        # Today is 26th, payday is 25th -> this month's payday opened the period
        assert get_previous_payday(date(2026, 3, 26), 25) == date(2026, 3, 25)

    def test_payday_still_ahead(self):
        # Today is 10th, payday is 25th -> the period opened last month
        assert get_previous_payday(date(2026, 3, 10), 25) == date(2026, 2, 25)

    def test_payday_is_today(self):
        # On payday the new period starts today (get_next_payday moves on too)
        assert get_previous_payday(date(2026, 3, 25), 25) == date(2026, 3, 25)

    def test_january_to_december(self):
        assert get_previous_payday(date(2026, 1, 10), 25) == date(2025, 12, 25)

    def test_payday_31_in_short_month(self):
        # Payday 31st, but the period opened on February's last day
        assert get_previous_payday(date(2026, 3, 1), 31) == date(2026, 2, 28)


class TestOccurrenceState:
    """Tests for the settled/pending state of a single occurrence.

    is_occurrence_settled decides whether the money for one occurrence has
    already moved, which is what lets a payment be corrected in either direction
    without touching the schedule.

    The second argument is the boundary the money totals use, not today: an
    occurrence before it has moved, one at or after it has not. For bills that
    boundary is tomorrow (they debit on their due day); for income it is today
    (pay is only assumed in the balance on payday itself).
    """

    class _Item:
        """Minimal stand-in with the scheduling fields the helpers read."""

        def __init__(self, **overrides):
            self.due_day = 15
            self.frequency_value = 1
            self.frequency_unit = "months"
            self.start_date = None
            self.end_date = None
            self.is_ephemeral = False
            self.archived_at = None
            self.settled_occurrence = None
            self.pending_occurrence = None
            self.__dict__.update(overrides)

    def test_upcoming_occurrence_is_not_settled(self):
        item = self._Item()
        assert not is_occurrence_settled(item, date(2026, 3, 15), date(2026, 3, 10))

    def test_past_occurrence_is_settled(self):
        item = self._Item()
        assert is_occurrence_settled(item, date(2026, 3, 15), date(2026, 3, 20))

    def test_bill_due_today_is_settled_but_pay_due_today_is_not(self):
        item = self._Item()
        # Bills: boundary is tomorrow, so today's debit counts as gone
        assert is_occurrence_settled(
            item, date(2026, 3, 15), expense_window_start(date(2026, 3, 15))
        )
        # Income: boundary is today, so today's pay is still expected
        assert not is_occurrence_settled(
            item, date(2026, 3, 15), income_window_start(date(2026, 3, 15), 25)
        )
        # ...except on payday, when it is assumed to be in the balance already
        assert is_occurrence_settled(
            item, date(2026, 3, 15), income_window_start(date(2026, 3, 15), 15)
        )

    def test_settled_mark_covers_an_upcoming_occurrence(self):
        item = self._Item(settled_occurrence=date(2026, 3, 15))
        assert is_occurrence_settled(item, date(2026, 3, 15), date(2026, 3, 10))
        # Only that one date: the next month's occurrence is still owed.
        assert not is_occurrence_settled(item, date(2026, 4, 15), date(2026, 3, 10))

    def test_pending_mark_covers_a_past_occurrence(self):
        item = self._Item(pending_occurrence=date(2026, 3, 15))
        assert not is_occurrence_settled(item, date(2026, 3, 15), date(2026, 3, 17))
        assert is_occurrence_settled(item, date(2026, 2, 15), date(2026, 3, 17))

    def test_next_occurrence(self):
        item = self._Item()
        assert get_next_occurrence(item, date(2026, 3, 10), date(2026, 2, 25)) == date(
            2026, 3, 15
        )
        # Once the boundary is past it, the next one is a month out
        assert get_next_occurrence(item, date(2026, 3, 16), date(2026, 2, 25)) == date(
            2026, 4, 15
        )

    def test_next_occurrence_of_a_yearly_item(self):
        item = self._Item(
            frequency_unit="years", start_date=date(2020, 9, 1), due_day=1
        )
        assert get_next_occurrence(item, date(2026, 3, 10), date(2026, 2, 25)) == date(
            2026, 9, 1
        )

    def test_next_occurrence_none_after_end_date(self):
        item = self._Item(end_date=date(2026, 2, 1))
        assert get_next_occurrence(item, date(2026, 3, 10), date(2026, 2, 25)) is None

    def test_latest_due_occurrence(self):
        item = self._Item()
        latest = get_latest_due_occurrence(item, date(2026, 3, 20), date(2026, 2, 25))
        assert latest == date(2026, 3, 15)

    def test_latest_due_occurrence_outside_the_period(self):
        item = self._Item()
        # The February occurrence came due before this period opened
        latest = get_latest_due_occurrence(item, date(2026, 3, 10), date(2026, 2, 25))
        assert latest is None

    def test_checkpoint_prefers_the_nearer_occurrence(self):
        item = self._Item()
        # Just after the due day the question is whether it landed
        assert get_checkpoint_occurrence(
            item, date(2026, 3, 17), date(2026, 2, 25)
        ) == date(2026, 3, 15)
        # Closer to the next one it becomes whether it was paid early
        assert get_checkpoint_occurrence(
            item, date(2026, 4, 10), date(2026, 3, 25)
        ) == date(2026, 4, 15)

    def test_checkpoint_follows_an_override(self):
        item = self._Item(settled_occurrence=date(2026, 4, 15))
        # An override always stays visible, so it can always be undone
        assert get_checkpoint_occurrence(
            item, date(2026, 3, 17), date(2026, 2, 25)
        ) == date(2026, 4, 15)


class TestApplyOccurrenceOverride:
    """Tests for recording that one occurrence has or hasn't moved yet."""

    def item(self, **overrides):
        return TestOccurrenceState._Item(**overrides)

    def test_settle_the_next_occurrence(self):
        item = self.item()
        applied = apply_occurrence_override(
            item, date(2026, 3, 15), True, date(2026, 3, 10), date(2026, 2, 25)
        )
        assert applied
        assert item.settled_occurrence == date(2026, 3, 15)
        assert item.pending_occurrence is None

    def test_unsettle_the_next_occurrence(self):
        item = self.item(settled_occurrence=date(2026, 3, 15))
        applied = apply_occurrence_override(
            item, date(2026, 3, 15), False, date(2026, 3, 10), date(2026, 2, 25)
        )
        assert applied
        assert item.settled_occurrence is None

    def test_flag_the_last_due_occurrence_as_pending(self):
        item = self.item()
        applied = apply_occurrence_override(
            item, date(2026, 3, 15), False, date(2026, 3, 17), date(2026, 2, 25)
        )
        assert applied
        assert item.pending_occurrence == date(2026, 3, 15)

    def test_settling_a_due_occurrence_clears_both_marks(self):
        item = self.item(
            settled_occurrence=date(2026, 3, 15), pending_occurrence=date(2026, 3, 15)
        )
        applied = apply_occurrence_override(
            item, date(2026, 3, 15), True, date(2026, 3, 17), date(2026, 2, 25)
        )
        assert applied
        assert item.pending_occurrence is None
        assert item.settled_occurrence is None

    def test_a_later_occurrence_is_rejected(self):
        item = self.item()
        applied = apply_occurrence_override(
            item, date(2026, 4, 15), True, date(2026, 3, 10), date(2026, 2, 25)
        )
        assert not applied
        assert item.settled_occurrence is None

    def test_a_date_that_is_not_an_occurrence_is_rejected(self):
        item = self.item()
        applied = apply_occurrence_override(
            item, date(2026, 3, 16), True, date(2026, 3, 10), date(2026, 2, 25)
        )
        assert not applied
        assert item.settled_occurrence is None


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

    def test_quarterly_anchored_to_start_date(self):
        # Every 3 months on the 23rd, starting June 23. Over a full year the
        # cadence must stay June/Sep/Dec, anchored to start_date — not to the
        # window's first month.
        occurrences = get_occurrences_in_window(
            due_day=23,
            frequency_value=3,
            frequency_unit="months",
            start_date=date(2026, 6, 23),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 1, 1),
            window_end=date(2027, 1, 1),
        )
        assert occurrences == [
            date(2026, 6, 23),
            date(2026, 9, 23),
            date(2026, 12, 23),
        ]

    def test_quarterly_off_phase_window_is_empty(self):
        # A quarterly bill anchored to June must NOT appear in a Jul-Aug window
        # (the regression: it used to re-anchor to the window's month and show
        # July 23).
        occurrences = get_occurrences_in_window(
            due_day=23,
            frequency_value=3,
            frequency_unit="months",
            start_date=date(2026, 6, 23),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 7, 1),
            window_end=date(2026, 9, 1),
        )
        assert occurrences == []

    def test_quarterly_in_phase_window(self):
        # The same quarterly bill DOES appear in a window containing September.
        occurrences = get_occurrences_in_window(
            due_day=23,
            frequency_value=3,
            frequency_unit="months",
            start_date=date(2026, 6, 23),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 9, 1),
            window_end=date(2026, 10, 1),
        )
        assert occurrences == [date(2026, 9, 23)]

    def test_quarterly_start_date_in_past(self):
        # Setting the start date backwards (March) keeps the Mar/Jun/Sep/Dec
        # cadence anchored to that month.
        occurrences = get_occurrences_in_window(
            due_day=23,
            frequency_value=3,
            frequency_unit="months",
            start_date=date(2026, 3, 23),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 1, 1),
            window_end=date(2027, 1, 1),
        )
        assert occurrences == [
            date(2026, 3, 23),
            date(2026, 6, 23),
            date(2026, 9, 23),
            date(2026, 12, 23),
        ]

    def test_every_two_years_anchored_to_start_year(self):
        # Every 2 years on March 15, starting 2024. Phase must be anchored to
        # 2024 (2026/2028/2030), not to the window's first year.
        occurrences = get_occurrences_in_window(
            due_day=15,
            frequency_value=2,
            frequency_unit="years",
            start_date=date(2024, 3, 15),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2025, 1, 1),
            window_end=date(2030, 12, 31),
        )
        assert occurrences == [
            date(2026, 3, 15),
            date(2028, 3, 15),
            date(2030, 3, 15),
        ]

    def test_weekly(self):
        # Weekly on Mondays (let's say 3rd is Monday), window 2 weeks
        # window_end is exclusive, so use 18th to include the 17th
        occurrences = get_occurrences_in_window(
            due_day=3,
            frequency_value=1,
            frequency_unit="weeks",
            start_date=date(2026, 3, 3),  # First occurrence
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 3, 3),
            window_end=date(2026, 3, 18),
        )
        assert occurrences == [date(2026, 3, 3), date(2026, 3, 10), date(2026, 3, 17)]

    def test_biweekly(self):
        # Every 2 weeks from March 3rd
        # window_end is exclusive, so use April 1st to include March 31st
        occurrences = get_occurrences_in_window(
            due_day=3,
            frequency_value=2,
            frequency_unit="weeks",
            start_date=date(2026, 3, 3),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 3, 1),
            window_end=date(2026, 4, 1),
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

    def test_ephemeral_no_start_date_uses_due_day(self):
        # One-time item without start_date should use due_day of current month
        # window_end is exclusive, so use 14th to include the 13th
        occurrences = get_occurrences_in_window(
            due_day=13,
            frequency_value=1,
            frequency_unit="months",
            start_date=None,
            end_date=None,
            is_ephemeral=True,
            archived_at=None,
            window_start=date(2026, 3, 10),
            window_end=date(2026, 3, 14),
        )
        assert occurrences == [date(2026, 3, 13)]

    def test_ephemeral_no_start_date_outside_window(self):
        # One-time item without start_date, but due_day already passed
        occurrences = get_occurrences_in_window(
            due_day=5,
            frequency_value=1,
            frequency_unit="months",
            start_date=None,
            end_date=None,
            is_ephemeral=True,
            archived_at=None,
            window_start=date(2026, 3, 10),
            window_end=date(2026, 3, 25),
        )
        assert occurrences == []  # due_day=5 is before window_start=10

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
        # window_end is exclusive, so use 11th to include the 10th
        occurrences = get_occurrences_in_window(
            due_day=1,
            frequency_value=3,
            frequency_unit="days",
            start_date=date(2026, 3, 1),
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 3, 1),
            window_end=date(2026, 3, 11),
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
        # window_end is exclusive, so use March 1st to include Feb 28th
        occurrences = get_occurrences_in_window(
            due_day=31,
            frequency_value=1,
            frequency_unit="months",
            start_date=None,
            end_date=None,
            is_ephemeral=False,
            archived_at=None,
            window_start=date(2026, 2, 1),
            window_end=date(2026, 3, 1),
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
