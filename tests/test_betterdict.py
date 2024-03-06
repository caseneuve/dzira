import pytest

from src.dzira.betterdict import D


@pytest.fixture
def d():
    return D(a=1, b=2, c=3)

def test_inherits_from_dict():
    assert isinstance(D(), dict)

@pytest.mark.parametrize(
    "input,expected",
    [
        (("a", "c"), [1, 3]),
        (("a",), [1]),
        (("b", "x"), [2, None])
    ]

)
def test_call_returns_unpacked_values_of_selected_keys_or_none(d, input, expected):
    assert d(*input) == expected

@pytest.mark.parametrize(
    "input,expected",
    [
        ((("x", 99), "c"), [99, 3]),
        (("a", ("z", 42)), [1, 42]),
        ((("b", 22), ("c", 88)), [2, 3])
    ]
)
def test_call_accepts_tuples_with_fallback_values(d, input, expected):
    assert d(*input) == expected

def test_update_returns_self_with_key_of_given_value(d):
    assert d.update("a", 99) == D({**d, "a": 99})
    assert d.update("x", 77) == D({**d, "x": 77})

def test_update_accepts_multiple_key_value_pairs(d):
    assert d.update("d", 4, "e", 5) == D({**d, "d": 4, "e": 5})
    assert d.update(d=4, e=5) == D({**d, "d": 4, "e": 5})

def test_update_accepts_function_as_value_and_calls_it_with_existing_value(d):
    assert d.update("a", lambda x: x * 10) == D({**d, "a": 10})
    assert d.update("b", lambda x: x + 2) == D({**d, "b": 4})
    assert d.update("absent", lambda x: x + 1 if x is not None else 1) == D({**d, "absent": 1})

def test_update_raises_when_odd_number_of_args_given(d):
    with pytest.raises(Exception) as exc_info:
        d.update("a")

    assert "Provide even number of key-value args, need a value for key: 'a'" in str(exc_info.value)

def test_has_returns_boolean_showing_if_key_has_a_value(d):
    assert d.has("a")
    assert d.has("foo") is False

def test_repr():
    assert repr(D(a=1)) == "betterdict({'a': 1})"

def test_str():
    assert str(D(a=1)) == "{'a': 1}"

def test_without_returns_new_instance_of_betterdict_without_keys_matching_args(d):
    assert d.without("a") == D(b=2, c=3)
    assert d.without("a", "c") == D(b=2)

def test_supports_setitem(d):
    assert d.x is None

    d.x = 42

    assert d.x == 42
    assert repr(d) == "betterdict({'a': 1, 'b': 2, 'c': 3, 'x': 42})"

def test_supports_delitem(d):
    assert d.a == 1

    del d.a

    assert d.a is None
    assert repr(d) == "betterdict({'b': 2, 'c': 3})"
