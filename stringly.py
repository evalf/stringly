# Copyright (c) 2018 Evalf
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

version = '1.0b0'

import builtins, inspect, collections

def safesplit(s, sep):
  if not s:
    return []
  parts = []
  level = 0
  for part in s.split(sep):
    if level:
      parts[-1] += sep + part
    else:
      parts.append(part)
    level += part.count('{') - part.count('}')
  return parts

def isnormal(s):
  'cheap algorithm to detect strings for which escape is an identity'
  depth = 0
  for part in s.split('{'):
    if depth == 1 and part.startswith('}'): # empty scope at level 0 requires escaping
      return False
    depth -= part.count('}')
    if depth < 0: # negative scope requires escaping
      return False
    depth += 1
  return depth == 1

def escape(s):
  'convert to a string with balanced braces and all non-brace characters in non-negative scope'
  if isnormal(s):
    return s
  disbalance = s.count('{') - s.count('}')
  depth = 0
  escaped = ''
  for c in s:
    if disbalance and depth == 0 and c == '{}'[disbalance<0]:
      c += '{}'[disbalance>0] # escape brace
      disbalance += 1 if disbalance<0 else -1 # reduce disbalance
    elif c == '{':
      depth += 1
      if depth <= 0:
        c = '{}' # escape opening brace
    elif c == '}':
      depth -= 1
      if depth < 0:
        c = '}{' # escape closing brace
      elif depth == 0 and escaped[-1] == '{': # empty scope at level 0
        c = '}}{' # escape existing opening brace and new closing brace
    escaped += c
  assert depth == disbalance == 0
  return escaped

def unescape(escaped):
  'inverse operation to escape'
  if isnormal(escaped):
    return escaped
  depth = 0
  s = ''
  for c in escaped:
    if c == '{':
      depth += 1
      if depth == 0 and s[-1] == '}':
        continue
    elif c == '}':
      depth -= 1
      if depth == 0 and s[-1] == '{':
        continue
    else:
      assert depth >= 0, 'source string is not positive'
    s += c
  assert depth == 0, 'source string is not balanced'
  return s

def protect(s, c):
  s = str(s)
  if not isnormal(s):
    return '{' + escape(s) + '}' # always embrace escaped strings to make them normal
  if s.startswith('{') and s.endswith('}'):
    return '{' + s + '}'
  n = 0
  for part in s.split(c)[:-1]:
    n += part.count('{') - part.count('}')
    if not n:
      return '{' + s + '}'
  return s

def unprotect(s):
  return unescape(s[1:-1] if s.startswith('{') and s.endswith('}') else s)

class booltype(type):
  def __instancecheck__(cls, other):
    return isinstance(other, builtins.bool)
  def __call__(cls, s):
    if s.lower() in ('true', 'yes'):
      return True
    elif s.lower() in ('false', 'no'):
      return False
    else:
      raise Exception('invalid boolean value {!r}'.format(s))

class bool(metaclass=booltype):
  __str__ = bool.__str__

class _type(type):
  def __new__(mcls, *args, **typeargs):
    return super().__new__(mcls, *args)
  def __init__(cls, *args, **typeargs):
    super().__init__(*args)
    cls.__classinit__(cls, **typeargs)
  def __call__(cls, *args, **kwargs):
    return cls.__new__(cls, *args, **kwargs)

class struct(metaclass=_type):
  def __classinit__(cls, **defaults):
    cls.defaults = defaults
  def __new__(cls, *args, **kwargs):
    assert cls is not struct
    if args:
      assert len(args) == 1
      for arg in safesplit(args[0], ','):
        key, sep, val = arg.partition('=')
        if key in kwargs:
          raise Exception('duplicate key {!r}'.format(key))
        kwargs[key] = unprotect(val)
    self = object.__new__(cls)
    self.__dict__.update(cls.defaults)
    for key, val in kwargs.items():
      try:
        defcls = cls.defaults[key].__class__
      except KeyError as e:
        raise TypeError('unexpected keyword argument {!r}'.format(key)) from e
      if not isinstance(val, defcls):
        val = defcls(val)
      self.__dict__[key] = val
    self.__init__()
    return self
  def __str__(self):
    return ','.join('{}={}'.format(key, protect(getattr(self, key), ',')) for key in self.__class__.defaults)
  @classmethod
  def inline(cls, **kwargs):
    return _type('<inline struct>', (cls,), {}, **kwargs)()

class tuple(builtins.tuple, metaclass=_type):
  def __classinit__(cls, **types):
    cls.types = types
  def __new__(cls, *args):
    assert cls is not tuple
    assert len(args) <= 1
    items = args and args[0]
    if isinstance(items, str):
      split = [item.partition(':')[::2] for item in safesplit(items, ',')]
      items = [cls.types[name](unprotect(args)) for name, args in split]
    self = builtins.tuple.__new__(cls, items)
    self.__init__()
    return self
  def __str__(self):
    clsname = {cls: name for name, cls in self.__class__.types.items()}
    return ','.join('{}:{}'.format(clsname[item.__class__], protect(item, ',')) for item in self)
  @staticmethod
  def inline(*args, **types):
    return _type('<inline tuple>', (tuple,), {}, **types)(*args)

class Immutable(metaclass=_type):
  def __classinit__(cls):
    _self, *params = inspect.signature(cls.__init__).parameters.values()
    cls._types = collections.OrderedDict()
    for param in params:
      if param.kind == param.POSITIONAL_ONLY:
        raise Exception('positional-only constructor argument in {}: {!r}'.format(cls.__name__, param.name))
      if param.annotation is not param.empty and callable(param.annotation):
        T = param.annotation
      elif param.default is not param.empty:
        T = param.default.__class__ if not isinstance(param.default, bool) else bool
      else:
        raise Exception('{} constructor argument without default or annotation: {!r}'.format(cls.__name__, param.name))
      cls._types[param.name] = T
  def __new__(*cls_args, **kwargs):
    cls, *args = cls_args
    if not args:
      _str = ','.join('{}={}'.format(name, protect(T.__str__(kwargs[name]), ',')) for name, T in cls._types.items() if name in kwargs)
    elif len(args) == 1 and not kwargs:
      _str, = args
      for arg in safesplit(_str, ','):
        key, sep, val = arg.partition('=')
        T = cls._types.get(key)
        if not T:
          raise TypeError('unexpected keyword argument {!r}'.format(key))
        kwargs[key] = T(unprotect(val))
    else:
      raise Exception('{} expects either keyword arguments or a single positional string'.format(cls.__name__))
    self = object.__new__(cls)
    self._str = _str # first set string representation in case the constructor hits an exception
    self.__init__(**kwargs)
    return self
  def __init__(self):
    raise Exception('Immutable base class cannot be instantiated')
  def __str__(self):
    return self._str

class choice:
  def __init__(self, **options):
    self.options = options
  def __call__(self, s):
    assert isinstance(s, str)
    key, sep, tail = s.partition(':')
    value = self.options[key]
    if isinstance(value, type):
      value = value(tail)
    else:
      assert not sep
    return value
  def __str__(self, *args):
    if not args:
      return '|'.join(sorted(self.options))
    arg, = args
    for key, val in self.options.items():
      if val == arg:
        return key
      if isinstance(val, type) and isinstance(arg, val):
        return '{}:{}'.format(key, arg)
    raise Exception('unrecognized object {!r}'.format(arg))

def _findfirst(iterable, items, complement=False):
  for index, item in enumerate(iterable):
    if (item in items)^complement:
      return index
  return len(iterable)

def _parse_unit(s, units, modifiers=dict(p=1e-9, μ=1e-6, m=1e-3, k=1e3, M=1e6, G=1e9)):
  i = _findfirst(s, '0123456789.', complement=True)
  value = float(s[:i] or 1)
  u = s[i:]
  powers = {}
  for mul in u.split('*'):
    s = +1
    for div in mul.split('/'):
      i = _findfirst(div, '0123456789')
      s *= int(div[i:] or 1)
      if div[:i] in units:
        v, p = units[div[:i]]
      else:
        v, p = units[div[1:i]]
        v *= modifiers[div[0]]
      value *= v**s
      for c, n in p.items():
        n = powers.pop(c, 0) + n * s
        if n:
          powers[c] = n
      s = -1
  return value, powers

class Unit(float):
  __slots__ = ()
  def __new__(cls, s):
    v, powers = _parse_unit(s, cls._units)
    if hasattr(cls, '_powers'):
      assert cls._powers == powers, 'invalid unit: expected {}, got {}'.format(cls._powers, powers)
    else:
      cls = type('Unit:' + ''.join(str(s) for item in powers.items() for s in item), (cls,), dict(__slots__='_str', _powers=powers))
    self = float.__new__(cls, v)
    self._str = s
    return self
  def __str__(self):
    return self._str

def create_unit(**units):
  remaining = []
  for key, value in units.items():
    if isinstance(value, str):
      remaining.append(key)
    else:
      assert not isinstance(value, builtins.tuple)
      units[key] = value, {key: 1}
  nmax = (len(remaining) * (len(remaining)+1)) // 2
  for key in remaining:
    assert nmax
    nmax -= 1
    try:
      units[key] = _parse_unit(units[key], units)
    except Exception as e:
      remaining.append(key)
  return type('<unit>', (Unit,), dict(__slots__=(), _units=units))
