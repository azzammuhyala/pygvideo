import os
import typing
from pathlib import Path as PathL
from moviepy import (
    VideoFileClip,
    CompositeVideoClip,
    ImageSequenceClip,
    AudioFileClip,
    CompositeAudioClip,
    Effect
)

Number = int | float
Path = os.PathLike[str] | PathL
SupportsClip = VideoFileClip | CompositeVideoClip | ImageSequenceClip
SupportsAudioClip = AudioFileClip | CompositeAudioClip
MoviePyFx = Effect
Excepts = Exception | BaseException
NameMethod = str
FloatSecondsValue = float
FloatMilisecondsValue = float
IntSecondsValue = int
IntMilisecondsValue = int
SecondsValue = FloatSecondsValue | IntSecondsValue
MilisecondsValue = FloatMilisecondsValue | IntMilisecondsValue

def _raised(exception, from_exception) -> None:
    if from_exception:
        raise exception from from_exception
    raise exception

def asserter(condition: bool, exception: Excepts | str, from_exception: Excepts | None = None) -> None:
    if not condition:
        if isinstance(exception, str):
            _raised(AssertionError(exception), from_exception)
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

    def append(self, object) -> None:
        if object not in self:
            super().append(object)

    def is_temp_audio_used(self, filename: Path) -> bool:
        return any(v.get_temp_audio() == filename for v in self)

    def is_any_video_ready(self) -> bool:
        return any(v.is_ready for v in self)