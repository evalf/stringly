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
