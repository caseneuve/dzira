import pytest

from src.dzira.betterdict import D


class TestD:
    def setup(self):
        self.d = D(a=1, b=2, c=3)

    def test_inherits_from_dict(self):
        assert isinstance(D(), dict)

    @pytest.mark.parametrize(
        "input,expected",
        [
            (("a", "c"), [1, 3]),
            (("a",), [1]),
            (("b", "x"), [2, None])
        ]

    )
    def test_call_returns_unpacked_values_of_selected_keys_or_none(self, input, expected):
        assert self.d(*input) == expected

    @pytest.mark.parametrize(
        "input,expected",
        [
            ((("x", 99), "c"), [99, 3]),
            (("a", ("z", 42)), [1, 42]),
            ((("b", 22), ("c", 88)), [2, 3])
        ]
    )
    def test_call_accepts_tuples_with_fallback_values(self, input, expected):
        assert self.d(*input) == expected

    def test_update_returns_self_with_key_of_given_value(self):
        assert self.d.update("a", 99) == D({**self.d, "a": 99})
        assert self.d.update("x", 77) == D({**self.d, "x": 77})

    def test_update_accepts_multiple_key_value_pairs(self):
        assert self.d.update("d", 4, "e", 5) == D({**self.d, "d": 4, "e": 5})
        assert self.d.update(d=4, e=5) == D({**self.d, "d": 4, "e": 5})

    def test_update_accepts_function_as_value_and_calls_it_with_existing_value(self):
        assert self.d.update("a", lambda x: x * 10) == D({**self.d, "a": 10})
        assert self.d.update("b", lambda x: x + 2) == D({**self.d, "b": 4})
        assert self.d.update("absent", lambda x: x + 1 if x is not None else 1) == D({**self.d, "absent": 1})

    def test_update_raises_when_odd_number_of_args_given(self):
        with pytest.raises(Exception) as exc_info:
            self.d.update("a")

        assert "Provide even number of key-value args, need a value for key: 'a'" in str(exc_info.value)

    def test_has_returns_boolean_showing_if_key_has_a_value(self):
        assert self.d.has("a")
        assert self.d.has("foo") is False

    def test_repr(self):
        assert repr(D(a=1)) == "betterdict({'a': 1})"

    def test_str(self):
        assert str(D(a=1)) == "{'a': 1}"

    def test_exposes_keys_as_attributes_and_raises_attributeerror_for_missing_attr(self):
        assert self.d.a == 1
        assert self.d.b == 2
        assert self.d.c == 3

        with pytest.raises(AttributeError) as exc_info:
            self.d.x

        assert "'D' object has no attribute 'x'" in str(exc_info.value)

    def test_without_returns_new_instance_of_betterdict_without_keys_matching_args(self):
        assert self.d.without("a") == D(b=2, c=3)
        assert self.d.without("a", "c") == D(b=2)
