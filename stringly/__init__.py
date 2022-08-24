# Copyright (c) 2018 Evalf
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

'''Stringly: Human Readable Object Serialization

Stringly aims to facilitate foreign function calls into Python by providing
human readable serialization and de-serialization of arbitrary Python objects.

Stringly is similar to Python's pickle protocol in that the serialized form
follows directly from class introspection. This as opposed to serialization
technologies such as JSON and YAML, which are self contained but support only a
predefined set of data types. Similar to those technologies, however, and
unlike pickle, the resulting strings are human readible and human writable.

A typical use case of stringly is as part of a command line parser, using the
stringly representation to instantiate objects direcly from the command line.'''

__version__ = '1.0b3'


import typing
from . import util, serializer, proto

T = typing.TypeVar('T')


def loads(t: typing.Type[T], s: str, *, pretty: bool = False) -> T:
    if pretty:
        s = util.deprettify(s)
    return serializer.get(t).loads(s)


def dumps(t: typing.Type[T], v: T, *, pretty: bool = False) -> str:
    s = serializer.get(t).dumps(v)
    if pretty:
        s = util.prettify(s)
    return s


def load(t: typing.Type[T], f: proto.SupportsRead, *, pretty: bool = False) -> T:
    return loads(t, f.read(), pretty=pretty)


def dump(t: typing.Type[T], v: T, f: proto.SupportsWrite, *, pretty: bool = False) -> None:
    f.write(dumps(t, v, pretty=pretty))
