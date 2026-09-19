"""Parser Bank of Canada na syntetycznym HTML o układzie bankofcanada.ca."""
import datetime as dt

import pytest

from src.data.calendar_boc import listing_links, schedule_dates, scheduled_times_utc

UTC = dt.timezone.utc
B = "https://www.bankofcanada.ca"


def release(text: str) -> str:
    return (f"<html><script>var x = 'Wednesday, May 1 2099';</script><main>"
            f"<p>Ottawa, Ontario July 15, 2015</p><p>{text}</p></main></html>")


SCHED_2016 = release(
    "The Bank of Canada today published its 2016 schedule. The scheduled announcement dates "
    "from September 2015 through December 2015 are reconfirmed as follows: Wednesday 9 "
    "September Wednesday 2 December The scheduled announcement dates for 2016 are the "
    "following: Wednesday 20 January* Wednesday 7 December *Monetary Policy Report published "
    "All rate announcements will be made at 10:00 (ET), and the MPR will continue. "
    "Business Outlook Survey: Wednesday, April 6 at 10:30 (ET).")

# Układ odwrotny (rok nowy przed potwierdzeniem) i zmiana godziny w trakcie roku.
SCHED_2025 = release(
    "The Bank of Canada today published its 2025 schedule. The scheduled dates for the "
    "interest rate announcements for 2025 are as follows: Wednesday, January 29 The scheduled "
    "dates for the interest rate announcements from September 2024 through December 2024 are "
    "reconfirmed as follows: Wednesday, September 4 All interest rate announcements will take "
    "place at 09:45 (ET), and the Monetary Policy Report will be published concurrently.")


def test_listing_separates_decisions_and_schedules():
    html = (f'<a href="{B}/2016/01/fad-press-release-2016-01-20/">x</a>'
            f'<a href="{B}/2015/07/boc-2016-schedule-fad-mpr-releases/">y</a>'
            f'<a href="{B}/2016/02/bank-canada-unveils-note/">z</a>')
    decisions, schedules = listing_links(html)
    assert decisions == {dt.date(2016, 1, 20): f"{B}/2016/01/fad-press-release-2016-01-20/"}
    assert schedules == {f"{B}/2015/07/boc-2016-schedule-fad-mpr-releases/": (2015, 7)}


def test_schedule_dates_take_year_from_preceding_text_and_stop_at_time_sentence():
    dates, at = schedule_dates(SCHED_2016, "x")
    assert dates == [dt.date(2015, 9, 9), dt.date(2015, 12, 2),
                     dt.date(2016, 1, 20), dt.date(2016, 12, 7)]
    assert at == dt.time(10, 0)
    dates, at = schedule_dates(SCHED_2025, "x")
    assert dates == [dt.date(2025, 1, 29), dt.date(2024, 9, 4)]
    assert at == dt.time(9, 45)


def test_pending_review_phrase_gives_current_time():
    html = release("The Bank of Canada today published. for 2021 are as follows: Wednesday, "
                   "January 20 The Bank is also reviewing the publication time of its interest "
                   "rate announcements, which is currently 10:00 (ET).")
    assert schedule_dates(html, "x") == ([dt.date(2021, 1, 20)], dt.time(10, 0))


def test_schedule_without_time_is_an_error():
    with pytest.raises(ValueError, match="nie zgaduję"):
        schedule_dates(release("The Bank of Canada today published: Wednesday, January 20"), "x")


def fad(*days):
    return {d: f"{B}/{d:%Y/%m}/fad-press-release-{d:%Y-%m-%d}/" for d in days}


def test_latest_schedule_sets_the_time_and_dst_applies():
    schedules = [
        ((2023, 7), [dt.date(2024, 1, 24), dt.date(2024, 9, 4)], dt.time(10, 0), "a"),
        ((2024, 8), [dt.date(2024, 9, 4)], dt.time(9, 45), "b"),
    ]
    decisions = fad(dt.date(2024, 1, 24), dt.date(2024, 9, 4), dt.date(2024, 3, 13))
    got = scheduled_times_utc(schedules, decisions)
    assert [t for t, _ in got] == [
        dt.datetime(2024, 1, 24, 15, 0, tzinfo=UTC),     # 10:00 EST
        dt.datetime(2024, 9, 4, 13, 45, tzinfo=UTC),     # 09:45 EDT, z nowszego harmonogramu
    ]                                                    # 13.03 — spoza harmonogramu: pominięta


def test_scheduled_date_without_decision_release_is_an_error():
    schedules = [((2015, 7), [dt.date(2016, 1, 20), dt.date(2016, 3, 9)], dt.time(10, 0), "a")]
    with pytest.raises(ValueError, match="bez komunikatu"):
        scheduled_times_utc(schedules, fad(dt.date(2016, 1, 20), dt.date(2016, 4, 13)))
