from dzira.core.result import Result, safe, pipe


def test_result_creation():
    success = Result(value=42, error=None)
    assert success.value == 42
    assert success.error is None

    error = ValueError("test error")
    failure = Result(value=None, error=error)
    assert failure.value is None
    assert failure.error == error


def test_safe_decorator_success():
    @safe
    def add_one(x: int) -> int:
        return x + 1

    result = add_one(41)
    assert result.value == 42
    assert result.error is None


def test_safe_decorator_error():
    @safe
    def divide(a: int, b: int) -> float:
        return a / b

    result = divide(10, 0)
    assert result.value is None
    assert isinstance(result.error, ZeroDivisionError)


def test_safe_decorator_with_kwargs():
    @safe
    def greet(name: str, greeting: str = "Hello") -> str:
        return f"{greeting}, {name}!"

    result = greet(name="World", greeting="Hi")
    assert result.value == "Hi, World!"
    assert result.error is None


def test_safe_decorator_propagate_error():
    @safe
    def add_one(x: int) -> int:
        return x + 1

    error = ValueError("test error")
    input_result = Result(value=None, error=error)
    result = add_one(input_result)
    assert result.value is None
    assert result.error == error


def test_pipe_success():
    @safe
    def double(x: int) -> int:
        return x * 2

    @safe
    def add_ten(x: int) -> int:
        return x + 10

    result = pipe(16, double, add_ten)
    assert result.value == 42
    assert result.error is None


def test_pipe_error():
    @safe
    def double(x: int) -> int:
        return x * 2

    @safe
    def divide(a: int, b: int) -> float:
        return a / b

    @safe
    def add_ten(x: int) -> int:
        return x + 10

    result = pipe(16, double, lambda x: divide(x, 0), add_ten)  # This will fail
    assert result.value is None
    assert isinstance(result.error, ZeroDivisionError)
