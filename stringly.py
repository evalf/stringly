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

def protect(part, c):
  levels = numpy.cumsum([s.count('{') - s.count('}') for s in part.split(c)])
  assert levels[-1] == 0 and min(levels) == 0
  return '{' + part + '}' if 0 in levels[:-1] else part

def unprotect(part):
  return part[1:-1] if part.startswith('{') and part.endswith('}') else part

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

class clstuplemeta(type):
  def __new__(*args, **types):
    cls = type.__new__(*args)
    cls.types = types
    return cls
  def __init__(*args, **types):
    type.__init__(*args)
  def __call__(cls, *args, **types):
    if cls is tuple:
      name = '<tuple of {}>'.format(', '.join(types))
      return clstuplemeta(name, (tuple,), {}, **types)(*args)
    assert not types and len(args) <= 1
    items = args and args[0]
    if isinstance(items, str):
      split = [item.partition(':')[::2] for item in safesplit(items, ',')]
      items = [cls.types[name](unprotect(args)) for name, args in split]
    self = builtins.tuple.__new__(cls, items)
    self.__init__()
    return self

class tuple(builtins.tuple, metaclass=clstuplemeta, types=()):
  def __str__(self):
    clsname = {cls: name for name, cls in self.__class__.types.items()}
    return ','.join('{}:{}'.format(clsname[item.__class__], protect(str(item), ',')) for item in self)
