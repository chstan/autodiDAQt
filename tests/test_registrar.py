from daquiri.registrar import Registrar

import pytest

def test_registrar_collects_values():
    r = Registrar()

    @r.metadata("a")
    def pow(a, b):
        return a ** b


    assert r.collect_metadata() == {"a": []}
    pow(2, 3)
    assert r.collect_metadata() == {"a": [8]}
    assert r.collect_metadata() == {"a": []}


def test_registrar_buffer_retention():
    r = Registrar()

    @r.metadata("b", clear_buffer_on_collect=False)
    def interpolate(a):
        return f"value-{a}"

    interpolate(5)
    assert r.collect_metadata() == {"b": ["value-5"]}
    interpolate(6)
    assert r.collect_metadata() == {"b": ["value-5", "value-6"]}

def test_registrar_double_registration():
    r = Registrar()

    @r.metadata("test_double_name")
    def f():
        return

    with pytest.raises(ValueError) as exc:
        @r.metadata("test_double_name")
        def g():
            return
    
    assert "test_double_name" in str(exc.value)






