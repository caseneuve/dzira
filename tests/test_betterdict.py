import pytest

from src.dzira.betterdict import D


@pytest.fixture
def d():
    return D(dict(a=1, b=2, c=3))


@pytest.mark.parametrize(
    "input,expected", [(("a", "c"), (1, 3)), (("a",), (1,)), (("b", "x"), (2, None))]
)
def test_should_return_values_for_specified_keys_or_none(d, input, expected):
    assert d(*input) == expected


@pytest.mark.parametrize(
    "input,expected",
    [((("x", 99), "c"), (99, 3)), (("a", ("z", 42)), (1, 42)), ((("b", 22), ("c", 88)), (2, 3))],
)
def test_should_use_fallback_values_from_tuples(d, input, expected):
    assert d(*input) == expected


def test_should_return_all_values_when_called_with_no_args(d):
    result = d()
    expected_values = [1, 2, 3]  # values from fixture: a=1, b=2, c=3

    assert list(result) == expected_values


def test_should_update_values_and_return_self(d):
    assert d.update("a", 99) == D({**d, "a": 99})
    assert d.update("x", 77) == D({**d, "x": 77})


def test_should_accept_multiple_key_value_pairs_in_update(d):
    assert d.update("d", 4, "e", 5) == D({**d, "d": 4, "e": 5})
    assert d.update(d=4, e=5) == D({**d, "d": 4, "e": 5})


def test_should_apply_functions_to_existing_values_in_update(d):
    assert d.update("a", lambda x: x * 10) == D({**d, "a": 10})
    assert d.update("b", lambda x: x + 2) == D({**d, "b": 4})
    assert d.update("absent", lambda x: x + 1 if x is not None else 1) == D({**d, "absent": 1})


def test_should_raise_exception_for_unpaired_arguments(d):
    with pytest.raises(Exception) as exc_info:
        d.update("a")

    assert "Even number of args required, missing value for: 'a'" in str(exc_info.value)


def test_should_check_if_key_has_non_none_value(d):
    assert d.has("a")  # a=1, which is not None
    assert d.has("foo") is False  # foo doesn't exist, so get() returns None


def test_should_have_informative_string_representation():
    d = D(a=1)
    assert repr(d) == "betterdict({'a': 1})"
    assert str(d) == "{'a': 1}"


def test_should_create_new_instance_without_specified_keys(d):
    assert d.dissoc("a") == D(b=2, c=3)
    assert d.dissoc("a", "c") == D(b=2)


def test_should_distinguish_none_from_other_falsy_values():
    d = D(zero=0, empty_string="", none_value=None, false_value=False, truthy_value="hello")

    assert d.has("zero")
    assert d.has("empty_string")
    assert not d.has("none_value")
    assert d.has("false_value")
    assert not d.has("non_existent")
    assert d.has("truthy_value")


def test_without_multiple_keys():
    d = D(a=1, b=2, c=3, d=4, e=5)

    result = d.dissoc("a", "c", "e")
    expected = D(b=2, d=4)

    assert result == expected
    assert d == D(a=1, b=2, c=3, d=4, e=5)


def test_chaining_operations():
    d = D()
    result = d.update("a", 1).update("b", 2).update(c=3)

    assert result == D(a=1, b=2, c=3)
    assert result is not d
    assert d == D()


def test_immutability():
    d1 = D(a=1, b=2)
    d2 = d1.assoc("c", 3)

    assert d1 == D(a=1, b=2)  # Original unchanged
    assert d2 == D(a=1, b=2, c=3)  # New instance created
    assert d1 is not d2


def test_assoc_with_callable():
    d = D(a=1)
    result = d.assoc("a", lambda x: x * 2)  # type: ignore

    assert result == D(a=2)
    assert d == D(a=1)


def test_functional_combinators():
    d = D(a=1, b=2, c=3)

    doubled = d.map_values(lambda x: x * 2)
    assert doubled == D(a=2, b=4, c=6)

    # map_keys
    prefixed = d.map_keys(lambda k: f"new_{k}")
    assert prefixed == D(new_a=1, new_b=2, new_c=3)

    # filter
    evens = d.filter(lambda k, v: v % 2 == 0)
    assert evens == D(b=2)

    # filter_keys
    a_keys = d.filter_keys(lambda k: "a" in k)
    assert a_keys == D(a=1)

    # filter_values
    small_vals = d.filter_values(lambda v: v < 3)
    assert small_vals == D(a=1, b=2)


def test_dict_like_operations():
    d = D(a=1, b=2)

    assert len(d) == 2
    assert "a" in d
    assert "x" not in d
    assert d["a"] == 1
    assert list(d.keys()) == ["a", "b"]
    assert list(d.values()) == [1, 2]
    assert list(d.items()) == [("a", 1), ("b", 2)]
    assert list(d) == ["a", "b"]


def test_get_with_default():
    d = D(a=1)

    assert d.get("a") == d.a == 1
    assert d.get("x") is None
    assert d.get("x", 42) == 42


def test_attribute_access_raises_keyerror():
    d = D(a=1)

    with pytest.raises(KeyError):
        d.nonexistent


@pytest.mark.parametrize(
    "keys,expected",
    [
        (["a"], D(b=2, c=3)),
        (["a", "c"], D(b=2)),
        ([], D(a=1, b=2, c=3)),
    ],
)
def test_dissoc_variants(keys, expected):
    d = D(a=1, b=2, c=3)
    result = d.dissoc(*keys)

    assert result == expected
    assert d == D(a=1, b=2, c=3)


def test_empty_dict_operations():
    d = D()

    assert len(d) == 0
    assert list(d()) == []
    assert not d.has("any_key")
    assert d.get("any_key") is None


def test_reduce():
    d = D(a=1, b=2, c=3)

    # Sum all values
    total = d.reduce(lambda acc, k, v: acc + v, 0)
    assert total == 6

    # Concat keys
    keys = d.reduce(lambda acc, k, v: acc + k, "")
    assert keys == "abc"


def test_merge():
    d1 = D(a=1, b=2)
    d2 = D(b=3, c=4)

    merged = d1.merge(d2)
    assert merged == D(a=1, b=3, c=4)
    assert d1 == D(a=1, b=2)


def test_select_keys():
    d = D(a=1, b=2, c=3, d=4)

    selected = d.select_keys(["a", "c", "x"])
    assert selected == D(a=1, c=3)
