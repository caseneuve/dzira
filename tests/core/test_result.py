import pytest

from dzira.core.result import Result, compose, destruct, failure, partial, pipe, safe, success


class TestResultCreation:
    def test_should_create_successful_result_with_value(self):
        success = Result(value=42, error=None)

        assert success.value == 42
        assert success.error is None

    def test_should_create_error_result_with_exception(self):
        error = ValueError("test error")
        failure = Result(value=None, error=error)

        assert failure.value is None
        assert failure.error == error

    def test_should_allow_any_value_type(self):
        string_result = Result(value="hello", error=None)
        list_result = Result(value=[1, 2, 3], error=None)
        dict_result = Result(value={"key": "value"}, error=None)

        assert string_result.value == "hello"
        assert list_result.value == [1, 2, 3]
        assert dict_result.value == {"key": "value"}


class TestSafeDecorator:
    def test_should_wrap_successful_function_calls(self):
        @safe
        def add_one(x: int) -> int:
            return x + 1

        result = add_one(41)

        assert result.value == 42
        assert result.error is None

    def test_should_catch_exceptions_and_return_error_result(self):
        @safe
        def divide(a: int, b: int) -> float:
            return a / b

        result = divide(10, 0)

        assert result.value is None
        assert isinstance(result.error, ZeroDivisionError)

    def test_should_handle_functions_with_keyword_arguments(self):
        @safe
        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        result = greet(name="World", greeting="Hi")

        assert result.value == "Hi, World!"
        assert result.error is None

    def test_should_preserve_function_metadata(self):
        @safe
        def documented_function(x: int) -> int:
            """This function adds one to x"""
            return x + 1

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ and ("adds one to x" in documented_function.__doc__)

    def test_safe_decorator_propagate_error(self):
        @safe
        def add_one(x: int) -> int:
            return x + 1

        error = ValueError("test error")
        input_result = Result(value=None, error=error)
        result = add_one(input_result)
        assert result.value is None
        assert result.error == error


class TestResultPipelines:
    def test_should_execute_successful_pipeline_steps_in_sequence(self):
        @safe
        def double(x: int) -> int:
            return x * 2

        @safe
        def add_ten(x: int) -> int:
            return x + 10

        result = pipe(16, double, add_ten)

        assert result.value == 42
        assert result.error is None

    def test_should_short_circuit_on_first_error_in_pipeline(self):
        @safe
        def double(x: int) -> int:
            return x * 2

        @safe
        def divide_by_zero(x: int) -> float:
            return x / 0  # This will fail

        @safe
        def add_ten(x: int) -> int:
            return x + 10  # Should never execute

        result = pipe(16, double, divide_by_zero, add_ten)

        assert result.value is None
        assert isinstance(result.error, ZeroDivisionError)

    def test_should_handle_mixed_result_and_value_inputs(self):
        @safe
        def double(x: int) -> int:
            return x * 2

        error_result = Result(value=None, error=ValueError("Previous error"))
        result = double(error_result)

        assert result.error is not None
        assert "Previous error" in str(result.error)
        assert result.value is None

    def test_should_propagate_errors_through_complex_pipeline(self):
        @safe
        def validate_positive(x: int) -> int:
            if x <= 0:
                raise ValueError("Must be positive")
            return x

        @safe
        def square(x: int) -> int:
            return x * x

        @safe
        def take_square_root(x: int) -> float:
            return x ** 0.5

        # Test with invalid input
        result = pipe(-5, validate_positive, square, take_square_root)

        assert result.error is not None
        assert "Must be positive" in str(result.error)
        assert result.value is None

        # Test with valid input
        result = pipe(4, validate_positive, square, take_square_root)

        assert result.error is None
        assert result.value == 4.0  # sqrt(16) = 4


class TestResultRopMethods:
    def test_map_should_transform_success_value(self):
        result = success(5)
        mapped = result.map(lambda x: x * 2)

        assert mapped.is_success
        assert mapped.value == 10
        assert mapped.error is None

    def test_map_should_propagate_failure_unchanged(self):
        error = ValueError("original error")
        result = failure(error)
        mapped = result.map(lambda x: x * 2)

        assert mapped.is_failure
        assert mapped.error == error
        assert mapped.value is None

    def test_map_should_catch_exceptions_in_mapper_function(self):
        result = success(5)
        mapped = result.map(lambda x: x / 0)  # Division by zero

        assert mapped.is_failure
        assert isinstance(mapped.error, ZeroDivisionError)
        assert mapped.value is None

    def test_bind_should_chain_success_results(self):
        result = success(5)
        bound = result.bind(lambda x: success(x * 2))

        assert bound.is_success
        assert bound.value == 10
        assert bound.error is None

    def test_bind_should_propagate_original_failure(self):
        error = ValueError("original error")
        result = failure(error)
        bound = result.bind(lambda x: success(x * 2))

        assert bound.is_failure
        assert bound.error == error
        assert bound.value is None

    def test_bind_should_propagate_new_failure(self):
        result = success(5)
        new_error = RuntimeError("bind error")
        bound = result.bind(lambda x: failure(new_error))

        assert bound.is_failure
        assert bound.error == new_error
        assert bound.value is None

    def test_bind_should_catch_exceptions_in_bound_function(self):
        result = success(5)
        bound = result.bind(lambda x: x / 0)  # This will raise ZeroDivisionError

        assert bound.is_failure
        assert isinstance(bound.error, ZeroDivisionError)

    def test_fold_should_handle_success_case(self):
        result = success(5)
        folded = result.fold(
            on_success=lambda x: f"success: {x}",
            on_failure=lambda e: f"error: {e}"
        )

        assert folded == "success: 5"

    def test_fold_should_handle_failure_case(self):
        error = ValueError("test error")
        result = failure(error)
        folded = result.fold(
            on_success=lambda x: f"success: {x}",
            on_failure=lambda e: f"error: {e}"
        )

        assert folded == "error: test error"

    def test_tee_should_apply_side_effect_on_success(self):
        side_effects = []
        result = success(5)

        teed = result.tee(lambda x: side_effects.append(x))

        assert teed.is_success
        assert teed.value == 5
        assert teed is result  # Should return original result
        assert side_effects == [5]

    def test_tee_should_ignore_side_effects_on_failure(self):
        side_effects = []
        error = ValueError("test error")
        result = failure(error)

        teed = result.tee(lambda x: side_effects.append(x))

        assert teed.is_failure
        assert teed.error == error
        assert teed is result
        assert side_effects == []

    def test_tee_should_ignore_exceptions_in_side_effect(self):
        result = success(5)

        # Side effect that raises exception
        teed = result.tee(lambda x: x / 0)

        assert teed.is_success
        assert teed.value == 5
        assert teed is result  # Should still return original result

    def test_or_else_should_return_value_on_success(self):
        result = success(5)
        value = result.or_else(10)

        assert value == 5

    def test_or_else_should_return_default_on_failure(self):
        result = failure(ValueError("error"))
        value = result.or_else(10)

        assert value == 10

    def test_bool_conversion_success(self):
        result = success(5)
        assert bool(result) is True

    def test_bool_conversion_failure(self):
        result = failure(ValueError("error"))
        assert bool(result) is False

    def test_is_success_property(self):
        assert success(5).is_success is True
        assert failure(ValueError()).is_success is False

    def test_is_failure_property(self):
        assert success(5).is_failure is False
        assert failure(ValueError()).is_failure is True


class TestHelperFunctions:
    def test_success_creates_success_result(self):
        result = success(42)

        assert result.is_success
        assert result.value == 42
        assert result.error is None

    def test_failure_creates_failure_result(self):
        error = ValueError("test error")
        result = failure(error)

        assert result.is_failure
        assert result.error == error
        assert result.value is None

    def test_compose_should_compose_functions_right_to_left(self):
        add_one = lambda x: x + 1
        multiply_two = lambda x: x * 2

        composed = compose(add_one, multiply_two)
        result = composed(5)

        # Should be: add_one(multiply_two(5)) = add_one(10) = 11
        assert result == 11

    def test_compose_with_single_function(self):
        add_one = lambda x: x + 1
        composed = compose(add_one)

        assert composed(5) == 6

    def test_compose_with_no_functions(self):
        composed = compose()

        # Identity function
        assert composed(5) == 5

    def test_partial_should_partially_apply_arguments(self):
        def add_three_numbers(a, b, c):
            return a + b + c

        partial_func = partial(add_three_numbers, 1, 2)
        result = partial_func(3)

        assert result == 6

    def test_partial_should_handle_keyword_arguments(self):
        def greet(greeting, name, punctuation="!"):
            return f"{greeting}, {name}{punctuation}"

        partial_func = partial(greet, "Hello", punctuation=".")
        result = partial_func("World")

        assert result == "Hello, World."

    def test_partial_with_mixed_args_and_kwargs(self):
        def func(a, b, c=3, d=4):
            return a + b + c + d

        partial_func = partial(func, 1, c=10)
        result = partial_func(2, d=20)

        assert result == 33  # 1 + 2 + 10 + 20

    def test_destruct_returns_keys_and_full_dict(self):
        input = {"a": 1, "b": 2, "c": 3, "d": 4}

        assert (1, 2, input) == destruct(input, "a", "b")
        assert (1, 3, input) == destruct(input, "a", "c")
        assert (2, 4, input) == destruct(input, "b", "d")

    def test_destruct_raises_if_no_key_provided(self):
        with pytest.raises(TypeError):
            destruct({})    # type: ignore[call-arg]

    def test_destruct_returns_none_for_missing_keys(self):
        input = {"a": 1}

        assert (None, input) == destruct(input, "b")
