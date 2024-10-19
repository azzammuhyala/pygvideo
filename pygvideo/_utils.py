import os
import typing
from pathlib import Path as PathL
from moviepy.editor import VideoFileClip

RealNumber = int | float
Path = os.PathLike[str] | PathL
MoviePyFx = typing.Callable[[VideoFileClip, typing.Any], VideoFileClip]
Excepts = Exception | BaseException
NameMethod = str
FloatSecondsValue = float
FloatMilisecondsValue = float
IntSecondsValue = int
IntMilisecondsValue = int
SecondsValue = FloatSecondsValue | IntSecondsValue
MilisecondsValue = FloatMilisecondsValue | IntMilisecondsValue

def _raised(x, f):
    if f:
        raise x from f
    raise x

def asserter(condition: bool, exception: Excepts | str, from_exception: Excepts | None = None) -> None:
    if not condition:
        if isinstance(exception, str):
            _raised(AssertionError, from_exception)
        _raised(exception, from_exception)

def name(obj: typing.Any) -> str:
    return type(obj).__name__

T = typing.TypeVar('T')

class global_video(list, typing.MutableSequence[T]):

    def __repr__(self) -> str:
        cls = self.__class__
        return f'{cls.__module__}.{cls.__qualname__}({super().__repr__()})'

    def __str__(self) -> str:
        return self.__repr__()

    def is_temp_audio_used(self, filename: Path) -> bool:
        return any(v.get_temp_audio() == filename for v in self)

    def index(self, value, start: int = 0, stop: int | None = None) -> int:
        if stop is None:
            stop = len(self)

        for i, v in enumerate(self[start:stop]):
            if v is value:
                return i

        raise ValueError(f'{repr(value)} is not in list or global_video')

    def remove(self, value) -> None:
        super().pop(self.index(value))