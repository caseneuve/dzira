from dzira.core.result import Result, safe, pipe


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
        assert "adds one to x" in documented_function.__doc__


def test_safe_decorator_propagate_error():
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
