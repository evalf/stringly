import typing, typing_extensions, decimal, enum, contextlib, inspect, sys, collections, itertools
from . import proto, util, error

if sys.version_info >= (3,7):
  import dataclasses
else:
  dataclasses = None

if sys.version_info >= (3,8):
  from typing import get_origin as typing_get_origin, get_args as typing_get_args
else:
  def typing_get_args(typ: typing.Any) -> typing.Tuple[typing.Type[typing.Any], ...]:
    args = getattr(typ, '__args__', ())
    if not isinstance(args, tuple):
      raise ValueError('expected __args__ to be a tuple but got {!r}'.format(args))
    return args
  if sys.version_info >= (3,7):
    def typing_get_origin(typ: typing.Any) -> typing.Optional[typing.Any]:
      return getattr(typ, '__origin__', None)
  else:
    def typing_get_origin(typ: typing.Any) -> typing.Optional[typing.Any]:
      origin = getattr(typ, '__origin__', None)
      if origin is typing.Dict:
        return dict
      elif origin is typing.Tuple:
        return tuple
      elif origin is typing.List:
        return list
      elif origin is typing.Set:
        return set
      elif origin is typing.FrozenSet:
        return frozenset
      else:
        return origin

T = typing.TypeVar('T')
K = typing.TypeVar('K')
V = typing.TypeVar('V')

@typing.overload
def get(t: typing.Type[T]) -> proto.Serializer[T]: ...
@typing.overload
def get(t: typing.Any) -> proto.Serializer[typing.Any]: ...

def get(t: typing.Any) -> proto.Serializer[typing.Any]:
  if hasattr(t, '__stringly_loads__') and hasattr(t, '__stringly_dumps__'):
    return Custom(t)
  if isinstance(t, type):
    if issubclass(t, bool):
      return Boolean()
    if issubclass(t, int):
      return Int()
    if issubclass(t, float):
      return Float()
    if issubclass(t, complex):
      return Complex()
    if issubclass(t, str):
      return String()
    if issubclass(t, decimal.Decimal):
      return Decimal()
    if issubclass(t, enum.Enum):
      return Enum(t)
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
        raise ValueError('duplicate names: {}'.format(', '.join(duplicate_nznames)))
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
  raise ValueError('unsupported type: {}'.format(t))

@contextlib.contextmanager
def loading(t: typing.Any, s: str, capture: typing.Type[Exception] = error.SerializationError) -> typing.Generator[None, None, None]:
  try:
    yield
  except capture as e:
    raise error.SerializationError('loading {!r} as {}: {}'.format(s, t, e)) from None

@contextlib.contextmanager
def dumping(t: typing.Any, v: typing.Any, capture: typing.Type[Exception] = error.SerializationError) -> typing.Generator[None, None, None]:
  try:
    yield
  except capture as e:
    raise error.SerializationError('dumping {!r} <{}> as {}: {}'.format(v, type(v).__name__, t, e)) from None

class Custom(typing.Generic[T]):
  def __init__(self, C: proto.Custom[T]) -> None:
    self.C = C
  def loads(self, s: str) -> T:
    with loading(self.C, s):
      return self.C.__stringly_loads__(s)
  def dumps(self, v: T) -> str:
    with dumping(self.C, v):
      return self.C.__stringly_dumps__(v)
  def __str__(self) -> str:
    return str(getattr(self.C, '__name__', self.C))

class Boolean:
  def loads(self, s: str) -> bool:
    with loading('bool', s):
      v = dict(true=True, yes=True, false=False, no=False).get(s.lower())
      if v is None:
        raise error.SerializationError('invalid boolean value')
      return v
  def dumps(self, v: bool) -> str:
    with dumping('bool', v):
      if not isinstance(v, bool):
        raise error.SerializationError('object is not an instance of bool')
      return bool.__str__(v)
  def __str__(self) -> str:
    return 'bool'

class Int:
  def loads(self, s: str) -> int:
    with loading('int', s, capture=ValueError):
      return int(s)
  def dumps(self, v: int) -> str:
    with dumping('int', v):
      if not isinstance(v, (bool, int)):
        raise error.SerializationError('object is not an instance of int or bool')
      return str(int(v))
  def __str__(self) -> str:
    return 'int'

class Float:
  def loads(self, s: str) -> float:
    with loading('float', s, capture=ValueError):
      return float(s)
  def dumps(self, v: float) -> str:
    with dumping('float', v):
      if not isinstance(v, (bool, int, float)):
        raise error.SerializationError('object is not an instance of float, int or bool')
      s = str(float(v))
      return s[:-2] if s.endswith('.0') else s
  def __str__(self) -> str:
    return 'float'

class Complex:
  def loads(self, s: str) -> complex:
    with loading('complex', s, capture=ValueError):
      return complex(s)
  def dumps(self, v: complex) -> str:
    with dumping('complex', v):
      if not isinstance(v, (bool, int, float, complex)):
        raise error.SerializationError('object is not an instance of complex, float, int or bool')
      s = str(complex(v)).lstrip('(').rstrip(')')
      return s[:-3] if s.endswith('+0j') else s[2:] if s.startswith('0+') else s
  def __str__(self) -> str:
    return 'complex'

class String:
  def loads(self, s: str) -> str:
    return s
  def dumps(self, v: str) -> str:
    with dumping('str', v):
      if not isinstance(v, str):
        raise error.SerializationError('object is not an instance of str')
      return v
  def __str__(self) -> str:
    return 'str'

class Decimal:
  def loads(self, s: str) -> decimal.Decimal:
    with loading('decimal.Decimal', s, capture=Exception):
      return decimal.Decimal(s)
  def dumps(self, v: decimal.Decimal) -> str:
    with dumping('decimal.Decimal', v):
      if not isinstance(v, decimal.Decimal):
        raise error.SerializationError('object is not an instance of Decimal')
      return str(v)
  def __str__(self) -> str:
    return 'decimal.Decimal'

class UniformTuple(typing.Generic[T]):
  def __init__(self, itemserializer: proto.Serializer[T]) -> None:
    self.itemserializer = itemserializer
  def loads(self, s: str) -> typing.Tuple[T,...]:
    with loading(self, s):
      parts = util.safesplit(s, ',')
      return tuple(self.itemserializer.loads(util.unprotect(si)) for si in parts)
  def dumps(self, v: typing.Tuple[T, ...]) -> str:
    with dumping(self, v):
      return ','.join(util.protect(self.itemserializer.dumps(vi), ',') or '{}' for vi in v)
  def __str__(self) -> str:
    return 'typing.Tuple[{}, ...]'.format(self.itemserializer)

class PluriformTuple:
  def __init__(self, itemserializers: typing.Tuple[proto.Serializer[typing.Any], ...]) -> None:
    self.itemserializers = itemserializers
  def loads(self, s: str) -> typing.Tuple[typing.Any, ...]:
    with loading(self, s):
      parts = util.safesplit(s, ',')
      if len(self.itemserializers) == len(parts):
        return tuple(zi.loads(util.unprotect(si)) for zi, si in zip(self.itemserializers, parts))
      raise error.SerializationError('tuple has incorrect length')
  def dumps(self, v: typing.Tuple[typing.Any, ...]) -> str:
    with dumping(self, v):
      if len(self.itemserializers) == len(v):
        return ','.join(util.protect(zi.dumps(vi), ',') or '{}' for zi, vi in zip(self.itemserializers, v))
      raise error.SerializationError('tuple has incorrect length')
  def __str__(self) -> str:
    return 'typing.Tuple[{}]'.format(', '.join(map(str, self.itemserializers)))

class Dict(typing.Generic[K, V]):
  def __init__(self, keyserializer: proto.Serializer[K], valueserializer: proto.Serializer[V]) -> None:
    self.keyserializer = keyserializer
    self.valueserializer = valueserializer
  def loads(self, s: str) -> typing.Dict[K, V]:
    with loading(self, s):
      v = {} # type: typing.Dict[K, V]
      for si in util.safesplit(s, ','):
        parts = util.safesplit(si, '=', 1)
        if len(parts) != 2:
          raise error.SerializationError('missing value')
        key, value = map(util.unprotect, parts)
        v[self.keyserializer.loads(key)] = self.valueserializer.loads(value)
      return v
  def dumps(self, v: typing.Dict[K, V]) -> str:
    with dumping(self, v):
      return ','.join(util.protect(self.keyserializer.dumps(vk), ',|=') + '=' + util.protect(self.valueserializer.dumps(vv), ',') for vk, vv in v.items())
  def __str__(self) -> str:
    return 'typing.Dict[{}, {}]'.format(self.keyserializer, self.valueserializer)

class Union:
  def __init__(self, serializers: typing.Mapping[str, proto.Serializer[typing.Any]]) -> None:
    self.serializers = serializers
  def loads(self, s: str) -> typing.Any:
    with loading(self, s):
      name, value = util.splitarg(s)
      if name not in self.serializers:
        raise error.SerializationError('unknown type: {}'.format(name))
      return self.serializers[name].loads(value)
  def dumps(self, v: typing.Any) -> str:
    with dumping(self, v):
      for name, serializer in self.serializers.items():
        try:
          s = serializer.dumps(v)
        except error.SerializationError:
          continue
        return name + util.protect(s) if s else name
      raise error.SerializationError('failed to find matching serializer')
  def __str__(self) -> str:
    return 'typing.Union[{}]'.format(', '.join(map(str, self.serializers.values())))

class Optional(typing.Generic[T]):
  def __init__(self, serializer: proto.Serializer[T]) -> None:
    self.serializer = serializer
  def loads(self, s: str) -> typing.Optional[T]:
    with loading(self, s):
      if s == '':
        return None
      return self.serializer.loads(util.unprotect(s))
  def dumps(self, v: typing.Optional[T]) -> str:
    with dumping(self, v):
      if v is None:
        return ''
      return self.serializer.dumps(v) or '{}'
  def __str__(self) -> str:
    return 'typing.Optional[{}]'.format(self.serializer)

class Sequence:
  def __init__(self, itemserializer: proto.Serializer[typing.Any], origin: typing.Any) -> None:
    self.itemserializer = itemserializer
    self.origin = origin
  def loads(self, s: str) -> typing.Any:
    with loading(self, s):
      return self.origin(self.itemserializer.loads(util.unprotect(si)) for si in util.safesplit(s, ','))
  def dumps(self, v: typing.Any) -> str:
    with dumping(self, v):
      return ','.join(util.protect(self.itemserializer.dumps(vi), ',') or '{}' for vi in v)
  def __str__(self) -> str:
    typename = {list: 'typing.List', set: 'typing.Set', frozenset: 'typing.FrozenSet'}[self.origin]
    return '{}[{}]'.format(typename, self.itemserializer)

enumT = typing.TypeVar('enumT', bound=enum.Enum)

class Enum(typing.Generic[enumT]):
  def __init__(self, cls: typing.Type[enumT]) -> None:
    self.cls = cls
  def loads(self, s: str) -> enumT:
    with loading(self, s):
      return self.cls.__members__[s]
  def dumps(self, v: enumT) -> str:
    with dumping(self, v):
      if not isinstance(v, self.cls):
        raise error.SerializationError('object is not an instance of type {}'.format(self.cls))
      return v.name
  def __str__(self) -> str:
    return str(getattr(self, '__name__', ''))

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
    self.serializers = [] # type: typing.List[proto.Serializer[T]]
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
        raise Exception('invalid function signature: type cannot be inferred for argument {!r}'.format(param.name))
      self.serializers.append(get(T))
  def loads(self, s: str) -> T:
    with loading(self.cls, s):
      args = self.defaults.copy()
      index = 0
      for si in util.safesplit(s, ','):
        parts = util.safesplit(si, '=', 1)
        if len(parts) == 2:
          name, value = map(util.unprotect, parts)
          try:
            index = self.argnames.index(name, self.npositional)
          except ValueError:
            raise error.SerializationError('invalid argument {!r}'.format(name)) from None
          args[index] = _strarg(value)
        elif index < self.npositional:
          args[index] = _strarg(util.unprotect(si))
          index += 1
        else:
          raise error.SerializationError('invalid expression')
      for i, arg in enumerate(args):
        if arg is inspect.Parameter.empty:
          raise error.SerializationError('missing mantatory argument {!r}'.format(self.argnames[i]))
        if isinstance(arg, _strarg):
          args[i] = self.serializers[i].loads(arg.value)
      return self.cls(*args[:self.npositional], **dict(zip(self.argnames[self.npositional:], args[self.npositional:]))) # type: ignore
  def dumps(self, v: T) -> str:
    with dumping(self.cls, v):
      if not isinstance(v, self.cls):
        raise error.SerializationError('object is not an instance of type {}'.format(self.cls))
      if hasattr(self.cls, '__getnewargs_ex__'):
        args, kwargs = self.cls.__getnewargs_ex__(v) # type: ignore
        assert len(args) + len(kwargs) == len(self.argnames)
        args += tuple(kwargs[name] for name in self.argnames[len(args):])
      elif hasattr(self.cls, '__getnewargs__'):
        args = self.cls.__getnewargs__(v) # type: ignore
        assert len(args) == len(self.argnames)
      elif dataclasses and dataclasses.is_dataclass(self.cls):
        args = tuple(getattr(v, name) for name in self.argnames)
      else:
        raise error.SerializationError('cannot dump {}'.format(v))
      return ','.join([util.protect(self.serializers[i].dumps(args[i]), '=') for i in range(self.npositional)]
                    + [util.protect(self.argnames[i], ',|=') + '=' + util.protect(self.serializers[i].dumps(args[i]), ',') for i in range(self.npositional, len(self.argnames))])
  def __str__(self) -> str:
    return str(getattr(self, '__name__', ''))
