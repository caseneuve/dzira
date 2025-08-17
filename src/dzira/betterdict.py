from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Callable, Generic, Iterable, TypeVar, Any, Iterator, cast

K = TypeVar("K")
V = TypeVar("V")
U = TypeVar("U")


@dataclass(frozen=True)
class D(Generic[K, V]):
    _data: dict[K, V] = field(default_factory=dict)

    def __init__(self, data: dict[K, V] | None = None, **kwargs: V):
        if data is None:
            data = {}
        object.__setattr__(self, "_data", {**data, **kwargs})

    def __getattr__(self, key: Any) -> V:
        # Don't interfere with special/dunder attributes
        if key.startswith("__") and key.endswith("__"):
            raise AttributeError(key)
        if key in self._data:
            return self._data[key]
        raise KeyError(key)

    def __call__(self, *keys: K) -> Iterable[V | None]:
        if keys:
            return tuple(
                self._data.get(*k) if isinstance(k, tuple) else self._data.get(k) for k in keys
            )
        else:
            return self._data.values()

    def get(self, key: K, default: V | None = None) -> V | None:
        return self._data.get(key, default)

    def _apply_update(self, key: K, value: V | Callable[[V | None], V]) -> V:
        if callable(value):
            return cast(V, value(self.get(key)))
        else:
            return cast(V, value)

    def assoc(self, key: K, value: V | Callable[[V | None], V]) -> D[K, V]:
        new_value = self._apply_update(key, value)
        return D({**self._data, key: new_value})

    def dissoc(self, *keys: K) -> D[K, V]:
        return D({k: v for k, v in self._data.items() if k not in keys})

    def update(self, *args: Any, **kwargs: Any) -> D[K, V]:
        if len(args) % 2 != 0:
            raise ValueError(f"Even number of args required, missing value for: {args[-1]!r}")

        new_data = dict(self._data)
        for i in range(0, len(args), 2):
            new_data[args[i]] = self._apply_update(args[i], args[i + 1])
        for k, v in kwargs.items():
            key = cast(K, k)
            new_data[key] = self._apply_update(key, v)
        return D(new_data)

    def has(self, key: K) -> bool:
        return self._data.get(key) is not None

    def map_values(self, fn: Callable[[V], U]) -> D[K, U]:
        return D({k: fn(v) for k, v in self._data.items()})

    def map_keys(self, fn: Callable[[K], U]) -> D[U, V]:
        return D({fn(k): v for k, v in self._data.items()})

    def filter(self, predicate: Callable[[K, V], bool]) -> D[K, V]:
        return D({k: v for k, v in self._data.items() if predicate(k, v)})

    def filter_keys(self, predicate: Callable[[K], bool]) -> D[K, V]:
        return D({k: v for k, v in self._data.items() if predicate(k)})

    def filter_values(self, predicate: Callable[[V], bool]) -> D[K, V]:
        return D({k: v for k, v in self._data.items() if predicate(v)})

    def reduce(self, fn: Callable[[U, K, V], U], initial: U) -> U:
        return functools.reduce(lambda acc, kv: fn(acc, kv[0], kv[1]), self._data.items(), initial)

    def merge(self, other: D[K, V] | dict[K, V]) -> D[K, V]:
        return D({**self._data, **other})

    def select_keys(self, keys: Iterable[K]) -> D[K, V]:
        return D({k: v for k, v in self._data.items() if k in keys})

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: K) -> bool:
        return key in self._data

    def __getitem__(self, key: K) -> V:
        return self._data[key]

    def __iter__(self) -> Iterator[K]:
        return iter(self._data)

    def __repr__(self):
        return f"betterdict({dict(self._data)})"

    def __str__(self):
        return str(dict(self._data))
