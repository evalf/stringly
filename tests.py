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

  class A(stringly.struct):
    def __init__(self, b=True, i=1, f=2.5):
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
    self.assertEqual(str(a), 'b=False,i=5,f=10.0')

  def test_partialkeywordargs(self):
    a = self.A(i=5, f=10.)
    self.check(a, i=5, f=10., b=True)
    self.assertEqual(str(a), 'b=True,i=5,f=10.0')

  def test_stringarg(self):
    a = self.A('f=10,i=5,b=no')
    self.check(a, i=5, f=10., b=False)
    self.assertEqual(str(a), 'b=False,i=5,f=10.0')

  def test_partialstringarg(self):
    a = self.A('i=1')
    self.check(a, i=1, f=2.5, b=True)
    self.assertEqual(str(a), 'b=True,i=1,f=2.5')

  def test_noarg(self):
    a = self.A()
    self.check(a, b=True, i=1, f=2.5)

class InlineStruct(Struct):

  a = stringly.struct(b=True, i=1, f=2.5)
  A = a.__class__

  def test_instance(self):
    self.check(self.a, i=1, f=2.5, b=True)

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
    self.check(self.T('b{1},a{2}'), 1., '2')

  def test_directarg(self):
    self.check(self.T([1., '2']), 1., '2')

  def test_string(self):
    self.assertEqual(str(self.T()), '')
    self.assertEqual(str(self.T([1., '2'])), 'b{1.0},a{2}')
    self.assertEqual(str(self.T('a{1},b{2}')), 'a{1},b{2.0}')

class InlineTuple(Tuple):

  t = stringly.tuple('b{2}', a=str, b=float)
  T = t.__class__

  def test_instance(self):
    self.check(self.t, 2.)

class Dict(unittest.TestCase):

  class T(stringly.dict, a=str, b=float):
    pass

  def check(*args, **values):
    self, t = args
    self.assertEqual(len(t), len(values))
    for k, v in values.items():
      self.assertEqual(t[k], v)
      self.assertIsInstance(t[k], v.__class__)

  def test_defaults(self):
    self.check(self.T())

  def test_stringarg(self):
    self.check(self.T('x=b{1},y=a{2}'), **{'x': 1., 'y': '2'})
    self.check(self.T('{{}x}=a{1=},{y=}=b{2}'), **{'{x': '1=', 'y=': 2.})

  def test_directarg(self):
    self.check(self.T({'x': 1., 'y': '2'}), **{'x': 1., 'y': '2'})
    self.check(self.T({'{x': '1=', 'y=': 2.}), **{'{x': '1=', 'y=': 2.})

  def test_string(self):
    self.assertEqual(str(self.T()), '')
    self.assertEqual(str(self.T(dict(x=1., y='2'))), 'x=b{1.0},y=a{2}')
    self.assertEqual(str(self.T('x=a{1},y=b{2}')), 'x=a{1},y=b{2.0}')
    self.assertEqual(str(self.T('{{}x}=a{1=},{y=}=b{2}')), '{{}x}=a{1=},{y=}=b{2.0}')

class InlineDict(Dict):

  t = stringly.dict('x=b{2}', a=str, b=float)
  T = t.__class__

  def test_instance(self):
    self.check(self.t, x=2.)

class Choice(unittest.TestCase):

  class C(stringly.choice, a=float, b=2):
    pass

  def check(self, c, expect):
    self.assertEqual(c, expect)
    self.assertIsInstance(c.value, expect.__class__)

  def test_objarg(self):
    self.check(self.C('b'), 2)

  def test_typeargstring(self):
    self.check(self.C('a{2.5}'), 2.5)

  def test_string(self):
    self.assertEqual(str(self.C('a{1}')), 'a{1.0}')
    self.assertEqual(str(self.C('b')), 'b')

class InlineChoice(Choice):

  c = stringly.choice('a{1}', a=float, b=2)
  C = c.__class__

  def test_instance(self):
    self.check(self.c, 1.)

class Unit(unittest.TestCase):

  class U(stringly.unit, m=1, s=1, g=1e-3, Pa='N/m2', N='kg*m*s-2', lb='453.59237g', h='3600s', **{'in': '.0254m'}):
    pass

  def check(self, *args, **powers):
    s, v = args
    u = self.U(s)
    self.assertEqual(u, v)
    U = u.__class__
    self.assertEqual(U._powers, powers)
    self.assertEqual(U(s), v)

  def test_length(self):
    self.check('m', 1, m=1)
    self.check('10in', .254, m=1)

  def test_mass(self):
    self.check('kg', 1, g=1)
    self.check('1lb', .45359237, g=1)

  def test_time(self):
    self.check('s', 1, s=1)
    self.check('.5h', 1800, s=1)

  def test_velocity(self):
    self.check('m/s', 1, m=1, s=-1)
    self.check('km/h', 1/3.6, m=1, s=-1)

  def test_force(self):
    self.check('N', 1, g=1, m=1, s=-2)
    self.check('100Pa*in2', .254**2, g=1, m=1, s=-2)

  def test_pressure(self):
    self.check('Pa', 1, g=1, m=-1, s=-2)
    self.check('10000lb/in/h2', 453.59237/25.4/36**2, g=1, m=-1, s=-2)
