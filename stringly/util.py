import itertools
import re
import textwrap
import typing
from . import error


def safesplit(s: str, sep: str, maxsplit: int = -1) -> typing.List[str]:
    if not s:
        return []
    parts: typing.List[str] = []
    level = 0
    for part in s.split(sep):
        if level or maxsplit >= 0 and len(parts) > maxsplit:
            parts[-1] += sep + part
        else:
            parts.append(part)
        level += part.count('{') - part.count('}')
    return parts

_bracepattern = re.compile(r'([\{\}])')
_prefixpattern = re.compile(r'^<\{*>')
_suffixpattern = re.compile(r'<\}*>$')


def protect_unconditionally(s: str) -> str:
    return _protect(s, lambda part: True)


def protect_unbalanced(s: str) -> str:
    return _protect(s, lambda part: False)


def protect_regex(s: str, regex: str) -> str:
    pattern = re.compile(regex)
    return _protect(s, lambda part: pattern.search(part) is not None)


def _protect(s: str, test: typing.Callable[[str], bool]) -> str:
    needsprotection = s.startswith('{') and s.endswith('}')
    # Determine the number of braces that need to be added to the left (`l`) and
    # right (`r`) to make `s` nonnegative and balanced. Furthermore, detect if
    # `test` is true at brace level (`n`) zero, in which case we need protection.
    l = n = 0
    for part in _bracepattern.split(s):
        if part == '{':
            n += 1
        elif part == '}':
            n -= 1
            l = max(l, -n)
        elif not needsprotection:
            needsprotection = n == 0 and test(part)
    r = n + l
    if needsprotection or l or r:
        # Prefix `s` with '<{{...{>' only if necessary to balance or to make
        # nonnegative (nonzero `l`) or if `s` starts with something that can be
        # parsed as a prefix (`_prefixpattern.search(s)`). Suffix following similar
        # rules.  Finally enclose in braces.
        return ('{<'+'{'*l+'>' if l or _prefixpattern.search(s) else '{') + s + ('<'+'}'*r+'>}' if r or _suffixpattern.search(s) else '}')
    else:
        return s

_protectedpattern = re.compile(r'\{(?:<\{*>)?(.*?)(?:<\}*>)?\}', flags=re.DOTALL)


def unprotect(s: str) -> str:
    m = _protectedpattern.fullmatch(s)
    return m.group(1) if m else s


def splitarg(s: str) -> typing.Tuple[str,str]:
    head, sep, tail = s.partition('{')
    if sep and not tail.endswith('}'):
        raise Exception(f'invalid joined argument {s!r}')
    return head, unprotect(sep + tail)


def prettify(s: str) -> str:
    return _prettify(s, '')


def _isnonnegativebalanced(s: str) -> bool:
    depths = tuple(itertools.accumulate(1 if b == '{' else -1 for b in _bracepattern.findall(s)))
    return not depths or all(depth >= 0 for depth in depths) and depths[-1] == 0


def _prettify(s: str, indent: str) -> str:
    pretty = ''
    for part in safesplit(s, ','):
        i = part.find('{')
        if i > 0 and part.endswith('}') and _isnonnegativebalanced(part[i+1:-1]):
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
                raise ValueError(f'line {i+1}: indentation should be two or more spaces but got one')
            s += '{'
            indents.append(indent)
        else:
            while indents and indents[-1] != indent:
                indents.pop()
                s += '}'
            if not indents or indent < indents[-1]:
                raise ValueError(f'line {i+1}: dedent does not match previous indentation')
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

    directives: typing.ClassVar[typing.Pattern[str]] = re.compile(r'^[.][.] (arguments|presets)::\n(.*?)(?:\n(?!(?:   | *\n))|\Z)', flags=re.MULTILINE | re.DOTALL)
    noindent: typing.ClassVar[typing.Pattern[str]] = re.compile(r'\n(?=\S)')

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
        p: typing.Dict[str, typing.Mapping[str, str]] = {}
        for name, body in self._directive('presets'):
            v: typing.Dict[str, str] = {}
            for si in safesplit(deprettify(body), ','):
                parts = safesplit(si, '=', 1)
                if len(parts) != 2:
                    raise error.SerializationError(f'preset {name!r} has not value for argument {unprotect(si)!r}')
                v[unprotect(parts[0])] = unprotect(parts[1])
            p[name] = v
        return p

    def __str__(self) -> str:
        return self._doc
