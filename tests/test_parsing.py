import math

import pandas as pd
import pytest

from ecuadata._parsing import (
    month_number,
    parse_month,
    parse_quarter,
    parse_week,
    parse_year,
    snake_case,
    to_number,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(1234.5, 1234.5), ("1.234,5", 1234.5), ("1,234.5", 1234.5), ("4,5 (p)", 4.5)],
)
def test_to_number(raw, expected):
    assert to_number(raw) == expected


def test_to_number_missing():
    assert math.isnan(to_number("n.d."))


def test_snake_case():
    assert snake_case("Formación Bruta de Capital Fijo (FBKF)") == (
        "formacion_bruta_de_capital_fijo_fbkf"
    )


@pytest.mark.parametrize("label", ["2025.II", "2025Q2", "II trimestre 2025"])
def test_parse_quarter(label):
    assert parse_quarter(label) == pd.Period("2025Q2", freq="Q")


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Ene 2006", "2006-01"),
        ("Ago 2026", "2026-08"),
        ("enero de 2026", "2026-01"),
        ("Sept 2026", "2026-09"),
        ("Setiembre 2026", "2026-09"),
        ("2026-08", "2026-08"),
        ("202608", "2026-08"),
        ("2026M08", "2026-08"),
    ],
)
def test_parse_month(label, expected):
    assert parse_month(label) == pd.Period(expected, freq="M")


@pytest.mark.parametrize("label", ["2026-13", "Foo 2026", "2026", "hello"])
def test_parse_month_rejects_garbage(label):
    with pytest.raises(ValueError):
        parse_month(label)


@pytest.mark.parametrize(
    ("label", "start"),
    [
        ("Ene 2015 (05 al 11)", "2015-01-05"),
        ("Oct 2026 (26 al 01 nov)", "2026-10-26"),
        ("Dic 2015 (28 al 03 ene 2016)", "2015-12-28"),
        ("Sep 2015 (7 al 13)", "2015-09-07"),
    ],
)
def test_parse_week(label, start):
    period = parse_week(label)
    assert period.freqstr == "W-SUN"
    assert period.start_time.date().isoformat() == start


def test_parse_week_rejects_month_label():
    with pytest.raises(ValueError):
        parse_week("Ene 2015")


@pytest.mark.parametrize("value", [1966, "1966", 1966.0, "1966.0"])
def test_parse_year(value):
    assert parse_year(value) == pd.Period("1966", freq="Y")


def test_parse_year_rejects_non_years():
    with pytest.raises(ValueError):
        parse_year("2016-I")


@pytest.mark.parametrize("label", ["2016-I", "2026-II", "2000.IV"])
def test_parse_quarter_bcedata_labels(label):
    assert parse_quarter(label).freqstr == "Q-DEC"


def test_month_number():
    assert [month_number(m) for m in ("Ene", "feb.", "Septiembre", "sep", "dic")] == [
        1,
        2,
        9,
        9,
        12,
    ]
    with pytest.raises(ValueError):
        month_number("xyz")
