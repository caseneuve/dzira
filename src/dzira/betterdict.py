from typing import Iterable


class D(dict):
    def __call__(self, *keys) -> Iterable:
        if keys:
            return [self.get(*k) if isinstance(k, tuple) else self.get(k) for k in keys]
        else:
            return self.values()

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'D' object has no attribute {key!r}")

    def _update(self, k, v):
        self[k] = v(self.get(k)) if callable(v) else v

    def update(self, *args, **kwargs):
        if len(args) % 2 != 0:
            raise Exception(
                f"Provide even number of key-value args, need a value for key: {args[-1]!r}"
            )
        for i in range(0, len(args), 2):
            self._update(args[i], args[i + 1])
        for k, v in kwargs.items():
            self._update(k, v)
        return self

    def has(self, k):
        return self.get(k) is not None

    def without(self, *args):
        return D({k: v for k, v in self.items() if k not in args})

    def __repr__(self):
        return f"betterdict({dict(self)})"

    def __str__(self):
        return str(dict(self))
