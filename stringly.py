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

import builtins, inspect, re, sys, importlib, runpy, contextlib

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

def protect(s, c=None):
  s = str(s)
  if c is None or not isnormal(s):
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

def splitarg(s):
  head, sep, tail = s.partition('{')
  if sep and not tail.endswith('}'):
    raise Exception('invalid joined argument {!r}'.format(s))
  return head, unprotect(sep + tail)

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
  def __init_subclass__(cls):
    super().__init_subclass__()
    self, *cls._params = inspect.signature(cls.__init__).parameters.values()
    cls._defaults = {param.name: param.default for param in cls._params if param.default is not param.empty}
    cls._types = {key: value.__class__ for key, value in cls._defaults.items()}
  def __new__(*cls_args, **kwargs):
    cls, *args = cls_args
    if cls is struct:
      if args:
        raise Exception('{} accepts only keyword arguments'.format(cls.__name__))
      self = 'self'
      while self in kwargs:
        self += '_'
      __init__ = eval('lambda {0}, {1}: {0}.__dict__.update({1})'.format(self, ','.join(map('{0}={0}'.format, kwargs))), kwargs.copy())
      cls = type('struct:' + ','.join(kwargs), (cls,), builtins.dict(__init__=__init__))
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
    self._kwargs = kwargs
    self.__init__(**kwargs)
    return self
  def __str__(self):
    return ','.join('{}={}'.format(param.name, protect(self._kwargs.get(param.name, param.default), ',')) for param in self._params)

class tuple(builtins.tuple, metaclass=_noinit):
  def __init_subclass__(cls, **types):
    super().__init_subclass__()
    cls.types = types
  def __new__(cls, *args, **types):
    if cls is tuple:
      cls = type('tuple:' + ','.join(types), (tuple,), {}, **types)
    elif types:
      raise Exception('{} does not accept keyword arguments'.format(cls.__name__))
    assert len(args) <= 1
    items = args and args[0]
    if isinstance(items, str):
      split = map(splitarg, safesplit(items, ','))
      items = [cls.types[name](args) for name, args in split]
    self = builtins.tuple.__new__(cls, items)
    self.__init__(items)
    return self
  def __str__(self):
    clsname = {cls: name for name, cls in self.__class__.types.items()}
    return ','.join(clsname[item.__class__] + protect(item) for item in self)

class dict(builtins.dict, metaclass=_noinit):
  def __init_subclass__(cls, **types):
    super().__init_subclass__()
    cls.types = types
  def __new__(cls, *args, **types):
    if cls is dict:
      cls = type('dict:' + ','.join(types), (dict,), {}, **types)
    elif types:
      raise Exception('{} does not accept keyword arguments'.format(cls.__name__))
    assert len(args) <= 1
    if not args:
      items = []
    elif isinstance(args[0], str):
      items = []
      for item in safesplit(args[0], ','):
        key, nameargs = safesplit(item, '=')
        name, args = splitarg(nameargs)
        items.append([unprotect(key), cls.types[name](args)])
    else:
      items = args[0]
    self = builtins.dict.__new__(cls, items)
    self.__init__(items)
    return self
  def __str__(self):
    clsname = {cls: name for name, cls in self.__class__.types.items()}
    return ','.join('{}={}{}'.format(protect(key, '='), clsname[val.__class__], protect(val)) for key, val in self.items())

class choice(metaclass=_noinit):
  def __getattr__(self, attr): return getattr(self.value, attr)
  def __bool__(self): return bool(self.value)
  def __int__(self): return int(self.value)
  def __float__(self): return float(self.value)
  def __abs__(self): return abs(self.value)
  def __lt__(self, other): return self.value < other
  def __le__(self, other): return self.value <= other
  def __gt__(self, other): return self.value > other
  def __ge__(self, other): return self.value >= other
  def __eq__(self, other): return self.value == other
  def __ne__(self, other): return self.value != other
  def __getitem__(self, item): return self.value[item]
  def __call__(self, *args, **kwargs): return self.value(*args, **kwargs)
  def __init_subclass__(cls, **options):
    super().__init_subclass__()
    cls._options = options
  def __new__(*cls_s_args, **kwargs):
    cls, s, *args = cls_s_args
    assert isinstance(s, str)
    if cls is choice:
      cls = _noinit('|'.join(kwargs), (choice,), {}, **kwargs)
      kwargs = {}
    key, arg = splitarg(s)
    obj = cls._options[key]
    if isinstance(obj, type):
      if args or kwargs:
        assert not arg
      else:
        args = arg,
      if obj is bool:
        obj = _bool
      obj = obj(*args, **kwargs)
    else:
      assert not arg and not args and not kwargs
    self = object.__new__(cls)
    self.key = key
    self.value = obj
    return self
  def __str__(self):
    return self.key + protect(self.value) if isinstance(self._options[self.key], type) else self.key

class unit(float, metaclass=_noinit):
  _pattern = re.compile('([a-zA-Zα-ωΑ-Ω]+)')
  def __init_subclass__(cls, **units):
    super().__init_subclass__()
    if not units:
      return
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
    else:
      cls = type(''.join(str(s) for item in powers.items() for s in item), (cls,), builtins.dict(_powers=powers))
    self = float.__new__(cls, v)
    self._str = s
    return self
  @classmethod
  def _parse(cls, s, modifiers=builtins.dict(p=1e-9, μ=1e-6, m=1e-3, c=1e-2, d=1e-1, k=1e3, M=1e6, G=1e9)):
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

class ImportFunctionError(Exception): pass

def import_function(funcpath):
  if ':' in funcpath:
    script, funcname = funcpath.rsplit(':', 1)
    ns = runpy.run_path(script, run_name='<stringly.import_function>')
    try:
      func = ns[funcname]
    except KeyError as e:
      raise ImportFunctionError('no such function in script {}: {}'.format(script, funcname)) from e
  else:
    parts = funcpath.split('.')
    for i in range(1, len(parts)):
      mod = importlib.import_module('.'.join(parts[:i]))
      try:
        func = getattr(mod, '.'.join(parts[i:]))
        break
      except AttributeError:
        pass
    else:
      raise ImportFunctionError('no such function: {}'.format(funcpath))
  if not callable(func):
    raise ImportFunctionError('function {!r} is not callable'.format(funcpath))
  return func

def _run(func=None, argv=None):
  if argv is None:
    argv = sys.argv

  if func is None:
    argv.pop(0)
    try:
      func = import_function(argv[0])
    except ImportFunctionError as e:
      print(e, file=sys.stderr)
      raise SystemExit(1) from e
  else:
    if not callable(func):
      raise ValueError("'func' is not callable")

  types = {}
  mandatory = set()

  sig = inspect.signature(func)
  for name, param in sig.parameters.items():
    if param.kind == param.POSITIONAL_ONLY:
      raise NotImplementedError
    elif param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY):
      if param.default != param.empty:
        arg_type = type(param.default)
      elif param.annotation != param.empty:
        arg_type = param.annotation
        mandatory.add(name)
      else:
        raise ValueError
      if arg_type == bool:
        arg_type = _bool
      types[name] = arg_type
    elif param.kind == param.VAR_POSITIONAL:
      raise ValueError('var positional arguments are not supported')
    else:
      raise NotImplementedError

  args =[]
  kwargs = {}
  for arg in argv[1:]:
    k, sep, v = arg.partition('=')
    if k not in types:
      print('unexpected argument {!r}'.format(k), file=sys.stderr)
      raise SystemExit(1)
    if not sep:
      print('argument {!r} requires a value'.format(k), file=sys.stderr)
      raise SystemExit(1)
    kwargs[k] = types[k](v)
  missing = set(mandatory) - set(kwargs)
  if missing:
    print('missing required argument(s): {}'.format(','.join(missing)), file=sys.stderr)
    raise SystemExit(1)

  func(*args, **kwargs)

def run(func, argv=None):
  _run(func=func, argv=argv)

if __name__ == '__main__':
  _run()
