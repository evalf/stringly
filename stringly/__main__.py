import sys
from . import cli, error

if len(sys.argv) <= 1:
  sys.exit('usage: stringly function [arguments]')
try:
  cli.run(cli.import_function(sys.argv.pop(1)))
except error.ImportFunctionError as e:
  sys.exit(str(e))
