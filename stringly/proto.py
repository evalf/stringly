import typing
import typing_extensions

T = typing.TypeVar('T')


class Serializer(typing_extensions.Protocol[T]):
    def loads(self, s: str) -> T: ...
    def dumps(self, v: T) -> str: ...


class Custom(typing_extensions.Protocol[T]):
    @staticmethod
    def __stringly_loads__(s: str) -> T: ...
    @staticmethod
    def __stringly_dumps__(v: T) -> str: ...


class SupportsRead(typing_extensions.Protocol):
    def read(self) -> str: ...


class SupportsWrite(typing_extensions.Protocol):
    def write(self, data: str) -> typing.Optional[int]: ...
