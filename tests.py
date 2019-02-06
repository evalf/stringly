import stringly, unittest

class Escape(unittest.TestCase):

  def assertEscaped(self, orig, normal=None):
    if normal is not None:
      self.assertEqual(stringly.escape(orig), normal)
    else:
      normal = stringly.escape(orig)
    self.assertEqual(stringly.unescape(normal), orig)

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
      self.assertEqual(stringly.protect(orig, sep), protected)
    else:
      protected = stringly.protect(orig, sep)
    self.assertEqual(stringly.safesplit(protected, sep), [protected] if orig else [])
    self.assertEqual(stringly.unprotect(protected), orig)

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

class Struct(unittest.TestCase):

  class A(stringly.struct, b=True):
    def __init__(self, b, i:int, f=2.5):
      self.b = b
      self.f = f
      self.i = i

  def check(self, a, *, i, f, b):
    self.assertIsInstance(a.i, int)
    self.assertEqual(a.i, i)
    self.assertIsInstance(a.f, float)
    self.assertEqual(a.f, f)
    self.assertIsInstance(a.b, bool)
    self.assertEqual(a.b, b)

  def test_keywordargs(self):
    a = self.A(i=5, f=10., b=False)
    self.check(a, i=5, f=10., b=False)
    self.assertEqual(str(a), 'b=False,f=10.0,i=5')

  def test_partialkeywordargs(self):
    a = self.A(i=5, f=10.)
    self.check(a, i=5, f=10., b=True)
    self.assertEqual(str(a), 'b=True,f=10.0,i=5')

  def test_stringarg(self):
    a = self.A('f=10,i=5,b=no')
    self.check(a, i=5, f=10., b=False)
    self.assertEqual(str(a), 'b=False,f=10.0,i=5')

  def test_partialstringarg(self):
    a = self.A('i=1')
    self.check(a, i=1, f=2.5, b=True)
    self.assertEqual(str(a), 'b=True,f=2.5,i=1')

  def test_subclass(self):
    class B(self.A):
      def __init__(_self, s='foo', **kwargs):
        self.assertEqual(kwargs, dict(i=10, f=2.5, b=True))
        _self.s = s
        super().__init__(**kwargs)
    b = B(i=10)
    self.check(b, i=10, f=2.5, b=True)
    self.assertEqual(b.s, 'foo')
    self.assertEqual(str(b), 'b=True,f=2.5,i=10,s=foo')

class InlineStruct(Struct):

  a = stringly.struct(i=10, f=2.5, b=True)
  A = a.__class__

  def test_instance(self):
    self.check(self.a, i=10, f=2.5, b=True)

class Tuple(unittest.TestCase):

  class T(stringly.tuple, a=str, b=float):
    pass

  def check(self, t, *values):
    self.assertEqual(len(t), len(values))
    for i, v in enumerate(values):
      self.assertEqual(t[i], v)
      self.assertIsInstance(t[i], v.__class__)

  def test_defaults(self):
    self.check(self.T())

  def test_stringarg(self):
    self.check(self.T('b:1,a:2'), 1., '2')

  def test_directarg(self):
    self.check(self.T([1., '2']), 1., '2')

  def test_string(self):
    self.assertEqual(str(self.T()), '')
    self.assertEqual(str(self.T([1., '2'])), 'b:1.0,a:2')
    self.assertEqual(str(self.T('a:1,b:2')), 'a:1,b:2.0')

class InlineTuple(Tuple):

  t = stringly.tuple('b:2', a=str, b=float)
  T = t.__class__

  def test_instance(self):
    self.check(self.t, 2.)
