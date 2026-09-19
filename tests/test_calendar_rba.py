"""Parser RBA na syntetycznym HTML o układzie rba.gov.au (kopie z archiwum)."""
import datetime as dt

import pytest

from src.data.calendar_rba import (
    announced_at, decision_dates, is_regular_meeting, scheduled_times,
)

UTC = dt.timezone.utc
B = "https://www.rba.gov.au"

DECISIONS_2020 = """
<p>Decisions regarding monetary policy were made by the Reserve Bank Board and explained in
a media release announcing the decision at 2.30 pm after each Board meeting.</p>
<ul class="list-articles">
  <li><a href="/media-releases/2020/mr-20-11.html">7 April 2020</a></li>
  <li><a href="/media-releases/2020/mr-20-08.html">19 March 2020</a></li>
  <li><a href="/media-releases/2020/mr-20-06.html">3 March 2020</a></li>
</ul>"""

TEXT_SCHEDULE = """<h2>Reserve Bank Board Meeting</h2>
<p>The Reserve Bank Board will meet on the following days, with a media release issued at
2.30 pm:</p><ul><li>Tuesday, 3 March</li><li>Tuesday, 7 April</li></ul>
<h2>Chart Pack</h2><p>The Chart Pack will be released at 11.30 am on:</p>
<ul><li>Wednesday, 4 March</li></ul>"""

LISTING_SCHEDULE = """<h3>February 2025</h3>
<p>Reserve Bank Board Meeting Monetary Policy Decision 17–18 February 2025</p>
<p>Monetary Policy Decision Statement Media Release 18 February 2025 2.30 pm AEDT</p>
<p>Media Conference Monetary Policy Decision 18 February 2025 3.30 pm AEDT</p>
<h3>May 2025</h3>
<p>Monetary Policy Decision Statement Media Release 20 May 2025 2.30 pm AEST</p>
<h3>grudzień 2024 — inny rok, pomijany</h3>
<p>Monetary Policy Decision Statement Media Release 10 December 2024 2.30 pm AEDT</p>"""


def test_decision_dates_and_announced_time():
    got = decision_dates(DECISIONS_2020, 2020, "x")
    assert got == {dt.date(2020, 3, 3): f"{B}/media-releases/2020/mr-20-06.html",
                   dt.date(2020, 3, 19): f"{B}/media-releases/2020/mr-20-08.html",
                   dt.date(2020, 4, 7): f"{B}/media-releases/2020/mr-20-11.html"}
    assert announced_at(DECISIONS_2020, "x") == dt.time(14, 30)


def test_text_schedule_gives_only_board_meetings_with_stated_time():
    assert scheduled_times(TEXT_SCHEDULE, 2020, "x") == {
        dt.date(2020, 3, 3): dt.datetime(2020, 3, 3, 3, 30, tzinfo=UTC),    # 14:30 AEDT
        dt.date(2020, 4, 7): dt.datetime(2020, 4, 7, 4, 30, tzinfo=UTC),    # 14:30 AEST
    }


def test_listing_schedule_keeps_the_year_and_checks_the_zone():
    assert scheduled_times(LISTING_SCHEDULE, 2025, "x") == {
        dt.date(2025, 2, 18): dt.datetime(2025, 2, 18, 3, 30, tzinfo=UTC),
        dt.date(2025, 5, 20): dt.datetime(2025, 5, 20, 4, 30, tzinfo=UTC),
    }


def test_wrong_zone_abbreviation_is_an_error():
    html = "Monetary Policy Decision Statement Media Release 20 May 2025 2.30 pm AEDT"
    with pytest.raises(ValueError, match="AEDT"):
        scheduled_times(html, 2025, "x")


def test_schedule_without_meetings_is_an_error():
    with pytest.raises(ValueError, match="nie zgaduję"):
        scheduled_times("<p>The Chart Pack will be released at 11.30 am</p>", 2020, "x")


def test_regular_meeting_phrase():
    assert is_regular_meeting("<p>At its meeting today, the Board decided to leave …</p>")
    assert not is_regular_meeting("<p>The coronavirus is first and foremost a public health "
                                  "issue …</p>")
