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

import builtins, inspect, re

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

def _bool(s):
  if s.lower() in ('true', 'yes'):
    return True
  elif s.lower() in ('false', 'no'):
    return False
  else:
    raise Exception('invalid boolean value {!r}'.format(s))

class _type(type):
  def __new__(mcls, name, bases, namespace, **typeargs):
    return super().__new__(mcls, name, bases, namespace)
  def __init__(cls, name, bases, namespace, **typeargs):
    super().__init__(name, bases, namespace)
    cls.__classinit__(cls, **typeargs)
  def __call__(cls, *args, **kwargs):
    return cls.__new__(cls, *args, **kwargs)

class tuple(builtins.tuple, metaclass=_type):
  def __classinit__(cls, **types):
    cls.types = types
  def __new__(cls, *args, **types):
    if cls is tuple:
      cls = _type('tuple:' + ','.join(types), (tuple,), {}, **types)
    elif types:
      raise Exception('{} does not accept keyword arguments'.format(cls.__name__))
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

class struct(metaclass=_type):
  def __classinit__(cls, **defaults):
    self, *params = inspect.signature(cls.__init__).parameters.values()
    defaults.update({param.name: param.default for param in params if param.default is not param.empty})
    types = {name: default.__class__ for name, default in defaults.items()}
    types.update({param.name: param.annotation for param in params if param.annotation is not param.empty and callable(param.annotation)})
    cls._defaults = dict(getattr(cls.__base__, '_defaults', {}), **defaults)
    cls._types = dict(getattr(cls.__base__, '_types', {}), **types)
  def __new__(*cls_args, **kwargs):
    cls, *args = cls_args
    if cls is struct:
      if args:
        raise Exception('{} accepts only keyword arguments'.format(cls.__name__))
      cls = type('struct:' + ','.join(kwargs), (cls,), {}, **kwargs)
    if args:
      if len(args) != 1 or kwargs:
        raise Exception('{} expects either keyword arguments or a single positional string'.format(cls.__name__))
      for arg in safesplit(args[0], ','):
        key, sep, val = arg.partition('=')
        T = cls._types.get(key)
        if not T:
          raise TypeError('unexpected keyword argument {!r}'.format(key))
        if T is bool:
          T = _bool
        kwargs[key] = T(unprotect(val))
    self = object.__new__(cls)
    self._args = cls._defaults.copy()
    self._args.update(kwargs)
    self.__init__(**self._args)
    return self
  def __init__(self, **kwargs):
    self.__dict__.update(kwargs)
  def __str__(self):
    return ','.join('{}={}'.format(key, protect(self._types[key].__str__(value), ',')) for key, value in sorted(self._args.items()))

class choice(type):
  def __new__(mcls, name='choice', bases=(), namespace={}, **options):
    return super().__new__(mcls, name, bases, namespace)
  def __init__(cls, name='choice', bases=(), namespace={}, **options):
    super().__init__(name, bases, namespace)
    cls.options = options
    cls.__str__ = cls.__invcall__
  def __str__(cls):
    return '|'.join(sorted(cls.options))
  def __instancecheck__(cls, other):
    return any(val == arg or isinstance(val, type) and isinstance(arg, val) for val in options.values())
  def __invcall__(cls, obj):
    for key, val in cls.options.items():
      if val == obj:
        return key
      if isinstance(val, type) and isinstance(obj, val):
        return '{}:{}'.format(key, obj)
    raise Exception('unrecognized object {!r}'.format(obj))
  def __call__(cls, s):
    assert isinstance(s, str)
    key, sep, tail = s.partition(':')
    obj = cls.options[key]
    if isinstance(obj, type):
      obj = obj(tail)
    else:
      assert not sep
    return obj

class unit(float, metaclass=_type):
  _pattern = re.compile('([a-zA-Zα-ωΑ-Ω]+)')
  def __classinit__(cls, **units):
    remaining = {key: cls._pattern.findall(value) if isinstance(value, str) else 1 for key, value in units.items()}
    def depth(key):
      if key not in units:
        key = key[1:]
      d = remaining[key]
      if not isinstance(d, int):
        del remaining[key] # safeguard for circular refrences
        remaining[key] = d = sum(map(depth, d))
      return d
    cls._units = {}
    for key in sorted(remaining, key=depth):
      value = units[key]
      cls._units[key] = cls._parse(value) if isinstance(value, str) else (value, {key: 1})
  def __new__(cls, s):
    v, powers = cls._parse(s)
    if hasattr(cls, '_powers'):
      assert cls._powers == powers, 'invalid unit: expected {}, got {}'.format(cls._powers, powers)
    else: # create subtype, bypassing _type (and __classinit__) but using type instead
      cls = type.__new__(type, ''.join(str(s) for item in powers.items() for s in item), (cls,), dict(_powers=powers))
    self = float.__new__(cls, v)
    self._str = s
    return self
  @classmethod
  def _parse(cls, s, modifiers=dict(p=1e-9, μ=1e-6, m=1e-3, c=1e-2, d=1e-1, k=1e3, M=1e6, G=1e9)):
    parts = cls._pattern.split(s)
    value = float(parts[0].rstrip('*/') or 1)
    powers = {}
    for i in range(1, len(parts), 2):
      s = int(parts[i+1].rstrip('*/') or 1)
      if parts[i-1].endswith('/'):
        s = -s
      key = parts[i]
      if key not in cls._units:
        v, p = cls._units[key[1:]]
        v *= modifiers[key[0]]
      else:
        v, p = cls._units[key]
      value *= v**s
      powers.update({c: powers.get(c, 0) + n * s for c, n in p.items()})
    return value, {c: n for c, n in powers.items() if n}
  def __str__(self):
    return self._str
