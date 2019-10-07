Stringly: Human Readable Object Serialization
=============================================

Stringly aims to facilitate foreign function calls into Python by providing
human readable serialization and de-serialization of arbitrary Python objects.

Stringly is similar to Python's pickle protocol in that the serialized form
follows directly from class introspection. This as opposed to serialization
technologies such as JSON and YAML, which are self contained but support only a
predefined set of data types. Similar to those technologies, however, and
unlike pickle, the resulting strings are human readible and human writable.

A typical use case of stringly is as part of a command line parser, using the
stringly representation to instantiate objects direcly from the command line.

Example
-------

Stringly requires [type hints](https://docs.python.org/3/library/typing.html)
to infer object types. Since these are getting more and more common, chances
are that stringly will work directly out of the box. In case extra work is
required, the reward is double as this effort should also benefit static type
checkers such as [mypy](http://www.mypy-lang.org/).

The following is an example of a class that is suitable for stringlification:

    >>> import typing, dataclasses, stringly
    >>>
    >>> @dataclasses.dataclass
    ... class A:
    ...   name: str
    ...   data: typing.Dict[str,int]

Objects are serialized using `stringly.dumps`:

    >>> a = A('hi', {'foo': 1, 'bar': 2})
    >>> stringly.dumps(A, a)
    # 'name=hi,data={foo=1,bar=2}'

Objects are de-serialized using `stringly.loads`:

    >>> a = stringly.loads(A, 'name=bye,data={baz=3}')
    >>> a.name
    # 'bye'
    >>> a.data
    # {'baz': 3}
