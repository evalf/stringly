import stringly, unittest, typing, enum, decimal, sys, textwrap

if sys.version_info >= (3,7):
  import dataclasses
else:
  dataclasses = None

class Escape(unittest.TestCase):

  def assertEscaped(self, orig, normal=None):
    if normal is not None:
      self.assertEqual(stringly.util.escape(orig), normal)
    else:
      normal = stringly.util.escape(orig)
    self.assertEqual(stringly.util.unescape(normal), orig)

  def test_combinations(self):
    for length in range(6):
      for i in range(2**length):
        self.assertEscaped(''.join('{}'[i>>j&1] for j in range(length)))

  def test_normality(self):
    self.assertEscaped('abc', 'abc')
    self.assertEscaped('ab{cd}ef', 'ab{cd}ef')

  def test_negativity(self):
    self.assertEscaped('ab}cd{ef', 'ab}{cd{}ef')
    self.assertEscaped('a}b}cd{e{f', 'a}{b}{cd{}e{}f')

  def test_disbalance(self):
    self.assertEscaped('abc}def', 'abc}{def')
    self.assertEscaped('abc{def', 'abc{}def')
    self.assertEscaped('a{bc}de{f', 'a{}bc}{de{}f')
    self.assertEscaped('a}bc{de}f', 'a}{bc{de}f')

class Protect(unittest.TestCase):

  def assertProtected(self, orig, protected=None, sep=','):
    if protected is not None:
      self.assertEqual(stringly.util.protect(orig, sep), protected)
    else:
      protected = stringly.util.protect(orig, sep)
    self.assertEqual(stringly.util.safesplit(protected, sep), [protected] if orig else [])
    self.assertEqual(stringly.util.unprotect(protected), orig)

  def test_combinations(self):
    for length in range(6):
      for i in range(4**length):
        self.assertProtected(''.join('{},x'[i>>(j*2)&3] for j in range(length)))

  def test_normality(self):
    self.assertProtected('abc', 'abc')
    self.assertProtected('ab{cd}ef', 'ab{cd}ef')

  def test_protection(self):
    self.assertProtected('abc,def', '{abc,def}')
    self.assertProtected('ab{c,d}ef', 'ab{c,d}ef')
    self.assertProtected('a{b,c}d,ef', '{a{b,c}d,ef}')

  def test_braces(self):
    self.assertProtected('{abc}', '{{abc}}')
    self.assertProtected('{abc{', '{{}abc{}}')
    self.assertProtected('}abc}', '{}{abc}{}')
    self.assertProtected('}abc{', '{}{abc{}}')
    self.assertProtected('}abc', '{}{abc}')
    self.assertProtected('abc{', '{abc{}}')

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
    with self.assertRaisesRegex(stringly.error.SerializationError, '1.0 .* is not an instance of int'):
      stringly.dumps(int, 1.0)

  def test_dumps_complex(self):
    with self.assertRaisesRegex(stringly.error.SerializationError, '1j .* is not an instance of int'):
      stringly.dumps(int, 1j)

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
    with self.assertRaisesRegex(stringly.error.SerializationError, '1j .* is not an instance of float'):
      stringly.dumps(float, 1j)

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

class Typing(unittest.TestCase):

  def check(self, t, v, s):
    self.assertEqual(stringly.dumps(t, v), s)
    self.assertEqual(stringly.loads(t, s), v)

  def test_decimal(self):
    self.check(decimal.Decimal, decimal.Decimal('1.2'), '1.2')

  def test_tuple(self):
    self.check(typing.Tuple[str], ('',), '{}')
    self.check(typing.Tuple[str], ('1',), '1')
    self.check(typing.Tuple[int,complex], (1,2j), '1,2j')

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

  def test_set(self):
    self.check(typing.Set[str], set(), '')
    self.check(typing.Set[str], {''}, '{}')
    self.check(typing.Set[int], {1}, '1')
    self.check(typing.Set[int], {1,2}, '1,2')

  def test_frozenset(self):
    self.check(typing.FrozenSet[str], frozenset(), '')
    self.check(typing.FrozenSet[str], frozenset({''}), '{}')
    self.check(typing.FrozenSet[int], frozenset({1}), '1')
    self.check(typing.FrozenSet[int], frozenset({1,2}), '1,2')

  def test_dict(self):
    self.check(typing.Dict[str,int], {}, '')
    self.check(typing.Dict[str,int], {'a': 1}, 'a=1')
    self.check(typing.Dict[str,str], {'a=': '=1'}, '{a=}==1')
    self.check(typing.Dict[str,str], {'a,': ',1'}, '{a,}={,1}')
    self.check(typing.Dict[int,complex], {1: 2j}, '1=2j')

  def test_union(self):
    self.check(typing.Union[str,int,complex], '1', 'str{1}')
    self.check(typing.Union[str,int,complex], 1, 'int{1}')
    self.check(typing.Union[str,complex,int], 1, 'complex{1}')
    self.check(typing.Union[str,int,complex], 2j, 'complex{2j}')

  def test_union_empty_value(self):
    self.check(typing.Union[str,complex], '', 'str')

  def test_optional(self):
    self.check(typing.Optional[str], '1', '1')
    self.check(typing.Optional[str], '', '{}')
    self.check(typing.Optional[int], 1, '1')

  def test_optional_union(self):
    self.check(typing.Optional[typing.Union[str,int]], '1', 'str{1}')
    self.check(typing.Optional[typing.Union[str,int]], 1, 'int{1}')
    self.check(typing.Optional[typing.Union[str,int]], None, '')
    self.check(typing.Optional[typing.Union[str,int]], '', 'str')

  def test_optional_empty_value(self):
    self.check(typing.Optional[str], None, '')
    self.check(typing.Optional[int], None, '')

  def test_dataclass(self):
    if not dataclasses:
      self.skipTest('module dataclasses unavailable for python < 3.7')
    t = dataclasses.make_dataclass('t', [('a', int), ('b', str, dataclasses.field(default='2'))])
    self.check(t, t(a=1, b='2,3'), 'a=1,b={2,3}')
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
    self.check(t, t(a=1, b='2,3'), 'a=1,b={2,3}')
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
    self.check(t, t(), 'a=1,b=2j')

  def test_positional(self):
    import inspect
    class t:
      def __init__(self, a: int, b: float):
        self.a = a
        self.b = b
      __init__.__signature__ = inspect.Signature([
        inspect.Parameter('self', inspect.Parameter.POSITIONAL_ONLY),
        inspect.Parameter('a', inspect.Parameter.POSITIONAL_ONLY, annotation=int),
        inspect.Parameter('b', inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=float)])
      def __getnewargs__(self):
        return self.a, self.b
      def __eq__(self, other):
        return isinstance(other, t) and self.a == other.a and self.b == other.b
    self.check(t, t(1,2.), '1,b=2')

  def test_enum(self):
    class t(enum.Enum):
      foo = 1
      bar = 2
    self.check(t, t.foo, 'foo')
    self.check(t, t.bar, 'bar')

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
          return 'int{{{}}}'.format(value)
        elif isinstance(value, str):
          return 'str{{{}}}'.format(value)
        else:
          raise ValueError('unsupported type')
    self.check(Custom, '1', 'str{1}')
    self.check(Custom, 1, 'int{1}')

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
