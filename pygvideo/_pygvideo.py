import pygame
import warnings
import proglog
import tqdm
import numpy as np
import moviepy.video.fx as fx
from moviepy import (
    AudioArrayClip,
    concatenate_videoclips,
    concatenate_audioclips
)
from ._video_preview import video_preview
from ._utils import (
    VideoFileClip,
    CompositeVideoClip,
    ImageSequenceClip,
    global_video,
    PathL as Path,
    typing,
    os,
    asserter,
    name
)
from . import _utils

__all__ = [
    'Video',
    'ignore_warn',
    'enable_warn',
    'quit',
    'close'
]

os.environ['PYGAME_VIDEO_USED'] = '0'

class Video:

    def __init__(

            self,
            filename_or_clip: _utils.Path | _utils.SupportsClip,
            target_resolution: typing.Optional[typing.Any] = None,
            logger: typing.Literal['bar', None] = 'bar',
            has_mask: bool = False,
            load_audio_in_prepare: bool = True,
            cache: bool = True

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
            supported by ffmpeg. Supports clip class: `VideoFileClip`, `CompositeVideoClip`, and
            `ImageSequenceClip`
        target_resolution:
            Target resolution. Almost the same as resize.
        looger:
            Showing logger/bar. If None, no logger will be shown.
        has_mask:
            Supports transparency/alpha. Depends on video format type.
        load_audio_in_prepare:
            load or precisely write the temp audio when prepare is called.
        cache:
            save frame to cache. (not recommended for videos with large duration and size).

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

        pygvideo.quit()
        pygame.quit()
        ```

        """

        self.filename_or_clip = filename_or_clip
        self.target_resolution = target_resolution
        self.logger = logger
        self.has_mask = bool(has_mask)
        self.load_audio_in_prepare = bool(load_audio_in_prepare)
        self.cache = bool(cache)

        if isinstance(logger, str):
            self.logger = logger.lower().strip()

        asserter(
            self.logger in ('bar', None),
            ValueError(f"logger must be either 'bar' or None, not {self.logger}")
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
        self.__volume = 0
        self.__alpha = 255

        # initialize moviepy video clip
        if isinstance(filename_or_clip, _utils.SupportsClip):
            self.clip = filename_or_clip
        else:
            self.clip = VideoFileClip(
                filename=filename_or_clip,
                has_mask=has_mask,
                target_resolution=target_resolution
            )

        # save an original clip
        self.__original_clip = self.__clip.copy()

        # load the temporary audio
        # The _reinit property will appear if the reinit method is called,
        # this is a sign that the init method was called because of reinit
        # or not which can avoid creating a new file.
        self.__load_audio(load_file=not hasattr(self, '_reinit'))

        # add Video to global
        global _GLOBAL_VIDEO
        _GLOBAL_VIDEO.append(self)

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
            index = index if index >= 0 else total_frame + index

            if 0 <= index < total_frame:
                return self.get_frame(index * (1 / self.__clip.fps))
            else:
                # index out of range
                raise IndexError('frame index out of range')

        # other will be raises a TypeError
        raise TypeError(f'frame index indices must be integers or slices, not {name(index)}')

    def __iter__(self) -> typing.Self:
        # reset index every time a new iteration starts
        self.__index = 0
        # returns the object itself as an iterator
        return self

    def __enter__(self) -> typing.Self:
        # returns an instance of the class itself
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

    def __add__(self, value: typing.Union[_utils.SupportsClip, 'Video', tuple, list]) -> typing.Self:
        self.concatenate_clip(value)
        return self

    def __mul__(self, value: int) -> typing.Self:
        self.loop(value)
        return self

    def __truediv__(self, value: int) -> typing.Self:
        asserter(
            isinstance(value, int),
            TypeError(f'value must be integers type, not {name(value)}')
        )
        asserter(
            value > 0,
            ValueError(f'value must be greater than 0, not {value}')
        )

        self.cut(0, self.__clip.duration / value)
        return self

    def __pow__(self, value: _utils.Number) -> typing.Self:
        self.set_speed(value)
        return self

    def __floordiv__(self, value: _utils.Number) -> typing.Self:
        self.set_speed(1 / value)
        return self

    def __rshift__(self, value: _utils.Number) -> typing.Self:
        self.next(value)
        return self

    def __lshift__(self, value: _utils.Number) -> typing.Self:
        self.previous(value)
        return self

    def __and__(self, value: _utils.Number) -> typing.Self:
        self.seek(value)
        return self

    def __xor__(self, value: _utils.Number) -> typing.Self:
        self.jump(value)
        return self

    def __matmul__(self, value: _utils.Number) -> typing.Self:
        self.rotate(value)
        return self

    def __mod__(self, value: pygame.Rect) -> typing.Self:
        self.crop(value)
        return self

    def __or__(self, value: typing.Literal['x', 'y']) -> typing.Self:
        self.mirror(value)
        return self

    def __invert__(self) -> typing.Self:
        self.reset()
        return self

    def __lt__(self, value: typing.Union[_utils.MilisecondsValue, _utils.SupportsClip, 'Video']) -> bool:
        return self.__comparison('<', value)

    def __gt__(self, value: typing.Union[_utils.MilisecondsValue, _utils.SupportsClip, 'Video']) -> bool:
        return self.__comparison('>', value)

    def __le__(self, value: typing.Union[_utils.MilisecondsValue, _utils.SupportsClip, 'Video']) -> bool:
        return self.__comparison('<=', value)

    def __ge__(self, value: typing.Union[_utils.MilisecondsValue, _utils.SupportsClip, 'Video']) -> bool:
        return self.__comparison('>=', value)

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
            f'{".".join(self.__get_mod())}('
            f'filename_or_clip={repr(filename)}, '
            f'target_resolution={repr(self.target_resolution)}, '
            f'logger={repr(self.logger)}, '
            f'has_mask={repr(self.has_mask)}, '
            f'load_audio_in_prepare={repr(self.load_audio_in_prepare)}, '
            f'cache={repr(self.cache)})'
        )

    def __str__(self) -> str:
        filename = self.__clip.filename if isinstance(self.__clip, VideoFileClip) else self.__clip
        return f'<{".".join(self.__get_mod())} filename_or_clip={repr(filename)}>'

    def __copy__(self) -> 'Video':
        return self.copy()

    def __load_audio(self, load: typing.Optional[bool] = None, load_file: bool = False) -> None:

        def write_audio():
            # trim audio to avoid excess audio duration
            audio = self.__clip.audio#.subclip(0, self.__clip.duration - 0.15)
            # check if the video has audio, otherwise it will raise an error
            asserter(
                audio is not None,
                OSError('video format has no audio. Video only supports video formats with audio')
            )
            # add fps attribute to CompositeAudioClip if it doesn't exist
            if not hasattr(audio, 'fps'):
                audio.fps = 44100 # set to standard frame rate, (44100 Hz)
            logger = 'bar' if self.logger == 'bar' else None
            audio.write_audiofile(self.__audio_file, logger=logger)

        if load_file:
            # create temporary audio file
            path = Path(os.environ.get('PYGAME_VIDEO_TEMP', ''))
            self.__audio_file = path / '__temp__.mp3'
            index = 2
            # check whether the audio file name already exists.
            # if it does then it will add an index to create a new temporary audio file name
            global _GLOBAL_VIDEO
            while self.__audio_file.exists() or _GLOBAL_VIDEO.is_temp_audio_used(self.__audio_file):
                self.__audio_file = path / f'__temp_{index}__.mp3'
                index += 1

        if isinstance(load, bool) and load:
            write_audio()

        elif load is None and not self.load_audio_in_prepare or self.__ready:
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

    def __check_video_initialized(self) -> None:
        asserter(
            not self.__quit,
            pygame.error('Video not initialized')
        )

    def __check_audio_loaded(self) -> None:
        asserter(
            self.__ready,
            pygame.error('Video not ready yet')
        )

    def __stop(self) -> None:
        if not self.__play:
            return

        self.__play = False
        self.__pause = False
        self.__frame_index = 0
        self.__audio_offset = 0

        pygame.mixer.music.stop()

    def __set_effect(self) -> None:
        self.__check_video_initialized()

        # stop video to stop the video
        self.__stop()

        # clear existing frame cache
        self.clear_cache_frame()

    def __comparison(self, operator: typing.Literal['<', '>', '<=', '>='], value: typing.Union[_utils.MilisecondsValue, _utils.SupportsClip, 'Video']) -> bool:
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

        raise TypeError(f"{repr(operator)} not supported between instances of '{'.'.join(self.__get_mod())}' and '{name(value)}'")

    def __add_cache(self, frame_index: _utils.Number, frame: pygame.Surface) -> None:
        if not self.__cache_full and self.cache:
            try:
                self.__cache_frames[frame_index] = frame
            except MemoryError:
                self.__cache_full = True

    def __get_mod(self) -> tuple[str, str]:
        cls = self.__class__
        return (cls.__module__, cls.__qualname__)

    def reinit(self) -> None:
        # quit or close then re-init
        self.quit()
        # make a marker
        self._reinit = 1
        # init again
        self.__init__(
            filename_or_clip=self.filename_or_clip,
            target_resolution=self.target_resolution,
            logger=self.logger,
            has_mask=self.has_mask,
            load_audio_in_prepare=self.load_audio_in_prepare,
            cache=self.cache
        )
        # remove a marker
        del self._reinit

    def copy(self) -> 'Video':
        video = Video(
            filename_or_clip=self.__clip.copy(),
            target_resolution=self.target_resolution,
            logger=self.logger,
            has_mask=self.has_mask,
            load_audio_in_prepare=self.load_audio_in_prepare,
            cache=self.cache
        )

        video._Video__cache_frames = self.__cache_frames.copy()
        video._Video__cache_full = self.__cache_full

        video.set_size(self.__size)
        video.set_alpha(self.__alpha)

        return video

    def get_original_clip(self) -> _utils.SupportsClip:
        return self.__original_clip

    def get_clip(self) -> _utils.SupportsClip:
        return self.__clip

    def get_filename(self) -> _utils.Path | None:
        if isinstance(self.__clip, CompositeVideoClip | ImageSequenceClip):
            return
        return self.__clip.filename

    def get_temp_audio(self) -> Path:
        return self.__audio_file

    def get_total_cache_frame(self) -> int:
        self.__check_video_initialized()
        return len(self.__cache_frames)

    def get_original_size(self) -> tuple[int, int]:
        self.__check_video_initialized()
        return (self.__original_clip.w, self.__original_clip.h)

    def get_clip_size(self) -> tuple[int, int]:
        self.__check_video_initialized()
        return (self.__clip.w, self.__clip.h)

    def get_size(self) -> tuple[int, int] | None:
        self.__check_video_initialized()
        return self.__size

    def get_file_size(self, unit: typing.Literal['b', 'kb', 'mb', 'gb']) -> _utils.Number | None:
        unit = unit.lower().strip()
        if isinstance(self.__clip, CompositeVideoClip | ImageSequenceClip):
            return None
        try:
            # get file size in bytes
            file_size = os.path.getsize(self.__clip.filename)
        except:
            return None

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
                raise ValueError(f'unknown unit named {repr(unit)}')

    def get_original_width(self) -> int:
        self.__check_video_initialized()
        return self.__original_clip.w

    def get_clip_width(self) -> int:
        self.__check_video_initialized()
        return self.__clip.w

    def get_width(self) -> int:
        self.__check_video_initialized()
        return self.__size[0]

    def get_original_height(self) -> int:
        self.__check_video_initialized()
        return self.__original_clip.h

    def get_clip_height(self) -> int:
        self.__check_video_initialized()
        return self.__clip.h

    def get_height(self) -> int:
        self.__check_video_initialized()
        return self.__size[1]

    def get_loops(self) -> int:
        self.__check_video_initialized()
        return self.__video_loops

    def get_pos(self) -> _utils.MilisecondsValue | typing.Literal[-1, -2]:
        self.__check_video_initialized()

        if not self.__ready:
            return -2
        elif not self.__play:
            return -1
        elif self.is_play:
            return self.__audio_offset + pygame.mixer.music.get_pos()

        return self.get_duration()

    def get_alpha(self) -> int:
        self.__check_video_initialized()
        return self.__alpha

    def get_duration(self) -> _utils.MilisecondsValue:
        self.__check_video_initialized()
        return self.__clip.duration * 1000

    def get_start(self) -> _utils.MilisecondsValue:
        self.__check_video_initialized()
        return self.__clip.start * 1000

    def get_end(self) -> _utils.MilisecondsValue:
        self.__check_video_initialized()
        return self.__clip.end * 1000

    def get_total_frame(self) -> int:
        self.__check_video_initialized()
        return int(self.__clip.duration * self.__clip.fps)

    def get_fps(self) -> _utils.Number:
        self.__check_video_initialized()
        return self.__clip.fps

    def get_volume(self) -> float:
        self.__check_video_initialized()
        self.__check_audio_loaded()
        if self.__mute:
            return self.__volume
        else:
            return pygame.mixer.music.get_volume()

    def get_frame_index(self) -> int:
        self.__check_video_initialized()
        return self.__frame_index

    def get_frame(self, index_time: _utils.Number, get_original: bool = False) -> pygame.Surface:
        self.__check_video_initialized()

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
        self.__check_video_initialized()
        asserter(
            self.cache,
            pygame.error("cache doesn't apply to this video")
        )

        range_iterable = range(self.get_total_frame())
        range_ = range_iterable
        is_bar = self.logger == 'bar'
        logger = proglog.default_bar_logger(self.logger if is_bar else None)
        blank_surface = pygame.Surface((self.__clip.w, self.__clip.h), pygame.SRCALPHA)
        if is_bar:
            range_iterable = tqdm.tqdm(range_iterable, desc='create cache frame', unit='frame', leave=False)

        blank_surface.fill('black')

        logger(message='Video - Create cache frame')

        for frame_index in range_iterable:
            try:
                frame = self.get_frame(frame_index * (1 / self.__clip.fps), get_original=True)
                self.__add_cache(frame_index, frame)
                # if the cache can no longer be saved, the generator exits
                if self.__cache_full:
                    break
                send_value = yield (frame, frame_index, range_)
            except:
                send_value = yield (blank_surface, frame_index, range_)

            if send_value:
                break

        if is_bar:
            range_iterable.close()

        if self.__cache_full:
            logger(message='Video - Done with full memory.')
        elif send_value:
            logger(message=f'Video - Done with the generator stopped. Reason: {send_value}')
        else:
            logger(message='Video - Done.')

        yield (blank_surface, -1, range_)

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
        if self.__pause:
            return self.__play
        elif not self.__ready:
            return False
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
    def clip(self, clip: _utils.SupportsClip) -> None:
        asserter(
            isinstance(clip, _utils.SupportsClip),
            TypeError(f'clip must be VideoFileClip, CompositeVideoClip or ImageSequenceClip, not {name(clip)}')
        )
        self.__clip = clip

    @size.setter
    def size(self, size: tuple[_utils.Number, _utils.Number] | list[_utils.Number] | None) -> None:
        self.set_size(size)

    @width.setter
    def width(self, width: _utils.Number) -> None:
        self.set_size((width, self.height))

    @height.setter
    def height(self, height: _utils.Number) -> None:
        self.set_size((self.width, height))

    @is_ready.setter
    def is_ready(self, value: bool) -> None:
        if value:
            self.prepare()
        else:
            self.release()

    @is_pause.setter
    def is_pause(self, value: bool) -> None:
        if value:
            self.pause()
        else:
            self.unpause()

    @is_play.setter
    def is_play(self, value: bool) -> None:
        if value:
            self.play()
        else:
            self.stop()

    @is_mute.setter
    def is_mute(self, value: bool) -> None:
        if value:
            self.mute()
        else:
            self.unmute()

    def draw_and_update(self, screen_surface: typing.Optional[pygame.Surface] = None, pos: typing.Any | pygame.Rect = (0, 0)) -> pygame.Surface:
        self.__check_video_initialized()
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

    def preview(self, *args, _type_: typing.Literal['clip', 'display-in-notebook', 'video-preview'] = 'video-preview', **kwargs) -> None:
        match _type_:

            case 'clip':
                self.__clip.preview(*args, **kwargs)

            case 'display-in-notebook':
                self.__clip.display_in_notebook(*args, **kwargs)

            case 'video-preview':
                video_preview(self, *args, **kwargs)

            case _:
                raise ValueError(f'unknown _type_ named {repr(_type_)}')

    def prepare(self) -> None:
        self.__check_video_initialized()

        if self.__ready:
            return

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

    def release(self) -> None:
        if not self.__ready:
            return

        self.__stop()

        self.__ready = False

        # unload audio
        pygame.mixer.music.unload()

        os.environ['PYGAME_VIDEO_USED'] = '0'

    def play(self, loops: int = 0, start: _utils.SecondsValue = 0) -> None:
        self.__check_video_initialized()
        self.__check_audio_loaded()
        asserter(
            isinstance(loops, int),
            TypeError(f'loops must be integers type, not {name(loops)}')
        )
        asserter(
            isinstance(start, _utils.SecondsValue),
            TypeError(f'start must be integers or floats type, not {name(start)}')
        )

        if self.is_play:
            return

        self.__play = True
        self.__loops = loops
        self.__frame_index = 0
        self.__audio_offset = start * 1000

        pygame.mixer.music.play(start=start)

    def preplay(self, *args, **kwargs) -> None:
        self.prepare()
        self.play(*args, **kwargs)

    def stop(self) -> None:
        self.__check_video_initialized()
        self.__check_audio_loaded()

        self.__stop()

    def restop(self) -> None:
        self.release()

    def pause(self) -> None:
        self.__check_video_initialized()
        self.__check_audio_loaded()

        if not self.__play or self.__pause:
            return

        self.__pause = True

        pygame.mixer.music.pause()

    def unpause(self) -> None:
        self.__check_video_initialized()
        self.__check_audio_loaded()

        if not self.__pause:
            return

        self.__pause = False

        pygame.mixer.music.unpause()

    def toggle_pause(self) -> None:
        if self.__pause:
            self.unpause()
        else:
            self.pause()

    def mute(self) -> None:
        if self.__mute:
            return

        self.__volume = self.get_volume()
        self.set_volume(0, set=True)
        self.__mute = True

    def unmute(self) -> None:
        if not self.__mute:
            return

        self.__mute = False
        self.set_volume(self.__volume, set=True)
        self.__volume = 0

    def toggle_mute(self) -> None:
        if self.__mute:
            self.unmute()
        else:
            self.mute()

    def jump(self, ratio: _utils.Number) -> None:
        asserter(
            isinstance(ratio, _utils.Number),
            TypeError(f'ratio must be integers or floats, not {name(ratio)}')
        )
        asserter(
            0 <= ratio <= 1,
            ValueError(f'ratio must be in the range of 0 to 1, not {ratio}')
        )

        self.set_pos(self.__clip.duration * ratio)

    def next(self, distance: _utils.SecondsValue) -> None:
        asserter(
            isinstance(distance, _utils.Number),
            TypeError(f'distance must be integers or floats, not {name(distance)}')
        )
        asserter(
            distance >= 0,
            ValueError('distance cannot be negative values')
        )

        if (move := self.get_pos() + distance * 1000) <= self.get_duration():
            self.set_pos(move / 1000)
        else:
            self.set_pos(self.__clip.duration)

    def previous(self, distance: _utils.SecondsValue) -> None:
        asserter(
            isinstance(distance, _utils.Number),
            TypeError(f'distance must be integers or floats, not {name(distance)}')
        )
        asserter(
            distance >= 0,
            ValueError('distance cannot be negative values')
        )

        if (move := self.get_pos() - distance * 1000) >= 0:
            self.set_pos(move / 1000)
        else:
            self.set_pos(0)

    def seek(self, distance: _utils.Number) -> None:
        asserter(
            isinstance(distance, _utils.Number),
            TypeError(f'distance must be integers or floats, not {name(distance)}')
        )

        if distance <= 0:
            self.previous(abs(distance))
        else:
            self.next(distance)

    def create_cache_frame(self, max_frame: typing.Optional[int] = None) -> None:
        asserter(
            isinstance(max_frame, int | None),
            TypeError(f'max_frame must be integers or None, not {name(max_frame)}')
        )

        if max_frame is None:
            max_frame = float('inf')
        else:
            if max_frame <= 0:
                return

            # subtract 2 because the index value is offset by 2 indices
            max_frame -= 2

        func = self.iter_chunk_cache_frame()

        for _, index, _ in func:
            if index > max_frame:
                func.send('Maximum frame reached.')
                func.close()
                return

    def clear_cache_frame(self) -> None:
        self.__cache_frames.clear()
        self.__cache_full = False

    def reset(self) -> None:
        self.__set_effect()

        self.__clip = self.__original_clip.copy()
        self.__size = None
        self.__alpha = 255

        self.__unload_audio()
        self.__load_audio()

    def custom_effect(self, _effect_s_or_method_: _utils.MoviePyFx | tuple[_utils.MoviePyFx] | list[_utils.MoviePyFx] | _utils.NameMethod, *args, **kwargs) -> None:
        self.__set_effect()

        if not isinstance(_effect_s_or_method_, _utils.NameMethod):
            if isinstance(_effect_s_or_method_, tuple | list):
                self.clip = self.__clip.with_effects(_effect_s_or_method_)
            else:
                self.clip = self.__clip.with_effects((_effect_s_or_method_(*args, **kwargs)))
        else:
            method = getattr(self.__clip, _effect_s_or_method_)
            self.clip = method(*args, **kwargs)

        self.__unload_audio()
        self.__load_audio()

    def invert_colors(self) -> None:
        self.custom_effect(fx.InvertColors)

    def grayscale(self) -> None:
        self.custom_effect(fx.BlackAndWhite)

    def split(self, *args, **kwargs) -> tuple['Video', 'Video', 'Video']:
        self.__check_video_initialized()

        self.__stop()

        is_bar = self.logger == 'bar'
        logger = proglog.default_bar_logger(self.logger if is_bar else None)
        color_channel = {0: 'RED',
                         1: 'GREEN',
                         2: 'BLUE'}

        def extract_channel(channel: typing.Literal[0, 1, 2]) -> ImageSequenceClip:
            frames = []
            arange = np.arange(0, self.__clip.duration, 1 / self.__clip.fps)

            color = color_channel[channel]

            if is_bar:
                range_iterable = tqdm.tqdm(arange, desc=f'create video color {color}', unit='frame', leave=False)
            else:
                range_iterable = arange

            logger(message=f'Video - Create color {color}, channel {channel}/2')

            for t in range_iterable:
                try:
                    frame = self.get_frame_array(t, get_original=True)
                    channel_frame = np.zeros_like(frame)
                    channel_frame[:, :, channel] = frame[:, :, channel]
                    frames.append(channel_frame)
                except:
                    pass

            if is_bar:
                range_iterable.close()

            logger(message=f'Video - Color {color} done.')

            return ImageSequenceClip(frames, fps=self.__clip.fps).with_audio(self.__clip.audio)

        return (Video(extract_channel(0), *args, **kwargs),
                Video(extract_channel(1), *args, **kwargs),
                Video(extract_channel(2), *args, **kwargs))

    def crop(self, rect: pygame.Rect | tuple | list) -> None:
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

        self.custom_effect('cropped', x1=rect.left,
                                      y1=rect.top,
                                      width=rect.width,
                                      height=rect.height)
        self.resize(rect.size)

    def rotate(self, rotate: _utils.Number) -> None:
        asserter(
            isinstance(rotate, _utils.Number),
            TypeError(f'rotate must be a integers or floats, not {name(rotate)}')
        )

        self.custom_effect('rotated', rotate % 360)

    def loop(self, loops: int) -> None:
        asserter(
            isinstance(loops, int),
            TypeError(f'loops must be integers, not {name(loops)}')
        )
        asserter(
            loops > 0,
            ValueError(f'loops must be greater than 0, not {loops}')
        )

        self.custom_effect(fx.Loop, loops)

    def resize(self, scale_or_size: _utils.Number | tuple[_utils.Number, _utils.Number] | list[_utils.Number]) -> None:
        if isinstance(scale_or_size, _utils.Number):
            self.custom_effect('resized', scale_or_size)
        else:
            self.custom_effect('resized', newsize=tuple(map(int, scale_or_size)))

    def mirror(self, axis: typing.Literal['x', 'y']) -> None:
        match axis:
            case 'x':
                self.custom_effect(fx.MirrorX)
            case 'y':
                self.custom_effect(fx.MirrorY)
            case _:
                raise ValueError(f'unknown axis named {repr(axis)}')

    def fade(self, type: typing.Literal['in', 'out'], duration: _utils.SecondsValue) -> None:
        match type:
            case 'in':
                self.custom_effect(fx.FadeIn, duration=duration)
            case 'out':
                self.custom_effect(fx.FadeOut, duration=duration)
            case _:
                raise ValueError(f'unknown type named {repr(type)}')

    def cut(self, start: _utils.SecondsValue, end: _utils.SecondsValue) -> None:
        asserter(
            isinstance(start, _utils.SecondsValue),
            TypeError(f'start must be integers or floats, not {name(start)}')
        )
        asserter(
            isinstance(end, _utils.SecondsValue),
            TypeError(f'end must be integers or floats, not {name(end)}')
        )
        self.custom_effect('subclipped', start, end)

    def reverse(self, step_sub: _utils.Number = 0.01, max_retries: int = 12) -> typing.Literal[-1, -2] | None:
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
            'Reverse will cut the duration of the main clip. '
            'Use the most minimal max_retries and sub steps possible.',
            category=UserWarning
        )

        current_time = self.__clip.duration
        time_func = lambda t : self.__clip.duration - t # in moviepy 2.1.1: self.__clip.duration - t - 1
        apply_to = ('mask', 'audio')

        while max_retries > 0:
            try:
                self.cut(0, current_time)
                # useless (moviepy ~2.1.1). It causes OSError exception
                # self.custom_effect(fx.TimeMirror)

                # using source code from time_mirror version moviepy 1.0.3
                self.clip = self.__clip.time_transform(time_func=time_func,
                                                       apply_to=apply_to,
                                                       keep_duration=True)
                break
            except:
                current_time -= step_sub
                max_retries -= 1
                if current_time <= 0:
                    return -2

        else:
            return -1

    def concatenate_clip(self, clip_or_clips: typing.Union[_utils.SupportsClip, 'Video', tuple, list], *args, **kwargs) -> None:
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

    def add_volume(self, add: _utils.Number, max_volume: _utils.Number = 1, set: bool = False) -> None:
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

        self.set_volume(min(self.get_volume() + add, max_volume), set=set)

    def sub_volume(self, sub: _utils.Number, min_volume: _utils.Number = 0, set: bool = False) -> None:
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

        self.set_volume(max(self.get_volume() - sub, min_volume), set=set)

    def set_alpha(self, value: int) -> None:
        self.__check_video_initialized()
        asserter(
            isinstance(value, int),
            TypeError(f'value must be integers, not {name(value)}')
        )
        asserter(
            0 <= value <= 255,
            ValueError(f'value must be in the range of 0 to 255, not {value}')
        )

        self.__alpha = value

    def set_size(self, size: tuple[_utils.Number, _utils.Number] | list[_utils.Number] | None) -> None:
        self.__check_video_initialized()

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

    def set_audio(self, audio: _utils.SupportsAudioClip) -> None:
        self.__check_video_initialized()
        asserter(
            isinstance(audio, _utils.SupportsAudioClip),
            TypeError(f'audio must be AudioFileClip or CompositeAudioClip, not {name(audio)}')
        )

        self.__stop()

        if (duration_diff := (self.__clip.duration - audio.duration)) > 0:
            fps = 44100
            silent_audio_array = np.zeros((int(duration_diff * fps), 2))
            silent_audio = AudioArrayClip(silent_audio_array, fps=fps)
            audio = concatenate_audioclips((audio, silent_audio))

        self.clip = self.__clip.with_audio(audio)

        self.__unload_audio()
        self.__load_audio()

    def set_speed(self, speed: _utils.Number) -> None:
        asserter(
            isinstance(speed, _utils.Number),
            TypeError(f'speed must be a integers or floats, not {name(speed)}')
        )
        asserter(
            speed > 0,
            ValueError(f'speed must be greater than 0, not {speed}')
        )
        self.custom_effect('with_speed_scaled', speed)

    def set_fps(self, fps: _utils.Number) -> None:
        asserter(
            isinstance(fps, _utils.Number),
            TypeError(f'fps must be a integers or floats, not {name(fps)}')
        )
        asserter(
            fps > 0,
            ValueError(f'fps must be greater than 0, not {fps}')
        )
        self.custom_effect('with_fps', fps)

    def set_volume(self, volume: _utils.Number, set: bool = False) -> None:
        self.__check_video_initialized()
        self.__check_audio_loaded()
        asserter(
            isinstance(volume, _utils.Number),
            TypeError(f'volume must be a integers or floats, not {name(volume)}')
        )

        # if the audio is currently muted with .mute(), then it will
        # not be able to be changed unless the `set` parameter is True
        if not self.__mute or set:
            pygame.mixer.music.set_volume(min(1, max(0, volume)))

    def set_pos(self, pos: _utils.SecondsValue) -> None:
        self.__check_video_initialized()
        self.__check_audio_loaded()
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

    def handle_event(self, event: pygame.event.Event, volume_adjustment: _utils.Number = 0.05, seek_adjustment: _utils.SecondsValue = 5) -> int | None:
        self.__check_video_initialized()
        self.__check_audio_loaded()
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

    def quit(self) -> None:
        if self.__quit:
            return

        # close up all assets
        self.clear_cache_frame()
        self.__clip.close()
        self.__original_clip.close()
        self.__unload_audio()

        self.__quit = True
        self.__play = False
        self.__ready = False
        self.__pause = False

    # same as .quit()
    close = quit

_GLOBAL_VIDEO: global_video[Video] = global_video()

def ignore_warn(category: Warning = UserWarning) -> None:
    warnings.filterwarnings('ignore', category=category)

def enable_warn() -> None:
    warnings.resetwarnings()

def quit(show_log: bool = True) -> None:
    # stop the audio
    if pygame.get_init():
        pygame.mixer.music.stop()
    # loop all existing videos
    global _GLOBAL_VIDEO
    for video in _GLOBAL_VIDEO:
        try:
            video.quit()
        except Exception as e:
            if show_log:
                print(f'Error durring quit / close Video > {video} => {name(e)}: {e}')

    _GLOBAL_VIDEO.clear()

close = quit