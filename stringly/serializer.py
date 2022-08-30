import collections
import contextlib
import dataclasses
import decimal
import enum
import inspect
import itertools
import pathlib
import typing
from typing_extensions import get_origin as typing_get_origin, get_args as typing_get_args
from . import proto, util, error

T = typing.TypeVar('T')
K = typing.TypeVar('K')
V = typing.TypeVar('V')


@typing.overload
def get(t: typing.Type[T]) -> proto.Serializer[T]:
    ...
@typing.overload
def get(t: typing.Any) -> proto.Serializer[typing.Any]:
    ...
def get(t: typing.Any) -> proto.Serializer[typing.Any]:
    if hasattr(t, '__stringly_loads__') and hasattr(t, '__stringly_dumps__'):
        return Custom(t)
    if isinstance(t, type):
        if t is bool:
            return Boolean()
        if t is int:
            return Native(t, alt=(bool,))
        if t is float:
            return Native(t, alt=(int, bool), trim=(('', '.0'),))
        if t is complex:
            return Native(t, alt=(float, int, bool), trim=(('(', ')'), ('', '+0j')))
        if t in (str, decimal.Decimal, pathlib.Path):
            return Native(t)
        if issubclass(t, enum.Enum):
            return Enum(t)
        if t is tuple:
            raise ValueError('cannot serialize tuple; use typing.Tuple[] instead')
        if t is list:
            raise ValueError('cannot serialize list; use typing.List[] instead')
        if t is set:
            raise ValueError('cannot serialize set; use typing.Set[] instead')
        if t is frozenset:
            raise ValueError('cannot serialize frozenset; use typing.FrozenSet[] instead')
        if t is dict:
            raise ValueError('cannot serialize dict; use typing.Dict[] instead')
    origin = typing_get_origin(t)
    if origin:
        args = typing_get_args(t)
        if origin is tuple:
            if args[1:] == (...,):
                return UniformTuple(get(args[0]))
            else:
                return PluriformTuple(tuple(map(get, args)))
        if origin is dict:
            return Dict(*map(get, args))
        if origin is typing.Union:
            nzargs = tuple(arg for arg in args if arg is not type(None))
            nznames = tuple(arg.__name__ for arg in nzargs)
            nzserializers = tuple(map(get, nzargs))
            duplicate_nznames = [name for name, g in itertools.groupby(sorted(nznames)) if len(list(g)) > 1]
            if duplicate_nznames:
                raise ValueError(f'duplicate names: {", ".join(duplicate_nznames)}')
            if len(nzargs) == len(args):
                return Union(collections.OrderedDict(zip(nznames, nzserializers)))
            elif len(nzargs) == 1:
                return Optional(nzserializers[0])
            else:
                return Optional(Union(collections.OrderedDict(zip(nznames, nzserializers))))
        if any(origin is typ for typ in (list, set, frozenset)): # in Python <= 3.5 `origin in (list, set, frozenset)` fails
            assert len(args) == 1
            return Sequence(get(args[0]), origin)
    if callable(t):
        return Generic(t)
    raise ValueError(f'unsupported type: {t}')


def _assert_isinstance(v, *types):
    if not isinstance(v, types):
        raise error.SerializationError(f'{v} <{type(v).__qualname__}> is not an instance of {" or ".join(T.__qualname__ for T in types)}')


class Custom(typing.Generic[T]):
    def __init__(self, C: proto.Custom[T]) -> None:
        self.C = C

    def loads(self, s: str) -> T:
        return self.C.__stringly_loads__(s)

    def dumps(self, v: T) -> str:
         return self.C.__stringly_dumps__(v)

    def __str__(self) -> str:
        return str(getattr(self.C, '__name__', self.C))


class Boolean:
    def loads(self, s: str) -> bool:
        v = dict(true=True, yes=True, false=False, no=False).get(s.lower())
        if v is None:
            raise error.SerializationError(f'invalid boolean value {s!r}')
        return v

    def dumps(self, v: bool) -> str:
        _assert_isinstance(v, bool)
        return bool.__str__(v)

    def __str__(self) -> str:
        return 'bool'


class Native:
    def __init__(self, T, alt=(), trim=()):
        self.T = T
        self.alt = alt
        self.trim = trim

    def loads(self, s: str) -> int:
        try:
            v = self.T(s)
        except Exception as e:
            raise error.SerializationError(e)
        return v

    def dumps(self, v):
        _assert_isinstance(v, self.T, *self.alt)
        s = str(self.T(v))
        for prefix, suffix in self.trim:
            if s.startswith(prefix) and s.endswith(suffix):
                s = s[len(prefix):len(s)-len(suffix)]
        return s

    def __str__(self):
        return self.T.__qualname__


class UniformTuple(typing.Generic[T]):
    def __init__(self, itemserializer: proto.Serializer[T]) -> None:
        self.itemserializer = itemserializer

    def loads(self, s: str) -> typing.Tuple[T,...]:
        parts = util.safesplit(s, ',')
        return tuple(self.itemserializer.loads(util.unprotect(si)) for si in parts)

    def dumps(self, v: typing.Tuple[T, ...]) -> str:
        return ','.join(util.protect_regex(self.itemserializer.dumps(vi), ',') or '{}' for vi in v)

    def __str__(self) -> str:
        return f'typing.Tuple[{self.itemserializer}, ...]'


class PluriformTuple:
    def __init__(self, itemserializers: typing.Tuple[proto.Serializer[typing.Any], ...]) -> None:
        self.itemserializers = itemserializers

    def loads(self, s: str) -> typing.Tuple[typing.Any, ...]:
        parts = util.safesplit(s, ',')
        if len(self.itemserializers) == len(parts):
            return tuple(zi.loads(util.unprotect(si)) for zi, si in zip(self.itemserializers, parts))
        raise error.SerializationError('tuple has incorrect length')

    def dumps(self, v: typing.Tuple[typing.Any, ...]) -> str:
        if len(self.itemserializers) == len(v):
            return ','.join(util.protect_regex(zi.dumps(vi), ',') or '{}' for zi, vi in zip(self.itemserializers, v))
        raise error.SerializationError('tuple has incorrect length')

    def __str__(self) -> str:
        return f'typing.Tuple[{", ".join(map(str, self.itemserializers))}]'


class Dict(typing.Generic[K, V]):
    def __init__(self, keyserializer: proto.Serializer[K], valueserializer: proto.Serializer[V]) -> None:
        self.keyserializer = keyserializer
        self.valueserializer = valueserializer

    def loads(self, s: str) -> typing.Dict[K, V]:
        v: typing.Dict[K, V] = {}
        for si in util.safesplit(s, ','):
            parts = util.safesplit(si, '=', 1)
            if len(parts) != 2:
                raise error.SerializationError('missing value')
            key, value = map(util.unprotect, parts)
            v[self.keyserializer.loads(key)] = self.valueserializer.loads(value)
        return v

    def dumps(self, v: typing.Dict[K, V]) -> str:
        return ','.join(util.protect_regex(self.keyserializer.dumps(vk), ',|=') + '=' + util.protect_regex(self.valueserializer.dumps(vv), ',') for vk, vv in v.items())

    def __str__(self) -> str:
        return f'typing.Dict[{self.keyserializer}, {self.valueserializer}]'


class Union:
    def __init__(self, serializers: typing.Mapping[str, proto.Serializer[typing.Any]]) -> None:
        self.serializers = serializers

    def loads(self, s: str) -> typing.Any:
        name, value = util.splitarg(s)
        if name not in self.serializers:
            raise error.SerializationError(f'unknown type: {name}')
        return self.serializers[name].loads(value)

    def dumps(self, v: typing.Any) -> str:
        for name, serializer in self.serializers.items():
            try:
                s = serializer.dumps(v)
            except error.SerializationError:
                continue
            return name + util.protect_unconditionally(s) if s else name
        raise error.SerializationError('failed to find matching serializer')

    def __str__(self) -> str:
        return f'typing.Union[{", ".join(map(str, self.serializers.values()))}]'


class Optional(typing.Generic[T]):
    def __init__(self, serializer: proto.Serializer[T]) -> None:
        self.serializer = serializer

    def loads(self, s: str) -> typing.Optional[T]:
        if s == '':
            return None
        return self.serializer.loads(util.unprotect(s))

    def dumps(self, v: typing.Optional[T]) -> str:
        if v is None:
            return ''
        s = self.serializer.dumps(v)
        return util.protect_unconditionally(s) if s.startswith('{') and s.endswith('}') or not s else s

    def __str__(self) -> str:
        return f'typing.Optional[{self.serializer}]'


class Sequence:
    def __init__(self, itemserializer: proto.Serializer[typing.Any], origin: typing.Any) -> None:
        self.itemserializer = itemserializer
        self.origin = origin

    def loads(self, s: str) -> typing.Any:
        return self.origin(self.itemserializer.loads(util.unprotect(si)) for si in util.safesplit(s, ','))

    def dumps(self, v: typing.Any) -> str:
        return ','.join(util.protect_regex(self.itemserializer.dumps(vi), ',') or '{}' for vi in v)

    def __str__(self) -> str:
        typename = {list: 'typing.List', set: 'typing.Set', frozenset: 'typing.FrozenSet'}[self.origin]
        return f'{typename}[{self.itemserializer}]'

enumT = typing.TypeVar('enumT', bound=enum.Enum)


class Enum(typing.Generic[enumT]):
    def __init__(self, cls: typing.Type[enumT]) -> None:
        self.cls = cls

    def loads(self, s: str) -> enumT:
        return self.cls.__members__[s]

    def dumps(self, v: enumT) -> str:
        _assert_isinstance(v, self.cls)
        return v.name

    def __str__(self) -> str:
        return str(getattr(self.cls, '__name__', ''))


class _strarg:
    def __init__(self, value: str) -> None:
        self.value = value


class Generic(typing.Generic[T]):
    def __init__(self, cls: typing.Type[T]) -> None:
        self.cls = cls
        params = inspect.signature(cls).parameters
        defaults = util.DocString(cls).defaults
        self.argnames = tuple(params)
        self.defaults = [_strarg(defaults[name]) if name in defaults else params[name].default for name in self.argnames]
        self.npositional = 0
        self.serializers: typing.List[proto.Serializer[T]] = []
        for param in params.values():
            if param.kind is param.POSITIONAL_ONLY:
                if self.npositional < len(self.serializers):
                    raise Exception('invalid function signature: keyword argument followed by positional argument')
                self.npositional += 1
            elif param.kind not in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
                raise Exception('invalid function signature: variable arguments are not supported')
            if param.annotation is not param.empty:
                T = param.annotation
            elif param.default is not param.empty:
                T = type(param.default)
            else:
                raise Exception(f'invalid function signature: type cannot be inferred for argument {param.name!r}')
            self.serializers.append(get(T))

    def loads(self, s: str) -> T:
        args = self.defaults.copy()
        if not s:
            pass
        elif len(self.argnames) == 1:
            if not self.npositional:
                parts = util.safesplit(s, '=', 1)
                if len(parts) != 2 or parts[0] != self.argnames[0]:
                    raise error.SerializationError(f'invalid argument {parts[0]!r}') from None
                s = parts[1]
            args[0] = _strarg(util.unprotect(s))
        else:
            index = 0
            for si in util.safesplit(s, ','):
                parts = util.safesplit(si, '=', 1)
                if len(parts) == 2:
                    name, value = map(util.unprotect, parts)
                    try:
                        index = self.argnames.index(name, self.npositional)
                    except ValueError:
                        raise error.SerializationError(f'invalid argument {name!r}') from None
                    args[index] = _strarg(value)
                elif index < self.npositional:
                    args[index] = _strarg(util.unprotect(si))
                    index += 1
                else:
                    raise error.SerializationError('invalid expression')
        for i, arg in enumerate(args):
            if arg is inspect.Parameter.empty:
                raise error.SerializationError(f'missing mantatory argument {self.argnames[i]!r}')
            if isinstance(arg, _strarg):
                args[i] = self.serializers[i].loads(arg.value)
        return self.cls(*args[:self.npositional], **dict(zip(self.argnames[self.npositional:], args[self.npositional:])))

    def dumps(self, v: T) -> str:
        _assert_isinstance(v, self.cls)
        if hasattr(self.cls, '__getnewargs_ex__'):
            args, kwargs = self.cls.__getnewargs_ex__(v) # type: ignore
            assert len(args) + len(kwargs) == len(self.argnames)
            args += tuple(kwargs[name] for name in self.argnames[len(args):])
        elif hasattr(self.cls, '__getnewargs__'):
            args = self.cls.__getnewargs__(v) # type: ignore
            assert len(args) == len(self.argnames)
        elif dataclasses.is_dataclass(self.cls):
            args = tuple(getattr(v, name) for name in self.argnames)
        else:
            raise error.SerializationError(f'cannot dump {v}')
        dumps = [serializer.dumps(arg) for serializer, arg in zip(self.serializers, args)]
        if len(self.argnames) == 1:
            return util.protect_unbalanced(dumps[0]) or '{}' if self.npositional \
              else util.protect_regex(self.argnames[0], '=') + '=' + util.protect_unbalanced(dumps[0])
        else:
            return ','.join(util.protect_regex(dumps[i], ',') if i < self.npositional
              else util.protect_regex(self.argnames[i], ',|=') + '=' + util.protect_regex(dumps[i], ',') for i in range(len(self.argnames)))

    def __str__(self) -> str:
        return str(getattr(self.cls, '__name__', repr(self.cls)))
