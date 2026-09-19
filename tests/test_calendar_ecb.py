"""Parser EBC na syntetycznym HTML o układzie ecb.europa.eu."""
import datetime as dt

import pytest

from src.data.calendar_ecb import decision_releases, meeting_times_utc

UTC = dt.timezone.utc


def index(items) -> str:
    return "<dl>" + "".join(
        f'<dt isoDate="x">{d}</dt><dd><div class="title"><a href="{href}">{title}</a></div>'
        f'<div>English</div></dd>' for d, href, title in items) + "</dl>"


def release(text: str) -> str:
    return f"<main><h1>Monetary policy decisions</h1><p>{text}</p></main>"


def test_only_decision_press_releases_are_listed():
    html = index([
        ("15 December 2022", "/press/pr/date/2022/html/ecb.mp221215~f.en.html", "Monetary policy decisions"),
        ("19 January 2023", "/press/accounts/2023/html/ecb.mg230119~e.en.html", "Meeting of 14-15 December 2022"),
        ("15 June 2022", "/press/pr/date/2022/html/ecb.pr220615~2.en.html",
         "Statement after the ad hoc meeting of the ECB Governing Council"),
    ])
    assert decision_releases(html) == [
        (dt.date(2022, 12, 15), "https://www.ecb.europa.eu/press/pr/date/2022/html/ecb.mp221215~f.en.html")]


@pytest.mark.parametrize("day, text, decision, conf", [
    # zima: CET = UTC+1
    (dt.date(2016, 3, 10), "a press conference starting at 14:30 CET today.",
     dt.datetime(2016, 3, 10, 12, 45), dt.datetime(2016, 3, 10, 13, 30)),
    # lato: „CET” w komunikacie = czas lokalny Frankfurtu (CEST, UTC+2)
    (dt.date(2016, 9, 8), "a press conference starting at 14:30 CET today.",
     dt.datetime(2016, 9, 8, 11, 45), dt.datetime(2016, 9, 8, 12, 30)),
    # po ecb.pr220627: 14:15 / 14:45
    (dt.date(2022, 7, 21), "a press conference starting at 14:45 CET today.",
     dt.datetime(2022, 7, 21, 12, 15), dt.datetime(2022, 7, 21, 12, 45)),
])
def test_times_follow_the_conference_stated_in_each_release(day, text, decision, conf):
    assert meeting_times_utc(release(text), day, "x") == (decision.replace(tzinfo=UTC),
                                                          conf.replace(tzinfo=UTC))


def test_release_without_press_conference_is_not_a_scheduled_meeting():
    assert meeting_times_utc(release("The Governing Council decided today."),
                             dt.date(2020, 3, 18), "x") is None


def test_unknown_conference_time_has_no_source_for_decision_time():
    with pytest.raises(ValueError, match="brak źródła"):
        meeting_times_utc(release("press conference starting at 15:00 CET today"),
                          dt.date(2026, 1, 1), "x")
