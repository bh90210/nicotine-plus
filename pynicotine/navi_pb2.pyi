from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class SearchRequest(_message.Message):
    __slots__ = ("term",)
    TERM_FIELD_NUMBER: _ClassVar[int]
    term: str
    def __init__(self, term: _Optional[str] = ...) -> None: ...

class SearchReply(_message.Message):
    __slots__ = ("username", "file")
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    FILE_FIELD_NUMBER: _ClassVar[int]
    username: str
    file: str
    def __init__(self, username: _Optional[str] = ..., file: _Optional[str] = ...) -> None: ...

class DownloadRequest(_message.Message):
    __slots__ = ("username", "file")
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    FILE_FIELD_NUMBER: _ClassVar[int]
    username: str
    file: str
    def __init__(self, username: _Optional[str] = ..., file: _Optional[str] = ...) -> None: ...

class DownloadReply(_message.Message):
    __slots__ = ("result",)
    RESULT_FIELD_NUMBER: _ClassVar[int]
    result: int
    def __init__(self, result: _Optional[int] = ...) -> None: ...
