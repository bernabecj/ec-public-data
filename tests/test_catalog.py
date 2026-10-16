from __future__ import annotations

import pytest

import ecuadata as ec
from ecuadata import _catalog

IMPLEMENTED = {
    ("BCE", "pib_trimestral"),
    ("BCE", "remesas"),
    ("BCE", "tasas_interes"),
    ("INEC", "ipc"),
}


def test_list_sources_shape():
    frame = ec.list_sources()
    assert frame.index.names == ["provider", "dataset"]
    assert list(frame.columns) == [
        "call",
        "status",
        "frequency",
        "start",
        "units",
        "title",
        "via",
        "url",
    ]
    assert set(frame.index) >= IMPLEMENTED
    assert frame.loc[("INEC", "ipc"), "call"] == "ec.inec.ipc()"
    assert frame.loc[("INEC", "enemdu"), "status"] == "planned"
    assert frame.loc[("INEC", "enemdu"), "call"] == ""


def test_list_sources_filter():
    assert set(ec.list_sources(status="experimental").index) == IMPLEMENTED
    assert ec.list_sources(status="planned")["call"].eq("").all()
    with pytest.raises(ValueError, match="Estado desconocido"):
        ec.list_sources(status="beta")


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("inflacion", [("INEC", "ipc")]),
        ("Inflación", [("INEC", "ipc")]),
        ("CPI", [("INEC", "ipc")]),
        ("remesas", [("BCE", "remesas")]),
        ("remittances", [("BCE", "remesas")]),
        ("tasa credito", [("BCE", "tasas_interes")]),
        ("gdp", [("BCE", "pib_trimestral")]),
        ("producto interno bruto", [("BCE", "pib_trimestral")]),
        ("nothing-like-this", []),
    ],
)
def test_search(query, expected):
    assert ec.search(query).index.tolist() == expected


def test_search_status_filter():
    assert ec.search("empleo").empty
    assert ec.search("empleo", status=None).index.tolist() == [("INEC", "enemdu")]
    assert ec.search("empleo", status="planned").index.tolist() == [("INEC", "enemdu")]
    with pytest.raises(ValueError, match="Estado desconocido"):
        ec.search("empleo", status="soon")
    with pytest.raises(ValueError, match="al menos una palabra"):
        ec.search("   ")


def test_every_implemented_entry_resolves_to_its_function():
    for dataset in _catalog.DATASETS:
        assert dataset.status in _catalog.STATUSES
        if dataset.function:
            function = dataset.resolve()
            assert callable(function) and function.__name__ == dataset.name
            assert dataset.call == f"ec.{dataset.function}()"
        else:
            assert dataset.status == "planned"
            with pytest.raises(NotImplementedError):
                dataset.resolve()


def test_get():
    assert _catalog.get("ipc").provider == "INEC"
    assert _catalog.get("bce.remesas").name == "remesas"
    with pytest.raises(KeyError):
        _catalog.get("nope")
