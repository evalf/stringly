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

import builtins, inspect

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

class _noinit(type):
  def __call__(*args, **kwargs):
    return args[0].__new__(*args, **kwargs)

class struct(metaclass=_noinit):
  def __init_subclass__(cls, **defaults):
    super().__init_subclass__()
    self, *params = inspect.signature(cls.__init__).parameters.values()
    defaults.update({param.name: param.default for param in params if param.default is not param.empty})
    types = {name: default.__class__ for name, default in defaults.items()}
    types.update({param.name: param.annotation for param in params if param.annotation is not param.empty and callable(param.annotation)})
    if any(param.kind == param.VAR_KEYWORD for param in params) and hasattr(cls, '_types'):
      defaults = dict(cls._defaults, **defaults)
      types = dict(cls._types, **types)
    cls._defaults = defaults
    cls._types = types
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

class tuplemeta(type):
  def __new__(*args, **types):
    cls = type.__new__(*args)
    cls.types = types
    return cls
  def __init__(*args, **types):
    type.__init__(*args)
  def __call__(cls, *args, **types):
    if cls is tuple:
      name = '<tuple of {}>'.format(', '.join(types))
      return tuplemeta(name, (tuple,), {}, **types)(*args)
    assert not types and len(args) <= 1
    items = args and args[0]
    if isinstance(items, str):
      split = [item.partition(':')[::2] for item in safesplit(items, ',')]
      items = [cls.types[name](unprotect(args)) for name, args in split]
    self = builtins.tuple.__new__(cls, items)
    self.__init__()
    return self

class tuple(builtins.tuple, metaclass=tuplemeta, types=()):
  def __str__(self):
    clsname = {cls: name for name, cls in self.__class__.types.items()}
    return ','.join('{}:{}'.format(clsname[item.__class__], protect(item, ',')) for item in self)
