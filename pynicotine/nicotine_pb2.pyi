from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SearchRequest(_message.Message):
    __slots__ = ("term",)
    TERM_FIELD_NUMBER: _ClassVar[int]
    term: str
    def __init__(self, term: _Optional[str] = ...) -> None: ...

class SearchResponse(_message.Message):
    __slots__ = ("username", "user_files")
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    USER_FILES_FIELD_NUMBER: _ClassVar[int]
    username: str
    user_files: _containers.RepeatedCompositeFieldContainer[File]
    def __init__(self, username: _Optional[str] = ..., user_files: _Optional[_Iterable[_Union[File, _Mapping]]] = ...) -> None: ...

class DownloadRequest(_message.Message):
    __slots__ = ("username", "file")
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    FILE_FIELD_NUMBER: _ClassVar[int]
    username: str
    file: File
    def __init__(self, username: _Optional[str] = ..., file: _Optional[_Union[File, _Mapping]] = ...) -> None: ...

class File(_message.Message):
    __slots__ = ("filepath", "size", "quality")
    FILEPATH_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    QUALITY_FIELD_NUMBER: _ClassVar[int]
    filepath: str
    size: str
    quality: str
    def __init__(self, filepath: _Optional[str] = ..., size: _Optional[str] = ..., quality: _Optional[str] = ...) -> None: ...

class DownloadResponse(_message.Message):
    __slots__ = ("status", "progress")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    status: DownloadStatus
    progress: DownloadProgress
    def __init__(self, status: _Optional[_Union[DownloadStatus, _Mapping]] = ..., progress: _Optional[_Union[DownloadProgress, _Mapping]] = ...) -> None: ...

class DownloadStatus(_message.Message):
    __slots__ = ("status",)
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UNKNOWN: _ClassVar[DownloadStatus.Status]
        QUEUED: _ClassVar[DownloadStatus.Status]
        DOWNLOADING: _ClassVar[DownloadStatus.Status]
        COMPLETED: _ClassVar[DownloadStatus.Status]
        CANCELLED: _ClassVar[DownloadStatus.Status]
    UNKNOWN: DownloadStatus.Status
    QUEUED: DownloadStatus.Status
    DOWNLOADING: DownloadStatus.Status
    COMPLETED: DownloadStatus.Status
    CANCELLED: DownloadStatus.Status
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: DownloadStatus.Status
    def __init__(self, status: _Optional[_Union[DownloadStatus.Status, str]] = ...) -> None: ...

class DownloadProgress(_message.Message):
    __slots__ = ("progress",)
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    progress: int
    def __init__(self, progress: _Optional[int] = ...) -> None: ...
