"""Finansowanie kohorty A: potrójna środa, kierunkowość, marża (ADR-035, ADR-037).

Wszystko na syntetyku z ręcznie policzoną odpowiedzią. Na prawdziwych
transakcjach nie wiadomo, ile swap „powinien" wynieść, więc test niczego
by nie dowodził.
"""
from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from src.data.rates import SCHEMA
from src.execution.financing import (
    ROLLOVER_UTC, apply_financing, financing_r, markup_from, markup_grid_from,
    refinanced, rollover_days,
)
from src.validation.cost_sensitivity import (
    markup_ladder, render_markup_markdown, repriced,
)

UTC = dt.timezone.utc


def at(y, m, d, h=0) -> dt.datetime:
    return dt.datetime(y, m, d, h, tzinfo=UTC)


# 2020-01-06 to poniedziałek.
MON, TUE, WED, THU, FRI, SAT, SUN = (at(2020, 1, d) for d in range(6, 13))


# --- liczenie dni -----------------------------------------------------------

def test_a_full_week_costs_seven_days():
    """1+1+3+1+1 na dni robocze, weekend niesie środa."""
    assert rollover_days(MON, at(2020, 1, 13)) == 7


def test_wednesday_rollover_is_charged_three_days():
    assert rollover_days(WED, THU) == 3


def test_a_plain_weekday_rollover_is_one_day():
    assert rollover_days(MON, TUE) == 1
    assert rollover_days(THU, FRI) == 1


def test_weekend_has_no_rollover_of_its_own():
    assert rollover_days(SAT, SUN) == 0
    assert rollover_days(FRI, at(2020, 1, 13)) == 1     # tylko piątkowy


def test_position_closed_before_the_rollover_pays_nothing():
    assert rollover_days(at(2020, 1, 6, 8), at(2020, 1, 6, 20)) == 0


def test_position_held_across_the_rollover_pays_one_day():
    assert rollover_days(at(2020, 1, 6, 20), at(2020, 1, 6, 22)) == 1


def test_rollover_boundary_is_inclusive_at_the_exit():
    exact = dt.datetime.combine(MON.date(), ROLLOVER_UTC, tzinfo=UTC)
    assert rollover_days(at(2020, 1, 6, 8), exact) == 1


def test_ten_business_days_is_about_two_calendar_weeks():
    """Horyzont V1a: wejście w poniedziałek, bariera 10 dni roboczych później."""
    assert rollover_days(MON, at(2020, 1, 20)) == 14


def test_exit_before_entry_is_rejected():
    with pytest.raises(ValueError, match="przed wejściem"):
        rollover_days(TUE, MON)


# --- wzór -------------------------------------------------------------------

def test_formula_matches_the_config_expression():
    # (1,0% marży + 2,0% różnicy przeciw nam) × 10 dni / (365 × 0,011)
    got = financing_r("short", days=10, stop_pct=0.011, diff_pct=2.0,
                      markup_annual_pct=1.0)
    assert got == pytest.approx(0.03 * 10 / (365 * 0.011))


def test_long_and_short_differ_by_twice_the_carry():
    kw = dict(days=10, stop_pct=0.011, diff_pct=2.8, markup_annual_pct=1.0)
    long, short = financing_r("long", **kw), financing_r("short", **kw)
    assert short - long == pytest.approx(2 * 0.028 * 10 / (365 * 0.011))


def test_positive_carry_can_make_financing_a_credit():
    """AUD 3,0% vs JPY −0,1%: long AUDJPY dostaje carry ponad marżę."""
    assert financing_r("long", days=10, stop_pct=0.02, diff_pct=3.1,
                       markup_annual_pct=1.0) < 0


def test_the_markup_is_paid_by_both_sides():
    """Przy zerowej różnicy stóp obie strony płacą tyle samo, i to dodatnio."""
    kw = dict(days=10, stop_pct=0.011, diff_pct=0.0, markup_annual_pct=1.0)
    long, short = financing_r("long", **kw), financing_r("short", **kw)
    assert long == short > 0


def test_cost_scales_linearly_with_days_and_inversely_with_the_stop():
    base = financing_r("short", days=10, stop_pct=0.011, diff_pct=2.0,
                       markup_annual_pct=1.0)
    assert financing_r("short", days=20, stop_pct=0.011, diff_pct=2.0,
                       markup_annual_pct=1.0) == pytest.approx(2 * base)
    assert financing_r("short", days=10, stop_pct=0.022, diff_pct=2.0,
                       markup_annual_pct=1.0) == pytest.approx(base / 2)


def test_financing_is_material_against_the_gate_2_threshold():
    """Uzasadnienie ADR-035 liczbą, nie zdaniem: EUR/USD 2019, 10 dni."""
    got = financing_r("long", days=14, stop_pct=0.011, diff_pct=-2.8,
                      markup_annual_pct=1.0)
    assert got > 0.10                    # więcej niż CAŁY próg bramki 2


def test_zero_stop_distance_is_rejected():
    with pytest.raises(ValueError, match="stop"):
        financing_r("long", days=10, stop_pct=0.0, diff_pct=1.0,
                    markup_annual_pct=1.0)


def test_unknown_side_is_rejected():
    with pytest.raises(ValueError, match="kierunek"):
        financing_r("flat", days=10, stop_pct=0.011, diff_pct=1.0,
                    markup_annual_pct=1.0)


def test_negative_markup_is_rejected():
    with pytest.raises(ValueError, match="marża"):
        financing_r("long", days=10, stop_pct=0.011, diff_pct=1.0,
                    markup_annual_pct=-0.5)


# --- nakładanie na etykiety -------------------------------------------------

def rates_frame() -> pl.DataFrame:
    rows = []
    for y in (2019, 2020):
        for m in range(1, 13):
            rows += [{"date": dt.date(y, m, 1), "currency": c, "kind": "overnight",
                      "value": v, "series": "TEST"}
                     for c, v in (("EUR", -0.40), ("USD", 2.40))]
    return pl.DataFrame(rows, schema=SCHEMA)


def labels_frame() -> pl.DataFrame:
    return pl.DataFrame({
        "symbol": ["EURUSD", "EURUSD"],
        "side": ["long", "short"],
        "ts": pl.Series([at(2020, 1, 6), at(2020, 1, 6)],
                        dtype=pl.Datetime("ms", "UTC")),
        "t1": pl.Series([at(2020, 1, 20), at(2020, 1, 20)],
                        dtype=pl.Datetime("ms", "UTC")),
        "entry_price": [1.1000, 1.1000],
        "sl": [1.0780, 1.1220],            # 2,0% ceny
        # Składniki spójne z rachunkiem symulatora:
        # r = gross_r − (cost_r − spread_r) = 0,512 − 0,008
        "r": [0.504, 0.504],
        "gross_r": [0.512, 0.512],
        "cost_r": [0.012, 0.012],
        "spread_r": [0.004, 0.004],
        "slip_r": [0.002, 0.002],
    })


def test_apply_financing_charges_the_long_and_credits_the_short():
    """EUR −0,40 vs USD 2,40: long EURUSD płaci różnicę, short ją dostaje."""
    out = apply_financing(labels_frame(), rates_frame(), markup_annual_pct=1.0)
    long, short = out["financing_r"][0], out["financing_r"][1]
    assert long > 0 > short
    assert out["r"][0] < 0.50 < out["r"][1]


def test_financing_uses_the_previous_month_rate():
    """Transakcja ze stycznia wycenia się grudniową różnicą stóp.

    Średnia stycznia jest znana dopiero po styczniu — użycie jej byłoby
    zaglądaniem w przyszłość. Rozjeżdżamy oba miesiące tak, żeby pomyłka
    była widoczna w wyniku, a nie tylko w intencji.
    """
    rows = []
    for (y, m), usd in (((2019, 12), 2.40), ((2020, 1), 0.10)):
        rows += [{"date": dt.date(y, m, 1), "currency": c, "kind": "overnight",
                  "value": v, "series": "TEST"}
                 for c, v in (("EUR", -0.40), ("USD", usd))]
    r = pl.DataFrame(rows, schema=SCHEMA)

    out = apply_financing(labels_frame(), r, markup_annual_pct=1.0)
    grudzien = financing_r("long", days=14, stop_pct=0.02, diff_pct=-2.80,
                           markup_annual_pct=1.0)
    styczen = financing_r("long", days=14, stop_pct=0.02, diff_pct=-0.50,
                          markup_annual_pct=1.0)
    assert out["financing_r"][0] == pytest.approx(grudzien)
    assert out["financing_r"][0] != pytest.approx(styczen)


def test_original_result_is_recoverable():
    out = apply_financing(labels_frame(), rates_frame(), markup_annual_pct=1.0)
    assert (out["r"] + out["financing_r"]).to_list() == pytest.approx([0.504, 0.504])


def test_cost_ladder_subtracts_financing_at_every_multiplier():
    """Bez tego drabinka raportowałaby wynik lepszy niż faktyczny."""
    out = apply_financing(labels_frame(), rates_frame(), markup_annual_pct=1.0)
    assert repriced(out, 1.0).to_list() == pytest.approx(out["r"].to_list())
    assert repriced(out, 2.0)[0] < repriced(out, 1.0)[0]


def test_labels_without_required_columns_are_rejected():
    lab = labels_frame().drop("sl")
    with pytest.raises(ValueError, match="sl"):
        apply_financing(lab, rates_frame(), markup_annual_pct=1.0)


def test_markup_comes_from_the_config():
    cfg = {"costs": {"financing": {"cohort_a_markup_annual_pct": 1.0}}}
    assert markup_from(cfg) == 1.0


# --- oś wrażliwości na marżę (ADR-037) --------------------------------------

def test_refinancing_reproduces_a_direct_computation():
    """Przeliczenie marży bez czytania stóp musi dać to samo, co liczenie od zera."""
    base, other = 0.5, 2.0
    a = apply_financing(labels_frame(), rates_frame(), markup_annual_pct=base)
    b = apply_financing(labels_frame(), rates_frame(), markup_annual_pct=other)
    assert refinanced(a, base, other).to_list() == pytest.approx(b["r"].to_list())


def test_refinancing_to_the_same_markup_changes_nothing():
    a = apply_financing(labels_frame(), rates_frame(), markup_annual_pct=0.5)
    assert refinanced(a, 0.5, 0.5).to_list() == pytest.approx(a["r"].to_list())


def test_higher_markup_hurts_both_directions_equally():
    """Marżę płacą obie strony, więc różnica long/short nie zależy od niej."""
    a = apply_financing(labels_frame(), rates_frame(), markup_annual_pct=0.5)
    r_lo, r_hi = a["r"].to_list(), refinanced(a, 0.5, 2.0).to_list()
    assert r_hi[0] < r_lo[0] and r_hi[1] < r_lo[1]
    assert (r_lo[0] - r_hi[0]) == pytest.approx(r_lo[1] - r_hi[1])


def test_markup_ladder_covers_the_configured_grid():
    cfg = {"costs": {"financing": {"cohort_a_markup_annual_pct": 0.5,
                                   "cohort_a_markup_sensitivity": [0.5, 1.0, 2.0]}}}
    a = apply_financing(labels_frame(), rates_frame(),
                        markup_annual_pct=markup_from(cfg))
    ladder = markup_ladder(a, markup_from(cfg), markup_grid_from(cfg))
    assert [s.markup_annual_pct for s in ladder] == [0.5, 1.0, 2.0]
    assert ladder[0].expectancy > ladder[1].expectancy > ladder[2].expectancy
    md = render_markup_markdown(ladder)
    assert all(f"| {m:g}% |" in md for m in (0.5, 1.0, 2.0))


def test_refinancing_without_apply_financing_is_rejected():
    with pytest.raises(ValueError, match="fin_unit_r|financing_r"):
        refinanced(labels_frame(), 0.5, 1.0)
