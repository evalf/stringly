from setuptools import setup
import os, re

with open(os.path.join('stringly', '__init__.py')) as f:
  version = next(filter(None, map(re.compile("^version = '([a-zA-Z0-9.]+)'$").match, f))).group(1)

if os.getenv('STRINGLY_USE_MYPYC', None) == '1':
  from mypyc.build import mypycify
  import pathlib
  ext_modules = mypycify([str(p) for p in pathlib.Path('stringly').glob('*.py') if p.name not in {'__init__.py', 'proto.py'}])
else:
  ext_modules = []

setup(
  name = 'stringly',
  version = version,
  description = 'Stringly typed command line interface',
  author = 'Evalf',
  author_email = 'info@evalf.com',
  url = 'https://github.com/evalf/stringly',
  packages = ['stringly'],
  package_data = {'stringly': ['py.typed']},
  ext_modules=ext_modules,
  license = 'MIT',
  python_requires = '>=3.5',
  install_requires = ['typing_extensions'],
)
