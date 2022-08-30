import dataclasses
import decimal
import enum
import pathlib
import stringly
import sys
import textwrap
import typing
import unittest


class Protect(unittest.TestCase):

    def assertProtected(self, orig, checkprotected=None, sep=','):
        if sep is None:
            protected = stringly.util.protect_unconditionally(orig)
        else:
            protected = stringly.util.protect_regex(orig, sep)
            self.assertEqual(stringly.util.safesplit(protected, sep), [protected] if orig else [])
        if checkprotected is not None:
            self.assertEqual(protected, checkprotected)
        self.assertEqual(stringly.util.unprotect(protected), orig)

    def assertNormal(self, s):
        sep = ','
        assert sep not in s
        self.assertProtected(s, s, sep=sep)
        self.assertProtected(s, '{'+s+'}', sep=None)

    def assertNormalUnlessUnconditionalProtection(self, s, protected):
        sep = ','
        assert sep not in s
        self.assertProtected(s, s, sep=sep)
        self.assertProtected(s, protected, sep=None)

    def test_combinations(self):
        for length in range(6):
            for i in range(4**length):
                self.assertProtected(''.join('{}<>'[i>>2*j&0b11] for j in range(length)))
                self.assertProtected(''.join('{}<>'[i>>2*j&0b11] for j in range(length)), sep=None)
        for length in range(6):
            for i in range(4**length):
                self.assertProtected(''.join('{},x'[i>>(j*2)&3] for j in range(length)))

    def test_normality(self):
        self.assertNormal('')
        self.assertNormal('abc')
        self.assertNormal('ab{cd}ef')
        self.assertNormal('<abc>')
        self.assertNormal('<abc></abc>')
        self.assertNormal('<{}>')
        self.assertNormal('a\nb')

    def test_protection(self):
        self.assertProtected('abc,def', '{abc,def}')
        self.assertProtected('ab{c,d}ef', 'ab{c,d}ef')
        self.assertProtected('a{b,c}d,ef', '{a{b,c}d,ef}')

    def test_braces(self):
        self.assertProtected('{abc}', '{{abc}}')
        self.assertProtected('{abc{', '{{abc{<}}>}')
        self.assertProtected('}abc}', '{<{{>}abc}}')
        self.assertProtected('}abc{', '{<{>}abc{<}>}')
        self.assertProtected('}abc', '{<{>}abc}')
        self.assertProtected('abc{', '{abc{<}>}')
        self.assertProtected('abc}def', '{<{>abc}def}')
        self.assertProtected('abc{def', '{abc{def<}>}')
        self.assertProtected('a{bc}de{f', '{a{bc}de{f<}>}')
        self.assertProtected('a}bc{de}f', '{<{>a}bc{de}f}')

    def test_header_footer(self):
        self.assertNormalUnlessUnconditionalProtection('<>', '{<><><>}')
        self.assertNormalUnlessUnconditionalProtection('a<>', '{a<><>}')
        self.assertNormalUnlessUnconditionalProtection('<>a', '{<><>a}')
        self.assertNormalUnlessUnconditionalProtection('<{><}>', '{<><{><}><>}')
        self.assertNormalUnlessUnconditionalProtection('<{{><}}>', '{<><{{><}}><>}')
        self.assertProtected('<{>', '{<><{><}>}')
        self.assertProtected('<}>', '{<{><}><>}')
        self.assertProtected('<{{>', '{<><{{><}}>}')
        self.assertProtected('<}}>', '{<{{><}}><>}')
        self.assertProtected('<>,', '{<><>,}')
        self.assertProtected(',<>', '{,<><>}')
        self.assertProtected('<>,<>', '{<><>,<><>}')


class PrettifyUglify(unittest.TestCase):

    def check(self, s, pretty):
        self.assertEqual(stringly.util.prettify(s), pretty)
        self.assertEqual(stringly.util.deprettify(pretty), s)

    def test_normal(self):
        self.check('a=1,b=c', 'a=1\nb=c\n')
        self.check('a=b{c,d}', 'a=b\n  c\n  d\n')
        self.check('a=b{c=d,e{f,g}},h=i', 'a=b\n  c=d\n  e\n    f\n    g\nh=i\n')

    def test_leading_whitespace(self):
        self.check(' ', '>| \n')
        self.check(' a', '>| a\n')
        self.check('a={ ,c}', 'a=\n  >| \n  c\n')

    def test_newline(self):
        self.check('\n', '>|\n |\n')
        self.check('\na', '>|\n |a\n')
        self.check('a={\n,c}', 'a=\n  >|\n   |\n  c\n')

    def test_startswith_escape(self):
        self.check('>|', '>|>|\n')

    def test_startswith_continuation(self):
        self.check(' >', '>| >\n')

    def test_consecutive_escape(self):
        self.check('a={ b,\nc}', 'a=\n  >| b\n  >|\n   |c\n')

    def test_escape_indent(self):
        self.check('a={ b{c},d}', 'a=\n  >| b\n    c\n  d\n')

    def test_double_scope(self):
        self.check('a{b}c{d}', 'a{b}c{d}\n')

    def test_all_indented(self):
        self.assertEqual(stringly.util.deprettify('  a=b\n  c=\n    d\n'), 'a=b,c={d}')

    def test_invalid_dedent(self):
        with self.assertRaisesRegex(ValueError, 'line 3: dedent does not match previous indentation'):
            stringly.util.deprettify('a=\n  b\n c\n')

    def test_invalid_indent(self):
        with self.assertRaisesRegex(ValueError, 'line 2: indentation should be two or more spaces but got one'):
            stringly.util.deprettify('a=\n b\n')
        with self.assertRaisesRegex(ValueError, 'line 3: indentation should be two or more spaces but got one'):
            stringly.util.deprettify('a=\n  >|\n   b\n')


class Bool(unittest.TestCase):

    def test_loads(self):
        self.assertEqual(stringly.loads(bool, 'True'), True)
        self.assertEqual(stringly.loads(bool, 'true'), True)
        self.assertEqual(stringly.loads(bool, 'yes'), True)
        self.assertEqual(stringly.loads(bool, 'YES'), True)
        self.assertEqual(stringly.loads(bool, 'False'), False)
        self.assertEqual(stringly.loads(bool, 'false'), False)
        self.assertEqual(stringly.loads(bool, 'no'), False)
        self.assertEqual(stringly.loads(bool, 'NO'), False)

    def test_dumps(self):
        self.assertEqual(stringly.dumps(bool, True), 'True')
        self.assertEqual(stringly.dumps(bool, False), 'False')

    def test_serializer(self):
        s = stringly.serializer.get(bool)
        self.assertIsInstance(s, stringly.serializer.Boolean)
        self.assertEqual(str(s), 'bool')


class Int(unittest.TestCase):

    def test_loads(self):
        self.assertEqual(stringly.loads(int, '1'), 1)
        with self.assertRaises(stringly.error.SerializationError):
            stringly.loads(int, '1.')
        with self.assertRaises(stringly.error.SerializationError):
            stringly.loads(int, '1a')

    def test_dumps_bool(self):
        self.assertEqual(stringly.dumps(int, True), '1')

    def test_dumps_int(self):
        self.assertEqual(stringly.dumps(int, 1), '1')

    def test_dumps_float(self):
        with self.assertRaisesRegex(stringly.error.SerializationError, '1.0 <float> is not an instance of int or bool'):
            stringly.dumps(int, 1.0)

    def test_dumps_complex(self):
        with self.assertRaisesRegex(stringly.error.SerializationError, '1j <complex> is not an instance of int or bool'):
            stringly.dumps(int, 1j)

    def test_serializer(self):
        s = stringly.serializer.get(int)
        self.assertIsInstance(s, stringly.serializer.Native)
        self.assertEqual(str(s), 'int')


class Float(unittest.TestCase):

    def test_loads(self):
        self.assertEqual(stringly.loads(float, '1'), 1)
        with self.assertRaises(stringly.error.SerializationError):
            stringly.loads(float, '1a')

    def test_dumps_bool(self):
        self.assertEqual(stringly.dumps(float, True), '1')

    def test_dumps_int(self):
        self.assertEqual(stringly.dumps(float, 1), '1')

    def test_dumps_float(self):
        self.assertEqual(stringly.dumps(float, 1.0), '1')
        self.assertEqual(stringly.dumps(float, 1.2), '1.2')
        self.assertEqual(stringly.dumps(float, 0.2), '0.2')

    def test_dumps_complex(self):
        with self.assertRaisesRegex(stringly.error.SerializationError, '1j <complex> is not an instance of float or int or bool'):
            stringly.dumps(float, 1j)

    def test_serializer(self):
        s = stringly.serializer.get(float)
        self.assertIsInstance(s, stringly.serializer.Native)
        self.assertEqual(str(s), 'float')


class Complex(unittest.TestCase):

    def test_loads(self):
        self.assertEqual(stringly.loads(complex, '1+2j'), 1+2j)
        with self.assertRaises(stringly.error.SerializationError):
            stringly.loads(complex, '1a')

    def test_dumps_bool(self):
        self.assertEqual(stringly.dumps(complex, True), '1')

    def test_dumps_int(self):
        self.assertEqual(stringly.dumps(complex, 1), '1')

    def test_dumps_float(self):
        self.assertEqual(stringly.dumps(complex, 1.0), '1')

    def test_dumps_complex(self):
        self.assertEqual(stringly.dumps(complex, 1j), '1j')
        self.assertEqual(stringly.dumps(complex, 1+0j), '1')
        self.assertEqual(stringly.dumps(complex, 1+2j), '1+2j')

    def test_serializer(self):
        s = stringly.serializer.get(complex)
        self.assertIsInstance(s, stringly.serializer.Native)
        self.assertEqual(str(s), 'complex')


class Path(unittest.TestCase):

    def test_loads(self):
        self.assertEqual(stringly.loads(
            pathlib.Path, '/foo/bar'), pathlib.Path('/foo/bar'))

    def test_dumps(self):
        self.assertEqual(stringly.dumps(
            pathlib.Path, pathlib.Path('/foo/bar')), '/foo/bar')
        with self.assertRaisesRegex(stringly.error.SerializationError, '1.2 <float> is not an instance of Path'):
            stringly.dumps(pathlib.Path, 1.2)

    def test_serializer(self):
        s = stringly.serializer.get(pathlib.Path)
        self.assertIsInstance(s, stringly.serializer.Native)
        self.assertEqual(str(s), 'Path')


class Decimal(unittest.TestCase):

    def test_loads(self):
        self.assertEqual(stringly.loads(decimal.Decimal, '1.2'), decimal.Decimal('1.2'))
        with self.assertRaises(stringly.error.SerializationError):
            stringly.loads(decimal.Decimal, '1a')

    def test_dumps(self):
        self.assertEqual(stringly.dumps(decimal.Decimal, decimal.Decimal('1.2')), '1.2')
        with self.assertRaisesRegex(stringly.error.SerializationError, '1.2 <float> is not an instance of Decimal'):
            stringly.dumps(decimal.Decimal, 1.2)

    def test_serializer(self):
        s = stringly.serializer.get(decimal.Decimal)
        self.assertIsInstance(s, stringly.serializer.Native)
        self.assertEqual(str(s), 'Decimal')


class Typing(unittest.TestCase):

    def check(self, t, v, s, strt=None):
        self.assertEqual(stringly.dumps(t, v), s)
        self.assertEqual(stringly.loads(t, s), v)
        self.assertEqual(str(stringly.serializer.get(t)), strt or str(t))

    def test_tuple(self):
        self.check(typing.Tuple[str], ('',), '{}')
        self.check(typing.Tuple[str], ('1',), '1')
        self.check(typing.Tuple[int,complex], (1,2j), '1,2j')
        with self.assertRaises(ValueError):
            stringly.serializer.get(tuple)

    def test_uniform_tuple(self):
        self.check(typing.Tuple[str,...], (), '')
        self.check(typing.Tuple[str,...], ('',), '{}')
        self.check(typing.Tuple[int,...], (1,), '1')
        self.check(typing.Tuple[int,...], (1,2), '1,2')

    def test_list(self):
        self.check(typing.List[str], [], '')
        self.check(typing.List[str], [''], '{}')
        self.check(typing.List[int], [1], '1')
        self.check(typing.List[int], [1,2], '1,2')
        with self.assertRaises(ValueError):
            stringly.serializer.get(list)

    def test_set(self):
        self.check(typing.Set[str], set(), '')
        self.check(typing.Set[str], {''}, '{}')
        self.check(typing.Set[int], {1}, '1')
        self.check(typing.Set[int], {1,2}, '1,2')
        with self.assertRaises(ValueError):
            stringly.serializer.get(set)

    def test_frozenset(self):
        self.check(typing.FrozenSet[str], frozenset(), '')
        self.check(typing.FrozenSet[str], frozenset({''}), '{}')
        self.check(typing.FrozenSet[int], frozenset({1}), '1')
        self.check(typing.FrozenSet[int], frozenset({1,2}), '1,2')
        with self.assertRaises(ValueError):
            stringly.serializer.get(frozenset)

    def test_dict(self):
        self.check(typing.Dict[str,int], {}, '')
        self.check(typing.Dict[str,int], {'a': 1}, 'a=1')
        self.check(typing.Dict[str,str], {'a=': '=1'}, '{a=}==1')
        self.check(typing.Dict[str,str], {'a,': ',1'}, '{a,}={,1}')
        self.check(typing.Dict[int,complex], {1: 2j}, '1=2j')
        with self.assertRaises(ValueError):
            stringly.serializer.get(dict)

    def test_union(self):
        self.check(typing.Union[str,int,complex], '1', 'str{1}')
        self.check(typing.Union[str,int,complex], 1, 'int{1}')
        self.check(typing.Union[str,complex,int], 1, 'complex{1}')
        self.check(typing.Union[str,int,complex], 2j, 'complex{2j}')

    def test_union_empty_value(self):
        self.check(typing.Union[str,complex], '', 'str')

    def test_optional(self):
        self.check(typing.Optional[str], '1', '1', 'typing.Optional[str]')
        self.check(typing.Optional[str], '', '{}', 'typing.Optional[str]')
        self.check(typing.Optional[str], '{}', '{{}}', 'typing.Optional[str]')
        self.check(typing.Optional[str], '{', '{', 'typing.Optional[str]')
        self.check(typing.Optional[str], '}', '}', 'typing.Optional[str]')
        self.check(typing.Optional[int], 1, '1', 'typing.Optional[int]')

    def test_optional_union(self):
        self.check(typing.Optional[typing.Union[str,int]], '1', 'str{1}', 'typing.Optional[typing.Union[str, int]]')
        self.check(typing.Optional[typing.Union[str,int]], 1, 'int{1}', 'typing.Optional[typing.Union[str, int]]')
        self.check(typing.Optional[typing.Union[str,int]], None, '', 'typing.Optional[typing.Union[str, int]]')
        self.check(typing.Optional[typing.Union[str,int]], '', 'str', 'typing.Optional[typing.Union[str, int]]')

    def test_optional_empty_value(self):
        self.check(typing.Optional[str], None, '', 'typing.Optional[str]')
        self.check(typing.Optional[int], None, '', 'typing.Optional[int]')

    def test_dataclass(self):
        t = dataclasses.make_dataclass('t', [('a', int), ('b', str, dataclasses.field(default='2'))])
        self.check(t, t(a=1, b='2,3'), 'a=1,b={2,3}', 't')
        self.assertEqual(stringly.loads(t, 'a=1'), t(a=1))

    def test_namedtuple(self):
        if sys.version_info < (3,6,1):
            self.skipTest('NamedTuple not support by stringly for Python < 3.6.1')
        l = {}
        exec(textwrap.dedent('''
      class t(typing.NamedTuple):
        a: int
        b: str = '2'
      '''), globals(), l)
        t = l['t']
        self.check(t, t(a=1, b='2,3'), 'a=1,b={2,3}', 't')
        self.assertEqual(stringly.loads(t, 'a=1'), t(a=1))

    def test_newarg(self):
        class t:
            def __init__(self, a = 1, b: complex = 2j):
                self.a = a
                self.b = b
            def __getnewargs_ex__(self):
                return (self.a, self.b), {}
            def __eq__(self, other):
                return type(self) == type(other) and self.a == other.a and self.b == other.b
        self.check(t, t(), 'a=1,b=2j', 't')

    def test_positional(self):
        import inspect
        class t:
            def __init__(self, a: str, b: float):
                self.a = a
                self.b = b
            __init__.__signature__ = inspect.Signature([
              inspect.Parameter('self', inspect.Parameter.POSITIONAL_ONLY),
              inspect.Parameter('a', inspect.Parameter.POSITIONAL_ONLY, annotation=str),
              inspect.Parameter('b', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=float)])
            def __getnewargs__(self):
                return self.a, self.b
            def __eq__(self, other):
                return isinstance(other, t) and self.a == other.a and self.b == other.b
        self.check(t, t('x,y',2.), '{x,y},b=2', 't')

    def test_single_positional(self):
        import inspect
        class t:
            def __init__(self, arg: str):
                self.arg = arg
            __init__.__signature__ = inspect.Signature([
              inspect.Parameter('self', inspect.Parameter.POSITIONAL_ONLY),
              inspect.Parameter('arg', inspect.Parameter.POSITIONAL_ONLY, annotation=str)])
            def __getnewargs__(self):
                return self.arg,
            def __eq__(self, other):
                return isinstance(other, t) and self.arg == other.arg
        self.check(t, t('x,y'), 'x,y', 't')

    def test_single_positional_default(self):
        import inspect
        class t:
            def __init__(self, arg: str = '1'):
                self.arg = arg
            __init__.__signature__ = inspect.Signature([
              inspect.Parameter('self', inspect.Parameter.POSITIONAL_ONLY),
              inspect.Parameter('arg', inspect.Parameter.POSITIONAL_ONLY, annotation=str, default='1')])
            def __getnewargs__(self):
                return self.arg,
            def __eq__(self, other):
                return isinstance(other, t) and self.arg == other.arg
        self.assertEqual(stringly.dumps(t, t('')), '{}')
        self.assertEqual(stringly.loads(t, ''), t())
        self.check(t, t('x,y'), 'x,y', 't')

    def test_single_keyword(self):
        import inspect
        class t:
            def __init__(self, arg: str):
                self.arg = arg
            def __getnewargs__(self):
                return self.arg,
            def __eq__(self, other):
                return isinstance(other, t) and self.arg == other.arg
        self.check(t, t('x,y'), 'arg=x,y', 't')

    def test_single_keyword_default(self):
        import inspect
        class t:
            def __init__(self, arg: str = '1'):
                self.arg = arg
            def __getnewargs__(self):
                return self.arg,
            def __eq__(self, other):
                return isinstance(other, t) and self.arg == other.arg
        self.assertEqual(stringly.loads(t, ''), t())
        self.check(t, t('x,y'), 'arg=x,y', 't')

    def test_enum(self):
        class t(enum.Enum):
            foo = 1
            bar = 2
        self.check(t, t.foo, 'foo', 't')
        self.check(t, t.bar, 'bar', 't')

    def test_custom(self):
        class Custom:
            @staticmethod
            def __stringly_loads__(value):
                if value.startswith('int{') and value.endswith('}'):
                    return int(value[4:-1])
                elif value.startswith('str{') and value.endswith('}'):
                    return str(value[4:-1])
                else:
                    raise ValueError('unsupported type')
            @staticmethod
            def __stringly_dumps__(value):
                if isinstance(value, int):
                    return f'int{{{value}}}'
                elif isinstance(value, str):
                    return f'str{{{value}}}'
                else:
                    raise ValueError('unsupported type')
        self.check(Custom, '1', 'str{1}', 'Custom')
        self.check(Custom, 1, 'int{1}', 'Custom')


class DocString(unittest.TestCase):
    '''Some text.

    .. arguments::

       foo
         Description of foo.
       bar [1]

    Some more text.

    .. presets::

       my preset
         foo=Foo
           x=1
           y=2
         bar=2
    '''

    def test_text(self):
        self.assertEqual(stringly.util.DocString(self).text,
          'Some text.\n\nSome more text.')

    def test_defaults(self):
        self.assertEqual(stringly.util.DocString(self).defaults,
          {'bar': '1'})

    def test_argdocs(self):
        self.assertEqual(stringly.util.DocString(self).argdocs,
          {'foo': 'Description of foo.', 'bar': ''})

    def test_presets(self):
        self.assertEqual(stringly.util.DocString(self).presets,
          {'my preset': {'foo': 'Foo{x=1,y=2}', 'bar': '2'}})
