from setuptools import setup
import re

with open('stringly.py') as f:
  version = next(filter(None, map(re.compile("^version = '([a-zA-Z0-9.]+)'$").match, f))).group(1)

setup(
  name = 'stringly',
  version = version,
  description = 'Stringly typed command line interface',
  author = 'Evalf',
  author_email = 'info@evalf.com',
  url = 'https://github.com/evalf/stringly',
  py_modules = ['stringly'],
  license = 'MIT',
  python_requires = '>=3.5',
)
