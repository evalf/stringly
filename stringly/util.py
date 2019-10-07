import typing, re, textwrap
from . import error

def safesplit(s: str, sep: str, maxsplit: int = -1) -> typing.List[str]:
  if not s:
    return []
  parts = [] # type: typing.List[str]
  level = 0
  for part in s.split(sep):
    if level or maxsplit >= 0 and len(parts) > maxsplit:
      parts[-1] += sep + part
    else:
      parts.append(part)
    level += part.count('{') - part.count('}')
  return parts

def isnormal(s: str) -> bool:
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

def escape(s: str) -> str:
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

def unescape(escaped: str) -> str:
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
    elif depth < 0:
      raise error.SerializationError('source string is not positive')
    s += c
  if depth != 0:
    raise error.SerializationError('source string is not balanced')
  return s

def protect(s: str, c: typing.Optional[str] = None) -> str:
  s = str(s)
  if c is None or not isnormal(s):
    return '{' + escape(s) + '}' # always embrace escaped strings to make them normal
  if s.startswith('{') and s.endswith('}'):
    return '{' + s + '}'
  n = 0
  for part in re.split(c, s)[:-1]:
    n += part.count('{') - part.count('}')
    if not n:
      return '{' + s + '}'
  return s

def unprotect(s: str) -> str:
  return unescape(s[1:-1] if s.startswith('{') and s.endswith('}') else s)

def splitarg(s: str) -> typing.Tuple[str,str]:
  head, sep, tail = s.partition('{')
  if sep and not tail.endswith('}'):
    raise Exception('invalid joined argument {!r}'.format(s))
  return head, unprotect(sep + tail)

def prettify(s: str) -> str:
  return _prettify(s, '')

def _prettify(s: str, indent: str) -> str:
  pretty = ''
  for part in safesplit(s, ','):
    i = part.find('{')
    if i > 0 and part.endswith('}') and isnormal(part[i+1:-1]):
      scope = _prettify(part[i+1:-1], indent+'  ')
      part = part[:i]
    else:
      scope = ''
    if part.startswith((' ', '>|')) or '\n' in part:
      pretty += indent+'>|'+part.replace('\n', '\n'+indent+' |')
    else:
      pretty += indent+part
    pretty += '\n'+scope
  return pretty

def deprettify(pretty: str) -> str:
  s = ''
  lines = pretty.split('\n')
  i = 0
  while i < len(lines):
    line = lines[i]
    if not line:
      i += 1
      continue
    indent = len(line) - len(line.lstrip(' '))
    if not s:
      indents = [indent]
    elif indent > indents[-1]:
      if indent - indents[-1] == 1:
        raise ValueError('line {}: indentation should be two or more spaces but got one'.format(i+1))
      s += '{'
      indents.append(indent)
    else:
      while indents and indents[-1] != indent:
        indents.pop()
        s += '}'
      if not indents or indent < indents[-1]:
        raise ValueError('line {}: dedent does not match previous indentation'.format(i+1))
      s += ','
    if line.startswith(' '*indent+'>|'):
      s += line[indent+2:]
      i += 1
      while i < len(lines) and lines[i].startswith(' '*indent+' |'):
        s += '\n'+lines[i][indent+2:]
        i += 1
    else:
      s += line[indent:]
      i += 1
  s += '}'*(len(indents)-1)
  return s

class DocString:
  directives = re.compile(r'^[.][.] (arguments|presets)::\n(.*?)(?:\n(?!(?:   | *\n))|\Z)', flags=re.MULTILINE|re.DOTALL) # type: typing.ClassVar[typing.Pattern[str]]
  noindent = re.compile(r'\n(?=\S)') # type: typing.ClassVar[typing.Pattern[str]]
  def __init__(self, f: typing.Callable[..., typing.Any]) -> None:
    head, sep, tail = (f.__doc__ or '').partition('\n')
    self._doc = (head + sep + textwrap.dedent(tail)).strip()
  def _directive(self, name: str) -> typing.List[typing.Tuple[str, str]]:
    return [item.partition('\n')[::2] for n, s in self.directives.findall(self._doc) if n == name for item in self.noindent.split(textwrap.dedent(s).lstrip('\n'))]
  @property
  def text(self) -> str:
    return '\n\n'.join(s.strip() for s in self.directives.split(self._doc)[::3] if s.strip())
  @property
  def defaults(self) -> typing.Mapping[str, str]:
    d = {}
    for name, body in self._directive('arguments'):
      if name.endswith(']'):
        k, v = name[:-1].split(' [', 1)
        d[k] = v
    return d
  @property
  def argdocs(self) -> typing.Mapping[str, str]:
    return {name.split(' [')[0] if name.endswith(']') else name: textwrap.dedent(body).rstrip() for name, body in self._directive('arguments')}
  @property
  def presets(self) -> typing.Mapping[str, typing.Mapping[str, str]]:
    p = {} # type: typing.Dict[str, typing.Mapping[str, str]]
    for name, body in self._directive('presets'):
      v = {} # type: typing.Dict[str, str]
      for si in safesplit(deprettify(body), ','):
        parts = safesplit(si, '=', 1)
        if len(parts) != 2:
          raise error.SerializationError('preset {!r} has not value for argument {!r}'.format(name, unprotect(si)))
        v[unprotect(parts[0])] = unprotect(parts[1])
      p[name] = v
    return p
  def __str__(self) -> str:
    return self._doc
