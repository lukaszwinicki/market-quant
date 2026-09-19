"""Parser harmonogramu Statistics Bureau na syntetycznym XML o układzie e-stat."""
import datetime as dt

import pytest

from src.data.calendar_jp import decode, release_times_utc

UTC = dt.timezone.utc


def entry(year, month, day, hour=8, minute=30):
    return (f"<class_3 name=''><class_4 name=''><class_5 name=''>"
            f"<release_year>{year}</release_year><release_month>{month}</release_month>"
            f"<release_day>{day}</release_day><release_hour>{hour}</release_hour>"
            f"<release_minute>{minute}</release_minute>"
            f"</class_5></class_4></class_3>")


XML = ("<e-stat><os_code id='00200573'>"
       '<class_1 name="全国">'
       '<class_2 name="平成30年(2018年)1月分">' + entry(2018, 2, 23) + "</class_2>"
       '<class_2 name="平成29年(2017年)平均">' + entry(2018, 3, 2) + "</class_2>"
       '<class_2 name="2025年12月分">' + entry(2026, 1, 23) + "</class_2>"
       "</class_1>"
       '<class_1 name="東京都区部（中旬速報値）">'
       '<class_2 name="平成30年(2018年)2月分">' + entry(2018, 2, 27) + "</class_2>"
       "</class_1></os_code></e-stat>")


def test_only_monthly_national_releases():
    got = release_times_utc(XML, "x")
    assert got == {(2018, 1): dt.datetime(2018, 2, 22, 23, 30, tzinfo=UTC),   # 8:30 JST
                   (2025, 12): dt.datetime(2026, 1, 22, 23, 30, tzinfo=UTC)}


def test_key_is_reference_month_so_era_change_is_not_a_duplicate():
    heisei = XML.replace("平成30年(2018年)1月分", "平成31年(2019年)5月分")
    reiwa = XML.replace("平成30年(2018年)1月分", "令和元年(2019年)5月分")
    assert set(release_times_utc(heisei, "x")) == set(release_times_utc(reiwa, "x"))


def test_missing_series_is_an_error():
    with pytest.raises(ValueError, match="zmiana układu"):
        release_times_utc("<e-stat><class_1 name='東京都区部'></class_1></e-stat>", "x")


def test_utf16_schedule_is_decoded():
    assert decode(XML.encode("utf-16")) == XML
