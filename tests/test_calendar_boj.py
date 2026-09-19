"""Parser Bank of Japan na syntetycznym tekście protokołu o układzie boj.or.jp."""
import datetime as dt

import pytest

from src.data.calendar_boj import BASE, adjournment_utc, is_unscheduled, minutes_links

UTC = dt.timezone.utc
P = "/en/mopo/mpmsche_minu"


def minutes(head: str, body: str = "II. Summary of Staff Reports") -> str:
    return ("Not to be released until 8:50 a.m. Japan Standard Time. Bank of Japan "
            f"Minutes of the Monetary Policy Meeting. A Monetary Policy Meeting of the Bank of "
            f"Japan Policy Board was held in the Head Office of the Bank of Japan in Tokyo "
            f"{head} Policy Board Members Present Mr. KURODA Haruhiko, Chairman. {body}")


def test_links_cover_pdf_and_html_minutes():
    html = (f'<a href="{P}/minu_2016/g161220.pdf">Meeting on December 19 and 20, 2016&nbsp;'
            f'[PDF&nbsp;91KB]</a>'
            f'<a href="{P}/minu_2018/g181220.htm">Meeting on December 19 and 20, 2018</a>'
            f'<a href="{P}/opinion_2018/opi181220.pdf">Summary of Opinions</a>')
    assert minutes_links(html) == [(dt.date(2016, 12, 20), f"{BASE}{P}/minu_2016/g161220.pdf"),
                                   (dt.date(2018, 12, 20), f"{BASE}{P}/minu_2018/g181220.htm")]


def test_time_is_the_end_of_the_last_meeting_day():
    head = ("on Thursday, January 28, 2016, from 2:00 p.m. to 3:46 p.m., and on Friday, "
            "January 29, from 9:00 a.m. to 12:31 p.m.1")
    assert adjournment_utc(minutes(head), dt.date(2016, 1, 29), "x") == \
        dt.datetime(2016, 1, 29, 3, 31, tzinfo=UTC)          # 12:31 JST


def test_space_before_comma_in_weekday_is_tolerated():
    head = ("on Wednesday , September 20, 2017, from 2:00 p.m. to 3:44 p.m., and on Thursday, "
            "September 21, from 9:00 a.m. to 11:44 a.m.1")
    assert adjournment_utc(minutes(head), dt.date(2017, 9, 21), "x") == \
        dt.datetime(2017, 9, 21, 2, 44, tzinfo=UTC)


def test_date_mismatch_is_an_error():
    head = "on Friday, January 29, 2016, from 9:00 a.m. to 12:31 p.m."
    with pytest.raises(ValueError, match="adres wskazuje"):
        adjournment_utc(minutes(head), dt.date(2016, 1, 28), "x")


def test_minutes_without_header_are_an_error():
    with pytest.raises(ValueError, match="nie zgaduję"):
        adjournment_utc("Minutes of the Monetary Policy Meeting", dt.date(2016, 1, 29), "x")


@pytest.mark.parametrize("body, unscheduled", [
    ("I. Remarks on the Purpose of This Unscheduled Monetary Policy Meeting", True),
    ("The chairman proposed that the March 18 and 19 meeting be brought forward.", True),
    ("A member commented on economic developments and the pace of purchases.", False),
])
def test_unscheduled_meetings_are_marked_in_the_text(body, unscheduled):
    head = "on Monday, March 16, 2020, from 12:00 p.m. to 1:59 p.m."
    assert is_unscheduled(minutes(head, body)) is unscheduled
