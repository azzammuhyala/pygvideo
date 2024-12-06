import pygame
import proglog
import warnings
import numpy as np
from moviepy.video import fx
from moviepy import (
    VideoFileClip,
    ImageSequenceClip,
    AudioArrayClip,
    concatenate_videoclips,
    concatenate_audioclips
)
from ._video_preview import video_preview
from ._utils import (
    PathL as Path,
    GlobalVideo,
    typing,
    os,
    asserter,
    name,
    get_save_value
)
from . import _utils
from . import _constants

__all__ = [
    'Video',
    'ignore_warn',
    'enable_warn',
    'get_global_logger',
    'set_global_logger',
    'mute_debug',
    'unmute_debug',
    'quit',
    'quit_all',
    'close',
    'close_all'
]

os.environ['PYGAME_VIDEO_USED'] = '0'

class Video:

    def __init__(

            self,
            filename_or_clip: _utils.Path | _utils.SupportsClip,
            target_resolution: typing.Optional[typing.Any] = None,
            logger: proglog.ProgressBarLogger | typing.Literal['bar', '.global'] | None = '.global',
            has_mask: bool = False,
            load_audio_in_prepare: bool = True,
            cache: bool = True,
            save_clip_to_global: bool = True

        ) -> None:

        """

        A video that can be played to the `pygame` screen. For example:

        ```
        ... video_player = Video('intro.mp4') # load the video
        ... video_player.set_fps(30)          # set the fps
        ... video_player.prepare()            # load the audio
        ... video_player.play()               # play the video and audio
        ... while ...:
        ...    for event in pygame.event.get():
        ...        ...
        ...        video.handle_event(event) # handle the event (OPTIONAL)
        ...    frame = video_player.draw_and_update() # updated, will be returns a frame
        ...    ...
        ... video_player.quit() # clean up resources
        ... ...
        ```

        Parameters
        ----------
        filename_or_clip:
            Name the video file or clip directly. If you use the filename make sure the file extension is
            supported by ffmpeg. Supports clip class: VideoClip and derivative of VideoClip like VideoFileClip,
            etc.
        target_resolution:
            Target resolution. Almost the same as resize. (I think..).
        logger:
            Showing logger/bar. If None, no logger will be shown.
        has_mask:
            Supports transparency/alpha. Depends on video format type.
        load_audio_in_prepare:
            load or precisely write the temp audio when prepare is called.
        cache:
            save frame to cache. (not recommended for videos with large duration and size).
        save_clip_to_global:
            save the VideoClip to global. This is useful for cleaning or closing replaced VideoClips with call
            `quit_all` or `close_all` function.

        Documentation
        -------------
        Full documentation is on [GitHub](https://github.com/azzammuhyala/pygvideo.git) or on
        [PyPi](https://pypi.org/project/pygvideo).

        Bugs
        ----
        There may still be many bugs that occur either from the `Video` code or from `moviepy` itself.
        Play videos that are not too large or not too long so that they run optimally.

        Warnings
        --------
        * Don't change the sound of `pygame.mixer.music` because this class uses audio from `pygame.mixer.music`.
        * Don't delete or replace the audio temp file `__temp__.mp3` because it is the main audio of the video.
        * Don't forget to call the `.prepare()` method to prepare the audio.
        * Don't play 2 videos at the same time.
        * Don't forget to close the video with `.quit()` or `.close()` when not in use or when the system exits.

        Full Example:

        ```
        import pygame
        import pygvideo

        pygame.init()
        pygame.mixer.init()

        running = True
        video = pygvideo.Video('myvideo.mp4')
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        clock = pygame.time.Clock()

        video.set_size(screen.get_size())

        video.preplay(-1)

        while running:

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                video.handle_event(event)

            video.draw_and_update(screen, (0, 0))

            pygame.display.flip()

            clock.tick(video.get_fps())

        pygvideo.quit_all()
        pygame.quit()
        ```

        """

        self.__filename_or_clip = filename_or_clip
        self.__target_resolution = target_resolution
        self.__logger = logger
        self.__has_mask = bool(has_mask)
        self.__load_audio_in_prepare = bool(load_audio_in_prepare)
        self.__cache = bool(cache)
        self.__save_clip_to_global = bool(save_clip_to_global)

        if isinstance(logger, str):
            self.__logger = logger.lower().strip() # convert to lowercase and strip whitespace
            if self.__logger not in ('bar', '.global'):
                warnings.warn(
                    f"Invalid logger name {self.__logger!r}. Use default logger instead.",
                    category=UserWarning,
                    stacklevel=2
                )

        # load properties
        self.__cache_frames = dict()
        self.__size = None
        self.__cache_full = False
        self.__quit = False
        self.__ready = False
        self.__play = False
        self.__pause = False
        self.__mute = False
        self.__index = 0
        self.__loops = 0
        self.__video_loops = 0
        self.__frame_index = 0
        self.__audio_offset = 0
        self.__volume = 0.0
        self.__alpha = 255

        # initialize moviepy video clip
        if isinstance(filename_or_clip, _utils.SupportsClip):
            self.clip = filename_or_clip.copy()
        else:
            self.clip = VideoFileClip(
                filename=filename_or_clip,
                has_mask=has_mask,
                target_resolution=target_resolution
            )

        # save an original clip
        self.__original_clip = self.__clip.copy()

        # load the temporary audio
        # The __reinit property will appear if the reinit method is called,
        # this is a sign that the init method was called because of reinit
        # or not which can avoid creating a new file.
        self.__load_audio(load_file=not hasattr(self, '_Video__reinit'))

        # add Video to global
        global GLOBALS
        GLOBALS['video'].append(self)

    def __getitem__(self, index: typing.SupportsIndex | slice):
        # get the maximum total frames
        # this is not 100% accurate total of all the frames in the Video
        total_frame = self.get_total_frame()

        # for slice case
        if isinstance(index, slice):
            result: list[pygame.Surface] = []
            start = index.start or 0
            stop = index.stop or total_frame
            step = index.step or 1

            if start < 0:
                start = max(total_frame + start, 0)
            if stop < 0:
                stop = max(total_frame + stop, 0)

            for i in range(start, stop, step):
                try:
                    result.append(self[i])
                except IndexError:
                    # outside the frame area then it's done
                    break
                except:
                    # other problems with moviepy such as OSError will be ignored
                    pass

            return result

        # for integer or index cases
        elif isinstance(index, int):
            #       v positif index          v negatif index
            #       ~~~~~                    ~~~~~~~~~~~~~~~~~~~
            index = index if index >= 0 else total_frame + index

            if 0 <= index < total_frame:
                return self.get_frame(index * (1 / self.__clip.fps))
            else:
                # index out of range
                raise IndexError('frame index out of range')

        # other will be raises a TypeError
        if isinstance(index, tuple):
            # advanced indexing error
            raise TypeError('frame index cannot use advanced indexing')
        # other
        raise TypeError(f'frame index indices must be integers or slices, not {name(index)}')

    def __iter__(self):
        self.__video_initialized()
        # reset index every time a new iteration starts
        self.__index = 0

        return self

    def __enter__(self):
        return self

    def __next__(self) -> pygame.Surface:
        # returns the next element, if any
        if self.__index < self.get_total_frame():
            result = self[self.__index]
            self.__index += 1
            return result
        else:
            # raises StopIteration when it has run out
            raise StopIteration

    def __exit__(self, *args, **kwargs) -> None:
        # exit (in raise condition or not)
        if hasattr(self, '_Video__clip') and isinstance(self.__clip, _utils.SupportsClip):
            self.quit()

    def __add__(self, clip_or_clips: typing.Union[_utils.SupportsClip, 'Video', tuple, list]):
        return self.concatenate_clip(clip_or_clips)

    def __sub__(self, sub_duration: _utils.SecondsValue):
        self.__video_initialized()
        asserter(
            isinstance(sub_duration, _utils.SecondsValue),
            TypeError(f'sub_duration must be integers or floats type, not {name(sub_duration)}')
        )
        asserter(
            sub_duration >= 0,
            ValueError(f'sub_duration must be greater than 0, not {sub_duration}')
        )

        if sub_duration != 0:
            self.cut(0, self.__clip.duration - sub_duration)

        return self

    def __mul__(self, loops: int):
        return self.loop(loops)

    def __truediv__(self, value: _utils.Number):
        asserter(
            isinstance(value, _utils.Number),
            TypeError(f'value must be integers or floats type, not {name(value)}')
        )
        asserter(
            value > 0,
            ValueError(f'value must be greater than 0, not {value}')
        )

        return self.cut(0, self.__clip.duration / value)

    def __pow__(self, speed: _utils.Number):
        return self.set_speed(speed)

    def __floordiv__(self, slow_speed: _utils.Number):
        asserter(
            isinstance(slow_speed, _utils.Number),
            TypeError(f'slow_speed must be integers or floats type, not {name(slow_speed)}')
        )

        return self.set_speed(1 / slow_speed)

    def __rshift__(self, distance: _utils.Number):
        return self.next(distance)

    def __lshift__(self, distance: _utils.Number):
        return self.previous(distance)

    def __and__(self, distance: _utils.Number):
        return self.seek(distance)

    def __xor__(self, ratio: _utils.Number):
        return self.jump(ratio)

    def __matmul__(self, rotate: _utils.Number):
        return self.rotate(rotate)

    def __mod__(self, rect: pygame.Rect | tuple | list):
        return self.crop(rect)

    def __or__(self, axis: typing.Literal['x', 'y']):
        return self.mirror(axis)

    def __invert__(self):
        return self.reset()

    def __lt__(self, other: typing.Union[_utils.MilisecondsValue, _utils.SupportsClip, 'Video']):
        return self.__comparison('<', other)

    def __gt__(self, other: typing.Union[_utils.MilisecondsValue, _utils.SupportsClip, 'Video']):
        return self.__comparison('>', other)

    def __le__(self, other: typing.Union[_utils.MilisecondsValue, _utils.SupportsClip, 'Video']):
        return self.__comparison('<=', other)

    def __ge__(self, other: typing.Union[_utils.MilisecondsValue, _utils.SupportsClip, 'Video']):
        return self.__comparison('>=', other)

    def __bool__(self) -> bool:
        return not self.__quit

    def __list__(self) -> list[pygame.Surface]:
        return self[::]

    def __tuple__(self) -> tuple[pygame.Surface]:
        return tuple(self[::])

    def __len__(self) -> int:
        return self.get_total_frame()

    def __repr__(self) -> str:
        filename = self.__clip.filename if isinstance(self.__clip, VideoFileClip) else self.__clip
        return (
            self.__get_mod() + '('
            f'filename_or_clip={filename!r}, '
            f'target_resolution={self.__target_resolution!r}, '
            f'logger={self.__logger!r}, '
            f'has_mask={self.__has_mask!r}, '
            f'load_audio_in_prepare={self.__load_audio_in_prepare!r}, '
            f'cache={self.__cache!r})'
        )

    def __str__(self) -> str:
        clip = self.__clip
        memory_address = f'{id(self):016x}'
        return f'<{self.__get_mod()} {clip=} object at 0x{memory_address.upper()}>'

    def __copy__(self) -> 'Video':
        self.__video_initialized()
        video = Video(
            filename_or_clip=self.__clip.copy(),
            target_resolution=self.__target_resolution,
            logger=self.__logger,
            has_mask=self.__has_mask,
            load_audio_in_prepare=self.__load_audio_in_prepare,
            cache=self.__cache
        )

        video._Video__cache_frames = self.__cache_frames.copy()
        video._Video__cache_full = self.__cache_full

        video.set_size(self.__size)
        video.set_alpha(self.__alpha)

        return video

    def __get_logger(self):
        if self.__logger == '.global':
            global GLOBALS
            return GLOBALS['logger']
        return self.__logger

    def __fill_audio_with_silent(self, audio: _utils.SupportsAudioClip | None) -> _utils.SupportsAudioClip:
        audio_duration = audio.duration if audio else 0

        if (duration_diff := (self.__clip.duration - audio_duration)) > 0:
            fps = _constants.AUDIO_STANDARD_FRAME_RATE
            silent_audio_array = np.zeros((int(duration_diff * fps), 2))
            silent_audio = AudioArrayClip(silent_audio_array, fps=fps)
            if audio:
                return concatenate_audioclips((audio, silent_audio))
            return silent_audio

        return audio

    def __video_initialized(self) -> None:
        asserter(
            not self.__quit,
            pygame.error('Video not initialized')
        )

    def __audio_loaded(self) -> None:
        asserter(
            self.__ready,
            pygame.error('Video not ready yet')
        )

    def __load_audio(self, load: typing.Optional[bool] = None, load_file: bool = False) -> None:

        def write_audio() -> None:
            # check if the video has audio, if not, it will be create a silent audio
            if self.__clip.audio is None:
                self.__clip.audio = self.__fill_audio_with_silent(None)

            # add fps attribute to CompositeAudioClip if it doesn't exist
            if not hasattr(self.__clip.audio, 'fps'):
                self.__clip.audio.fps = _constants.AUDIO_STANDARD_FRAME_RATE

            self.__clip.audio.write_audiofile(self.__audio_file, logger=self.__get_logger())

        if load_file:
            # create temporary audio file
            path = Path(os.environ.get('PYGAME_VIDEO_TEMP', ''))
            self.__audio_file = path / '__temp__.mp3'
            index = 2

            # check whether the audio file name already exists.
            # if it does then it will add an index to create a new temporary audio file name
            global GLOBALS
            while self.__audio_file.exists() or GLOBALS['video'].is_temp_audio_used(self.__audio_file):
                self.__audio_file = path / f'__temp_{index}__.mp3'
                index += 1

        if isinstance(load, bool) and load:
            write_audio()

        elif load is None and not self.__load_audio_in_prepare or self.__ready:
            write_audio()

    def __unload_audio(self) -> None:
        if pygame.get_init():
            self.release()

        # delete audio temporary file if the file are still there
        if self.__audio_file.exists():
            try:
                os.remove(self.__audio_file)
            except PermissionError:
                # access denied, if audio is in use
                pass

    def __stop(self) -> None:
        if not self.__play:
            return

        self.__play = False
        self.__pause = False
        self.__frame_index = 0
        self.__audio_offset = 0

        pygame.mixer.music.stop()

    def __set_effect(self) -> None:
        self.__video_initialized()
        # stop video to stop the video
        self.__stop()

        # clear existing frame cache
        self.clear_cache_frame()

    def __comparison(self,
                     operator: typing.Literal['<', '>', '<=', '>='],
                     value: typing.Union[_utils.MilisecondsValue, _utils.SupportsClip, 'Video']) -> bool:

        clip_duration = self.get_duration()

        method = {
            '<': clip_duration.__lt__,
            '>': clip_duration.__gt__,
            '<=': clip_duration.__le__,
            '>=': clip_duration.__ge__
        }

        if isinstance(value, _utils.Number):
            return method[operator](value)
        elif isinstance(value, _utils.SupportsClip):
            return method[operator](value.duration * 1000)
        elif isinstance(value, Video):
            return method[operator](value.get_duration())

        raise TypeError(f"{operator!r} not supported between instances of '{self.__get_mod()}' and '{name(value)}'")

    def __add_cache(self, frame_index: _utils.Number, frame: pygame.Surface) -> None:
        if not self.__cache_full and self.__cache:
            try:
                self.__cache_frames[frame_index] = frame
            except MemoryError:
                self.__cache_full = True

    def __get_mod(self) -> str:
        cls = self.__class__
        return f'{cls.__module__}.{cls.__qualname__}'

    __deepcopy__ = __copy__
    copy = __copy__

    def reinit(self):
        self.__video_initialized()
        # copy the isinstance clip before close it
        is_clip = isinstance(self.__filename_or_clip, _utils.SupportsClip)
        if is_clip:
            clip = self.__clip.copy()
        else:
            clip = None

        # quit or close then re-init
        self.quit()
        # make a marker
        self.__reinit = 1
        # init again
        self.__init__(
            filename_or_clip=clip if is_clip else self.__filename_or_clip,
            target_resolution=self.__target_resolution,
            logger=self.__logger,
            has_mask=self.__has_mask,
            load_audio_in_prepare=self.__load_audio_in_prepare,
            cache=self.__cache
        )
        # remove a marker
        del self.__reinit

        return self

    def get_original_clip(self) -> _utils.SupportsClip:
        return self.__original_clip

    def get_clip(self) -> _utils.SupportsClip:
        return self.__clip

    def get_filename(self) -> _utils.Path | None:
        if isinstance(self.__clip, VideoFileClip):
            return self.__clip.filename

    def get_temp_audio(self) -> Path:
        return self.__audio_file

    def get_total_cache_frame(self) -> int:
        self.__video_initialized()
        return len(self.__cache_frames)

    def get_original_size(self) -> tuple[int, int]:
        self.__video_initialized()
        return (self.__original_clip.w, self.__original_clip.h)

    def get_clip_size(self) -> tuple[int, int]:
        self.__video_initialized()
        return (self.__clip.w, self.__clip.h)

    def get_size(self) -> tuple[int, int] | None:
        self.__video_initialized()
        return self.__size

    def get_file_size(self, unit: typing.Literal['b', 'kb', 'mb', 'gb']) -> _utils.Number | None:
        unit = unit.lower().strip()
        # check if the clip is composite or image sequence will return None
        if not isinstance(self.__clip, VideoFileClip):
            return

        try:
            # get file size in bytes
            file_size = os.path.getsize(self.__clip.filename)
        except:
            return

        # convert to unit form according to the specified unit
        match unit:
            case 'b':
                return file_size
            case 'kb':
                return file_size / 1_024
            case 'mb':
                return file_size / 1_048_576
            case 'gb':
                return file_size / 1_073_741_824
            case _:
                raise ValueError(f'unknown unit named {unit!r}')

    def get_original_width(self) -> int:
        self.__video_initialized()
        return self.__original_clip.w

    def get_clip_width(self) -> int:
        self.__video_initialized()
        return self.__clip.w

    def get_width(self) -> int | None:
        self.__video_initialized()
        if self.__size:
            return self.__size[0]

    def get_original_height(self) -> int:
        self.__video_initialized()
        return self.__original_clip.h

    def get_clip_height(self) -> int:
        self.__video_initialized()
        return self.__clip.h

    def get_height(self) -> int | None:
        self.__video_initialized()
        if self.__size:
            return self.__size[1]

    def get_loops(self) -> int:
        self.__video_initialized()
        return self.__video_loops

    def get_pos(self) -> _utils.MilisecondsValue | typing.Literal[-1, -2]:
        self.__video_initialized()

        if not self.__ready:
            return -2
        elif not self.__play:
            return -1
        elif self.is_play:
            return self.__audio_offset + pygame.mixer.music.get_pos()

        return self.get_duration()

    def get_alpha(self) -> int:
        self.__video_initialized()
        return self.__alpha

    def get_duration(self) -> _utils.MilisecondsValue:
        self.__video_initialized()
        return self.__clip.duration * 1000

    def get_start(self) -> _utils.MilisecondsValue:
        self.__video_initialized()
        return self.__clip.start * 1000

    def get_end(self) -> _utils.MilisecondsValue | None:
        self.__video_initialized()
        if self.__clip.end:
            return self.__clip.end * 1000

    def get_total_frame(self) -> int:
        self.__video_initialized()
        return int(self.__clip.duration * self.__clip.fps)

    def get_fps(self) -> _utils.Number:
        self.__video_initialized()
        return self.__clip.fps

    def get_volume(self) -> float:
        self.__video_initialized()
        self.__audio_loaded()
        if self.__mute:
            return self.__volume
        else:
            return pygame.mixer.music.get_volume()

    def get_frame_index(self) -> int:
        self.__video_initialized()
        return self.__frame_index

    def get_frame(self, index_time: _utils.Number, get_original: bool = False) -> pygame.Surface:
        self.__video_initialized()
        frame = self.__clip.get_frame(index_time)
        frame_surface = pygame.surfarray.make_surface(frame.swapaxes(0, 1))

        if not get_original:
            if self.__size:
                frame_surface = pygame.transform.scale(frame_surface, self.__size)
            frame_surface.set_alpha(self.__alpha)

        return frame_surface

    def get_frame_array(self, index_time: _utils.Number, get_original: bool = False):
        frame = self.get_frame(index_time, get_original)
        array = pygame.surfarray.pixels3d(frame)

        return np.transpose(array, (1, 0, 2))

    def iter_chunk_cache_frame(self) -> typing.Generator[tuple[pygame.Surface, int | typing.Literal[-1], range], None, None]:
        self.__set_effect()
        asserter(
            self.__cache,
            pygame.error("cache doesn't apply to this video")
        )

        logger = proglog.default_bar_logger(self.__get_logger())
        range_iterable = range(self.get_total_frame())
        blank_surface = pygame.Surface((self.__clip.w, self.__clip.h), pygame.SRCALPHA)

        blank_surface.fill('black')

        logger(message='PyGVideo - Create cache frames')

        for frame_index in logger.iter_bar(chunk=range_iterable, bar_message=lambda _ : 'Creating cache frames'):
            try:
                frame = self.get_frame(frame_index * (1 / self.__clip.fps), get_original=True)
                self.__add_cache(frame_index, frame)

                # if the cache can no longer be saved, the generator exits
                if self.__cache_full:
                    break

                send_value = yield (frame, frame_index, range_iterable)
            except:
                send_value = yield (blank_surface, frame_index, range_iterable)

            if send_value:
                break

        if self.__cache_full:
            logger(message='PyGVideo - Done with full memory.')
        elif send_value:
            logger(message=f'PyGVideo - Done with the generator stopped. Reason: {send_value}')
        else:
            logger(message='PyGVideo - Done.')

        yield (blank_surface, -1, range_iterable)

    @property
    def filename_or_clip(self):
        return self.__filename_or_clip

    @property
    def target_resolution(self):
        return self.__target_resolution

    @property
    def logger(self):
        return self.__logger

    @property
    def has_mask(self) -> bool:
        return self.__has_mask

    @property
    def load_audio_in_prepare(self):
        return self.__load_audio_in_prepare

    @property
    def cache(self):
        return self.__cache

    @property
    def save_clip_to_global(self):
        return self.__save_clip_to_global

    @property
    def clip(self) -> _utils.SupportsClip:
        return self.__clip

    @property
    def size(self) -> tuple[int, int]:
        if self.__size:
            return self.__size
        return self.__clip.size

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]

    @property
    def is_cache_full(self) -> bool:
        return self.__cache_full

    @property
    def is_ready(self) -> bool:
        return self.__ready

    @property
    def is_pause(self) -> bool:
        return self.__pause

    @property
    def is_play(self) -> bool:
        if not self.__ready:
            return False
        elif self.__pause:
            return self.__play
        return self.__play and pygame.mixer.music.get_busy()

    @property
    def is_mute(self) -> bool:
        return self.__mute

    @property
    def is_quit(self) -> bool:
        return self.__quit

    @property
    def is_close(self) -> bool:
        return self.__quit

    @clip.setter
    def clip(self, new_clip: _utils.SupportsClip) -> None:
        asserter(
            isinstance(new_clip, _utils.SupportsClip),
            TypeError(f'clip must be VideoClip, not {name(new_clip)}')
        )
        asserter(
            not (new_clip.duration is None or 
            getattr(new_clip, 'fps', None) is None or 
            (new_clip.audio and new_clip.audio.duration is None)),
            ValueError(
                "VideoClip doesn't have the required valid attributes of "
                'Video: clip.duration, clip.fps, and clip.audio.duration if '
                'clip.audio exists'
            )
        )

        if self.__save_clip_to_global and hasattr(self, '_Video__clip'):
            global GLOBALS
            GLOBALS['video-clip'].append(self.__clip)

        self.__clip = new_clip

    @size.setter
    def size(self, new_size: tuple[_utils.Number, _utils.Number] | list[_utils.Number] | None) -> None:
        self.set_size(new_size)

    @width.setter
    def width(self, new_width: _utils.Number) -> None:
        self.set_size((new_width, self.height))

    @height.setter
    def height(self, new_height: _utils.Number) -> None:
        self.set_size((self.width, new_height))

    @is_ready.setter
    def is_ready(self, boolean: bool) -> None:
        if boolean:
            self.prepare()
        else:
            self.release()

    @is_pause.setter
    def is_pause(self, boolean: bool) -> None:
        if boolean:
            self.pause()
        else:
            self.unpause()

    @is_play.setter
    def is_play(self, boolean: bool) -> None:
        if boolean:
            self.play()
        else:
            self.stop()

    @is_mute.setter
    def is_mute(self, boolean: bool) -> None:
        if boolean:
            self.mute()
        else:
            self.unmute()

    def draw_and_update(self,
                        screen_surface: typing.Optional[pygame.Surface] = None,
                        pos: typing.Any | pygame.Rect = (0, 0)) -> pygame.Surface:

        self.__video_initialized()
        asserter(
            self.__play,
            pygame.error('the video is not playing yet. Use the .play() method before call this method')
        )

        music_pos = pygame.mixer.music.get_pos()

        if music_pos != -1:
            self.__frame_index = int(((self.__audio_offset + music_pos) / 1000) * self.__clip.fps)
        else:
            self.__frame_index = self.get_total_frame()

        # logic loops
        if not self.is_play and self.__loops != 0:
            self.__audio_offset = 0
            self.__video_loops += 1
            self.stop()
            self.play(self.__loops - 1)

        try:
            # check if the frame index is already in cache_frames, if not it will be loaded and saved to cache_frames
            if self.__frame_index in self.__cache_frames:
                frame_surface = self.__cache_frames[self.__frame_index]
            else:
                frame_surface = self.get_frame(self.__frame_index * (1 / self.__clip.fps), get_original=True)
                self.__add_cache(self.__frame_index, frame_surface)

            if self.__size:
                frame_surface = pygame.transform.scale(frame_surface, self.__size)
        except:
            # if there is an error in the frame index, it will load an empty surface image
            size_surface = self.__size if self.__size else (self.__clip.w, self.__clip.h)
            frame_surface = pygame.Surface(size_surface)
            frame_surface.fill('black')

        frame_surface.set_alpha(self.__alpha)

        if screen_surface:
            screen_surface.blit(frame_surface, pos)

        return frame_surface

    def preview(self, *args, _type_: typing.Literal['clip', 'display-in-notebook', 'video-preview'] = 'video-preview', **kwargs):
        self.__video_initialized()

        match _type_:

            case 'clip':
                self.__clip.preview(*args, **kwargs)

            case 'display-in-notebook':
                self.__clip.display_in_notebook(*args, **kwargs)

            case 'video-preview':
                video_preview(self, *args, **kwargs)

            case _:
                raise ValueError(f'unknown _type_ named {_type_!r}')

        return self

    def prepare(self):
        self.__video_initialized()

        if not self.__ready:
            # check if video class object is in use, if it is in use it will raise error message
            asserter(
                os.environ['PYGAME_VIDEO_USED'] != '1',
                pygame.error('cannot use 2 videos at the same time')
            )

            # if the audio temp is lost or deleted, it will automatically load the audio
            if not self.__audio_file.exists():
                self.__load_audio(load=True)

            # load audio ke mixer
            pygame.mixer.music.load(self.__audio_file)

            self.__ready = True
            self.__video_loops = 0

            os.environ['PYGAME_VIDEO_USED'] = '1'

        return self

    def release(self):
        self.__video_initialized()

        if self.__ready:
            self.__stop()

            self.__ready = False

            # unload audio
            pygame.mixer.music.unload()

            os.environ['PYGAME_VIDEO_USED'] = '0'

        return self

    def play(self, loops: int = 0, start: _utils.SecondsValue = 0):
        self.__video_initialized()
        self.__audio_loaded()
        asserter(
            isinstance(loops, int),
            TypeError(f'loops must be integers type, not {name(loops)}')
        )
        asserter(
            isinstance(start, _utils.SecondsValue),
            TypeError(f'start must be integers or floats type, not {name(start)}')
        )

        if not self.is_play:
            self.__play = True
            self.__loops = loops
            self.__frame_index = 0
            self.__audio_offset = start * 1000

            pygame.mixer.music.play(start=start)

        return self

    def preplay(self, *args, **kwargs):
        self.prepare()
        return self.play(*args, **kwargs)

    def stop(self):
        self.__video_initialized()
        self.__audio_loaded()

        self.__stop()

        return self

    def restop(self):
        return self.release()

    def pause(self):
        self.__video_initialized()
        self.__audio_loaded()

        if self.__play and not self.__pause:
            self.__pause = True

            pygame.mixer.music.pause()

        return self

    def unpause(self):
        self.__video_initialized()
        self.__audio_loaded()

        if self.__pause:
            self.__pause = False

            pygame.mixer.music.unpause()

        return self

    def toggle_pause(self):
        if self.__pause:
            return self.unpause()
        else:
            return self.pause()

    def mute(self):
        if not self.__mute:
            self.__volume = self.get_volume()
            self.set_volume(0, set=True)
            self.__mute = True

        return self

    def unmute(self):
        if self.__mute:
            self.__mute = False
            self.set_volume(self.__volume, set=True)
            self.__volume = 0.0

        return self

    def toggle_mute(self):
        if self.__mute:
            return self.unmute()
        else:
            return self.mute()

    def jump(self, ratio: _utils.Number):
        asserter(
            isinstance(ratio, _utils.Number),
            TypeError(f'ratio must be integers or floats, not {name(ratio)}')
        )

        return self.set_pos(self.__clip.duration * get_save_value(ratio, 1, 0))

    def next(self, distance: _utils.SecondsValue):
        asserter(
            isinstance(distance, _utils.Number),
            TypeError(f'distance must be integers or floats, not {name(distance)}')
        )
        asserter(
            distance >= 0,
            ValueError('distance cannot be negative values')
        )

        if (move := self.get_pos() + distance * 1000) <= self.get_duration():
            return self.set_pos(move / 1000)
        return self.set_pos(self.__clip.duration)

    def previous(self, distance: _utils.SecondsValue):
        asserter(
            isinstance(distance, _utils.Number),
            TypeError(f'distance must be integers or floats, not {name(distance)}')
        )
        asserter(
            distance >= 0,
            ValueError('distance cannot be negative values')
        )

        if (move := self.get_pos() - distance * 1000) >= 0:
            return self.set_pos(move / 1000)
        return self.set_pos(0)

    def seek(self, distance: _utils.Number):
        asserter(
            isinstance(distance, _utils.Number),
            TypeError(f'distance must be integers or floats, not {name(distance)}')
        )

        if distance <= 0:
            return self.previous(abs(distance))
        return self.next(distance)

    def create_cache_frame(self, max_frame: typing.Optional[int] = None):
        asserter(
            isinstance(max_frame, int | None),
            TypeError(f'max_frame must be integers or None, not {name(max_frame)}')
        )

        warnings.warn(
            f'From {self.__get_mod()}.create_cache_frame: '
            'Cache will risk taking up a lot of memory and can hamper device performance. '
            'Try to set frame limits (you can set at `max_frame` parameter as integers value) '
            'according to your needs and adjust them to the memory size that the device can '
            'accommodate.',
            category=UserWarning,
            stacklevel=2
        )

        if max_frame is None:
            max_frame = float('inf')
        else:
            if max_frame <= 0:
                return self

            # subtract 2 because the index value is offset by 2 indices
            max_frame -= 2

        func = self.iter_chunk_cache_frame()

        for _, index, _ in func:
            if index > max_frame:
                func.send('Maximum frame reached.')
                func.close()
                break

        return self

    def clear_cache_frame(self):
        self.__cache_frames.clear()
        self.__cache_full = False

        return self

    def reset(self):
        self.__set_effect()

        self.clip = self.__original_clip.copy()
        self.__size = None
        self.__alpha = 255

        self.__unload_audio()
        self.__load_audio()

        return self

    def with_effects(self,
                     _effect_s_or_method_: _utils.MoviePyFx | tuple[_utils.MoviePyFx] | list[_utils.MoviePyFx] | _utils.NameMethod,
                     *args, **kwargs):
        self.__set_effect()

        if not isinstance(_effect_s_or_method_, _utils.NameMethod):
            if isinstance(_effect_s_or_method_, tuple | list):
                self.clip = self.__clip.with_effects(_effect_s_or_method_)
            else:
                self.clip = self.__clip.with_effects((_effect_s_or_method_(*args, **kwargs),))
        else:
            method = getattr(self.__clip, _effect_s_or_method_)
            self.clip = method(*args, **kwargs)

        self.__unload_audio()
        self.__load_audio()

        return self

    def invert_colors(self):
        return self.with_effects(fx.InvertColors)

    def grayscale(self):
        return self.with_effects(fx.BlackAndWhite)

    def split_colors(self, *args, **kwargs) -> tuple['Video', 'Video', 'Video']:
        self.__set_effect()

        self.__stop()

        logger = proglog.default_bar_logger(self.__get_logger())
        total_frame = self.get_total_frame()
        channel = 0
        frames = []
        rgb_videos = []
        color_channel = {
            0: 'RED',
            1: 'GREEN',
            2: 'BLUE',
        }

        def append_video() -> None:
            nonlocal rgb_videos, frames

            rgb_videos.append(
                Video(
                    ImageSequenceClip(
                        frames.copy(),
                        fps=self.__clip.fps
                    ).with_audio(self.__clip.audio),
                    *args, **kwargs
                )
            )

            frames.clear()

        logger(message='PyGVideo - Split colors video')

        for i in logger.iter_bar(chunk=range(total_frame * 3),
                                 bar_message=lambda _ : f'Separating {channel + 1}/3 ({color_channel[channel]})'):
            frame_index = i % total_frame

            if frame_index == 0 and i != 0:
                # red and green video
                append_video()
                channel += 1

            try:
                frame = self.__clip.get_frame(frame_index * (1 / self.__clip.fps))
                channel_frame = np.zeros_like(frame)
                channel_frame[:, :, channel] = frame[:, :, channel]
                frames.append(channel_frame)
            except:
                pass

        # blue video
        append_video()

        logger(message='PyGVideo - Done.')

        return tuple(rgb_videos)

    def crop(self, rect: pygame.Rect | tuple | list):
        asserter(
            isinstance(rect, pygame.Rect | tuple | list),
            TypeError(f'rect must be rects, tuples or lists, not {name(rect)}')
        )

        if isinstance(rect, tuple | list):
            rect = pygame.Rect(*rect)

        asserter(
            pygame.Rect((0, 0), self.get_clip_size()).contains(rect),
            ValueError('rect outside the video area boundaries')
        )

        self.with_effects('cropped', x1=rect.left,
                                     y1=rect.top,
                                     width=rect.width,
                                     height=rect.height)
        return self.resize(rect.size)

    def rotate(self, rotate: _utils.Number):
        asserter(
            isinstance(rotate, _utils.Number),
            TypeError(f'rotate must be a integers or floats, not {name(rotate)}')
        )

        return self.with_effects('rotated', rotate % 360)

    def loop(self, loops: int):
        asserter(
            isinstance(loops, int),
            TypeError(f'loops must be integers, not {name(loops)}')
        )
        asserter(
            loops > 0,
            ValueError(f'loops must be greater than 0, not {loops}')
        )

        return self.with_effects(fx.Loop, loops)

    def resize(self, scale_or_size: _utils.Number | tuple[_utils.Number, _utils.Number] | list[_utils.Number]):
        if isinstance(scale_or_size, _utils.Number):
            return self.with_effects('resized', scale_or_size)
        return self.with_effects('resized', tuple(map(int, scale_or_size)))

    def mirror(self, axis: typing.Literal['x', 'y']):
        match axis:
            case 'x':
                return self.with_effects(fx.MirrorX)
            case 'y':
                return self.with_effects(fx.MirrorY)
            case _:
                raise ValueError(f'unknown axis named {axis!r}')

    def fade(self,
             type: typing.Literal['in', 'out'],
             duration: _utils.SecondsValue,
             initial_color: typing.Optional[list[int]] = None):
        match type:
            case 'in':
                return self.with_effects(fx.FadeIn, duration, initial_color)
            case 'out':
                return self.with_effects(fx.FadeOut, duration, initial_color)
            case _:
                raise ValueError(f'unknown type named {type!r}')

    def cut(self, start: _utils.SecondsValue, end: _utils.SecondsValue):
        asserter(
            isinstance(start, _utils.SecondsValue),
            TypeError(f'start must be integers or floats, not {name(start)}')
        )
        asserter(
            isinstance(end, _utils.SecondsValue),
            TypeError(f'end must be integers or floats, not {name(end)}')
        )

        return self.with_effects('subclipped', start, end)

    def reverse(self, step_sub: _utils.Number = 0.01, max_retries: int = 12):
        asserter(
            isinstance(step_sub, _utils.Number),
            TypeError(f'step_sub must be integers or floats, not {name(step_sub)}')
        )
        asserter(
            isinstance(max_retries, int),
            TypeError(f'max_retries must be integers, not {name(max_retries)}')
        )
        asserter(
            0.001 <= step_sub <= 1,
            ValueError(f'step_sub must be in the range of (0.001 to 1)s, not {step_sub}')
        )
        asserter(
            max_retries > 0,
            ValueError(f'max_retries must be greater than 0, not {max_retries}')
        )

        warnings.warn(
            f'From {self.__get_mod()}.reverse: '
            'Reverse will cut the duration of the main clip. '
            'Use the most minimal max_retries and sub steps possible.',
            category=UserWarning,
            stacklevel=2
        )

        current_time = self.__clip.duration
        time_func = lambda t : self.__clip.duration - t # in moviepy 2.1.1: self.__clip.duration - t - 1
        apply_to = ('mask', 'audio')

        while max_retries > 0:
            try:
                self.cut(0, current_time)
                # useless (moviepy ~2.1.1). It causes OSError exception
                # self.with_effects(fx.TimeMirror)

                # using source code from time_mirror version moviepy 1.0.3
                self.clip = self.__clip.time_transform(time_func=time_func,
                                                       apply_to=apply_to,
                                                       keep_duration=True)
                break
            except:
                current_time -= step_sub
                max_retries -= 1
                if current_time <= 0:
                    break

        return self

    def concatenate_clip(self,
                         clip_or_clips: typing.Union[_utils.SupportsClip, 'Video', tuple, list],
                         *args, **kwargs):

        self.__set_effect()

        typeerror = lambda x : TypeError(f'cannot concatenate clip type with {name(x)}')
        check = lambda x : asserter(
            isinstance(x, _utils.SupportsClip | Video),
            typeerror(x)
        )

        if isinstance(clip_or_clips, tuple | list):
            clips = []
            for c in clip_or_clips:
                check(c)
                clips.append(c if isinstance(c, _utils.SupportsClip) else c.clip)
            self.clip = concatenate_videoclips((self.__clip, *clips), *args, **kwargs)

        elif isinstance(clip_or_clips, _utils.SupportsClip | Video):
            check(clip_or_clips)
            clip = clip_or_clips if isinstance(clip_or_clips, _utils.SupportsClip) else clip_or_clips.clip
            self.clip = concatenate_videoclips((self.__clip, clip), *args, **kwargs)

        else:
            raise typeerror(clip_or_clips)

        self.__unload_audio()
        self.__load_audio()

        return self

    def add_volume(self, add: _utils.Number, max_volume: _utils.Number = 1, set: bool = False):
        asserter(
            isinstance(add, _utils.Number),
            TypeError(f'add must be integers or floats, not {name(add)}')
        )
        asserter(
            isinstance(max_volume, _utils.Number),
            TypeError(f'max_volume must be integers or floats, not {name(max_volume)}')
        )
        asserter(
            add >= 0,
            ValueError('add cannot be negative values')
        )
        asserter(
            max_volume >= 0,
            ValueError('max_volume cannot be negative values')
        )

        return self.set_volume(min(self.get_volume() + add, max_volume), set=set)

    def sub_volume(self, sub: _utils.Number, min_volume: _utils.Number = 0, set: bool = False):
        asserter(
            isinstance(sub, _utils.Number),
            TypeError(f'sub must be integers or floats, not {name(sub)}')
        )
        asserter(
            isinstance(min_volume, _utils.Number),
            TypeError(f'min_volume must be integers or floats, not {name(min_volume)}')
        )
        asserter(
            sub >= 0,
            ValueError('sub cannot be negative values')
        )
        asserter(
            min_volume >= 0,
            ValueError('min_volume cannot be negative values')
        )

        return self.set_volume(max(self.get_volume() - sub, min_volume), set=set)

    def set_alpha(self, value: int):
        self.__video_initialized()
        asserter(
            isinstance(value, int),
            TypeError(f'value must be integers, not {name(value)}')
        )

        self.__alpha = get_save_value(value, 255, 0)

        return self

    def set_size(self, size: tuple[_utils.Number, _utils.Number] | list[_utils.Number] | None):
        self.__video_initialized()

        if size is None:
            self.__size = None
            return

        size_len = len(size)

        asserter(
            isinstance(size, tuple | list),
            TypeError(f'size must be tuples, lists or None, not {name(size)}')
        )
        asserter(
            size_len == 2,
            ValueError(f'size must contain 2 values, not {size_len}')
        )

        self.__size = tuple(map(int, size))

        return self

    def set_audio(self, audio: _utils.SupportsAudioClip):
        self.__video_initialized()
        asserter(
            isinstance(audio, _utils.SupportsAudioClip),
            TypeError(f'audio must be AudioClip, not {name(audio)}')
        )
        asserter(
            getattr(audio, 'duration', None) is not None,
            AttributeError('audio must have duration attribute')
        )

        self.__stop()

        self.__clip.audio = self.__fill_audio_with_silent(audio)

        self.__unload_audio()
        self.__load_audio()

        return self

    def set_speed(self, speed: _utils.Number):
        asserter(
            isinstance(speed, _utils.Number),
            TypeError(f'speed must be a integers or floats, not {name(speed)}')
        )
        asserter(
            speed > 0,
            ValueError(f'speed must be greater than 0, not {speed}')
        )

        return self.with_effects('with_speed_scaled', speed)

    def set_fps(self, fps: _utils.Number):
        asserter(
            isinstance(fps, _utils.Number),
            TypeError(f'fps must be a integers or floats, not {name(fps)}')
        )
        asserter(
            fps > 0,
            ValueError(f'fps must be greater than 0, not {fps}')
        )

        return self.with_effects('with_fps', fps)

    def set_volume(self, volume: _utils.Number, set: bool = False):
        self.__video_initialized()
        self.__audio_loaded()
        asserter(
            isinstance(volume, _utils.Number),
            TypeError(f'volume must be a integers or floats, not {name(volume)}')
        )

        # if the audio is currently muted with .mute(), then it will
        # not be able to be changed unless the `set` parameter is True
        if not self.__mute or set:
            pygame.mixer.music.set_volume(get_save_value(volume, 1, 0))

        return self

    def set_pos(self, pos: _utils.SecondsValue):
        self.__video_initialized()
        self.__audio_loaded()
        asserter(
            isinstance(pos, _utils.SecondsValue),
            TypeError(f'pos must be a integers or floats, not {name(pos)}')
        )

        self.__audio_offset = pos * 1000

        if 0 <= self.__audio_offset <= self.get_duration():
            pygame.mixer.music.stop()
            pygame.mixer.music.play(start=pos)
            if self.__pause:
                pygame.mixer.music.pause()
        else:
            raise ValueError(f'pos {self.__audio_offset} is out of music range')

        return self

    def handle_event(self,
                     event: pygame.event.Event,
                     volume_adjustment: _utils.Number = 0.05,
                     seek_adjustment: _utils.SecondsValue = 5) -> int | None:

        self.__video_initialized()
        self.__audio_loaded()
        asserter(
            isinstance(event, pygame.event.Event),
            TypeError(f'event must be Event, not {name(event)}')
        )

        if event.type == pygame.KEYDOWN:

            if event.key == pygame.K_UP:
                self.add_volume(volume_adjustment)
                return event.key

            elif event.key == pygame.K_DOWN:
                self.sub_volume(volume_adjustment)
                return event.key

            elif event.key == pygame.K_LEFT:
                self.previous(seek_adjustment)
                return event.key

            elif event.key == pygame.K_RIGHT:
                self.next(seek_adjustment)
                return event.key

            elif event.key == pygame.K_0:
                self.jump(0)
                return event.key

            elif event.key == pygame.K_1:
                self.jump(0.1)
                return event.key

            elif event.key == pygame.K_2:
                self.jump(0.2)
                return event.key

            elif event.key == pygame.K_3:
                self.jump(0.3)
                return event.key

            elif event.key == pygame.K_4:
                self.jump(0.4)
                return event.key

            elif event.key == pygame.K_5:
                self.jump(0.5)
                return event.key

            elif event.key == pygame.K_6:
                self.jump(0.6)
                return event.key

            elif event.key == pygame.K_7:
                self.jump(0.7)
                return event.key

            elif event.key == pygame.K_8:
                self.jump(0.8)
                return event.key

            elif event.key == pygame.K_9:
                self.jump(0.9)
                return event.key

            elif event.key in (pygame.K_SPACE, pygame.K_p):
                self.toggle_pause()
                return event.key

            elif event.key == pygame.K_m:
                self.toggle_mute()
                return event.key

    def quit(self):
        if not self.__quit:
            # close up all assets
            self.clear_cache_frame()
            self.__clip.close()
            self.__original_clip.close()
            self.__unload_audio()

            self.__quit = True
            self.__play = False
            self.__ready = False
            self.__pause = False

        return self

    # same as .quit()
    __del__ = quit
    close = quit

GLOBALS: dict[typing.Literal['video', 'video-clip', 'logger'],
              GlobalVideo | list[_utils.SupportsClip] | str | typing.Any
] = {
    'video': GlobalVideo(),
    'video-clip': [],
    'logger': 'bar'
}

def ignore_warn(category: type[Warning] = UserWarning) -> None:
    warnings.filterwarnings('ignore', category=category)

def enable_warn() -> None:
    warnings.resetwarnings()

def get_global_logger():
    global GLOBALS
    return GLOBALS['logger']

def set_global_logger(logger) -> None:
    global GLOBALS
    GLOBALS['logger'] = logger

def mute_debug() -> None:
    ignore_warn()
    set_global_logger(None)

def unmute_debug() -> None:
    enable_warn()
    set_global_logger('bar')

def quit(show_log: bool = True) -> None:
    # stop the audio
    if pygame.get_init():
        pygame.mixer.music.stop()

    global GLOBALS
    global_video = GLOBALS['video']

    # loop all existing videos
    for video in global_video:
        try:
            video.quit()
        except Exception as e:
            if show_log:
                print(f'Error durring quit / close Video > {video} => {name(e)}: {e}')

    global_video.clear()

def quit_all(show_log: bool = True) -> None:
    # step one, quit all videos
    quit(show_log=show_log)

    # step two, quit all video clips
    global GLOBALS
    global_video_clip = GLOBALS['video-clip']

    # loop all existing video clips
    for videoclip in global_video_clip:
        try:
            videoclip.close()
        except Exception as e:
            if show_log:
                print(f'Error durring quit / close VideoClip > {videoclip} => {name(e)}: {e}')

    global_video_clip.clear()

close = quit
close_all = quit_all