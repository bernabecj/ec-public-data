import math

import pandas as pd
import pytest

from ecuadata._parsing import parse_quarter, snake_case, to_number


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
