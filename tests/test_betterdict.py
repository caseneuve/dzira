import pytest

from src.dzira.betterdict import D


@pytest.fixture
def d():
    return D(a=1, b=2, c=3)

class TestBetterDictBehavior:
    def test_should_inherit_from_dict(self):
        assert isinstance(D(), dict)
        # Should support all dict operations
        d = D(a=1, b=2)
        assert len(d) == 2
        assert "a" in d
        assert list(d.keys()) == ["a", "b"]
        assert list(d.values()) == [1, 2]

@pytest.mark.parametrize(
    "input,expected",
    [
        (("a", "c"), [1, 3]),
        (("a",), [1]),
        (("b", "x"), [2, None])
    ]

)
def test_should_return_values_for_specified_keys_or_none(d, input, expected):
    assert d(*input) == expected

@pytest.mark.parametrize(
    "input,expected",
    [
        ((("x", 99), "c"), [99, 3]),
        (("a", ("z", 42)), [1, 42]),
        ((("b", 22), ("c", 88)), [2, 3])
    ]
)
def test_should_use_fallback_values_from_tuples(d, input, expected):
    assert d(*input) == expected

def test_should_return_all_values_when_called_with_no_args(d):
    # Test the missing line 18 coverage: return self.values()
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

    assert "Provide even number of key-value args, need a value for key: 'a'" in str(exc_info.value)

def test_should_check_if_key_has_non_none_value(d):
    assert d.has("a")  # a=1, which is not None
    assert d.has("foo") is False  # foo doesn't exist, so get() returns None

def test_should_have_informative_string_representation():
    d = D(a=1)
    assert repr(d) == "betterdict({'a': 1})"
    assert str(d) == "{'a': 1}"

def test_should_create_new_instance_without_specified_keys(d):
    assert d.without("a") == D(b=2, c=3)
    assert d.without("a", "c") == D(b=2)

def test_should_support_attribute_style_assignment(d):
    assert d.x is None

    d.x = 42

    assert d.x == 42
    assert repr(d) == "betterdict({'a': 1, 'b': 2, 'c': 3, 'x': 42})"

def test_should_support_attribute_style_deletion(d):
    assert d.a == 1

    del d.a

    assert d.a is None
    assert repr(d) == "betterdict({'b': 2, 'c': 3})"

def test_should_distinguish_none_from_other_falsy_values():
    d = D(zero=0, empty_string="", none_value=None, false_value=False)
    
    # has() checks 'is not None', not truthiness
    assert d.has("zero")  # 0 is not None
    assert d.has("empty_string")  # "" is not None
    assert not d.has("none_value")  # None is None
    assert d.has("false_value")  # False is not None
    
    # Non-existent key should return False (gets None)
    assert not d.has("non_existent")
    
    # Any non-None value should return True
    d.truthy_value = "hello"
    assert d.has("truthy_value")

def test_without_multiple_keys():
    d = D(a=1, b=2, c=3, d=4, e=5)
    
    # Test removing multiple keys at once
    result = d.without("a", "c", "e")
    expected = D(b=2, d=4)
    
    assert result == expected
    # Original should be unchanged
    assert d == D(a=1, b=2, c=3, d=4, e=5)

def test_chaining_operations():
    # Test that update returns self, allowing chaining
    d = D()
    result = d.update("a", 1).update("b", 2).update(c=3)
    
    assert result is d  # Should be the same object
    assert d == D(a=1, b=2, c=3)
