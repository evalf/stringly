import typing, importlib, runpy, inspect, sys, os, textwrap
from . import error, util, serializer

T = typing.TypeVar('T')

def import_function(funcpath: str) -> typing.Callable[..., typing.Any]:
  if '/' in funcpath:
    if ':' in funcpath:
      script, funcname = funcpath.rsplit(':', 1)
    else:
      script = funcpath
      funcname = 'main'
    ns = runpy.run_path(script, run_name='<stringly.import_function>')
    try:
      func = ns[funcname]
    except KeyError as e:
      raise error.ImportFunctionError('no such function in script {}: {}'.format(script, funcname)) from e
  else:
    parts = funcpath.split('.')
    for i in range(1, len(parts)):
      mod = importlib.import_module('.'.join(parts[:i]))
      try:
        func = getattr(mod, '.'.join(parts[i:]))
        break
      except AttributeError:
        pass
    else:
      raise error.ImportFunctionError('no such function: {}'.format(funcpath))
  if not callable(func):
    raise error.ImportFunctionError('function {!r} is not callable'.format(funcpath))
  return typing.cast(typing.Callable[..., typing.Any], func)

def run(func: typing.Callable[..., T]) -> T:
  if not callable(func):
    sys.exit('function is not callable')

  sig = inspect.signature(func)
  doc = util.DocString(func)
  defaults = dict(doc.defaults)
  prog, *args = sys.argv

  if '-h' in args or '--help' in args:
    usage = ['USAGE: {}'.format(os.path.basename(prog))]
    if doc.presets:
      usage.append(' [{}]'.format('|'.join(doc.presets)))
    if sig.parameters:
      usage.append(' [arg1=value1] [arg2=value2] ...')
      usage.append('\n\nARGUMENTS')
      argdocs = doc.argdocs
      for param in sig.parameters.values():
        description = argdocs[param.name] if param.name in argdocs \
                 else textwrap.dedent(param.annotation.__doc__).lstrip() if isinstance(param.annotation, type) and isinstance(param.annotation.__doc__, str) \
                 else str(param.annotation)
        default = defaults.get(param.name)
        usage.append('\n  {} ({})'.format(param.name, 'default empty' if default == '' else 'default: {}'.format(default) if default else 'optional' if param.default is not param.empty else 'mandatory'))
        usage.extend(textwrap.wrap(description, initial_indent='\n    ', subsequent_indent='\n    '))
    if doc.text:
      usage.append('\n\nABOUT\n')
      usage.append(doc.text)
    sys.exit(''.join(usage))

  if args and '=' not in args[0]:
    preset = args.pop(0)
    defaults.update(doc.presets[preset])
  for arg in args:
    name, sep, value = arg.partition('=')
    if not sep:
      sys.exit('argument {!r} requires a value'.format(name))
    defaults[name] = value

  kwargs = {param.name: serializer.get(param.annotation if param.annotation != param.empty else type(param.default)).loads(defaults.pop(param.name))
    for param in sig.parameters.values() if param.name in defaults} # type: typing.Dict[str,typing.Any]

  if defaults:
    sys.exit('unexpected argument: {}'.format(', '.join(defaults)))

  return func(**kwargs)
