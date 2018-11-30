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

import builtins

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

class structmeta(type):
  def __new__(*args, **defaults):
    cls = type.__new__(*args)
    cls.defaults = defaults
    return cls
  def __init__(*args, **defaults):
    type.__init__(*args)
  def __call__(cls, *args, **kwargs):
    if args:
      assert len(args) == 1 and not kwargs
      for arg in safesplit(args[0], ','):
        key, sep, val = arg.partition('=')
        kwargs[key] = unprotect(val)
    if cls is struct:
      # direct invocation of struct returns an automatically generated subtype
      name = '<struct of {}>'.format(', '.join(kwargs))
      return structmeta(name, (cls,), {}, **kwargs)()
    self = object.__new__(cls)
    self.__dict__.update(cls.defaults)
    for key, val in kwargs.items():
      try:
        defcls = cls.defaults[key].__class__
      except KeyError:
        raise TypeError('unexpected keyword argument {!r}'.format(key))
      if not isinstance(val, defcls):
        val = defcls(val)
      self.__dict__[key] = val
    self.__init__()
    return self

class struct(metaclass=structmeta):
  def __str__(self):
    return ','.join('{}={}'.format(key, protect(str(getattr(self, key)), ',')) for key in self.__class__.defaults)

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
    return ','.join('{}:{}'.format(clsname[item.__class__], protect(str(item), ',')) for item in self)
