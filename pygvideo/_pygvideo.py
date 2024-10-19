import pygame as _pygame
import proglog as _proglog
import tqdm as _tqdm
import numpy as _np

import moviepy.video.fx.all as _vfx
from ._utils import VideoFileClip as _VideoFileClip

from ._utils import global_video as _global_video
from ._utils import typing as _typing
from ._utils import PathL as _Path
from ._utils import os as _os
from ._utils import asserter as _assert
from ._utils import name as _name

from . import _utils

_os.environ["PYGAME_VIDEO_USED"] = "0"

class Video:

    def __init__(

            self,
            filename_or_clip: _utils.Path | _VideoFileClip,
            target_resolution: _typing.Optional[_typing.Any] = None,
            logger: _typing.Literal['bar', 'verbose', None] = 'bar',
            has_mask: bool = False,
            load_audio_in_prepare: bool = True,
            cache: bool = True

        ) -> None:

        """

        A video that can be played to the `pygame` screen. For example:

        ```
        ... video_player = Video("intro.mp4") # load the video
        ... video_player.set_fps(30)          # set the fps
        ... video_player.prepare()            # load the audio
        ... video_player.play()               # play the video and audio
        ... while ...:
        ...    for event in pygame.event.get():
        ...        ...
        ...    frame = video_player.draw_and_update() # updated, will be returns a frame
        ...    ...
        ... video_player.quit() # clean up resources
        ... ...
        ```

        Parameters
        ----------
        filename_or_clip:
            Name the video file or clip directly. If you use the filename make sure the file extension is
            supported by ffmpeg.
        target_resolution:
            Target resolution. Almost the same as resize.
        looger:
            Showing logger.
        has_mask:
            Supports transparency/alpha. Depends on video format type.
        load_audio_in_prepare:
            load or precisely write the temp audio when prepare is called.
        cache:
            save frame to cache.

        Documentation
        -------------
        Full documentation is on github https://github.com/azzammuhyala/pygvideo.git or on pypi
        https://pypi.org/project/pygvideo.

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
        video = pygvideo.Video('intro.mp4')
        screen = pygame.display.set_mode((900, 900))
        clock = pygame.time.Clock()

        video_fps = video.get_fps()

        video.set_size(screen.get_size())
        # store temporary cache, to minimize lag but has storage size limitations [OPTIONAL]
        video.create_cache_frame()

        video.prepare()
        video.play(-1)

        while running:

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

            video.draw_and_update(screen, (0, 0))

            pygame.display.flip()

            clock.tick(video_fps)

        pygvideo.quit()
        pygame.quit()
        ```

        """

        self.filename_or_clip = filename_or_clip
        self.target_resolution = target_resolution
        self.logger = logger
        self.has_mask = has_mask
        self.load_audio_in_prepare = load_audio_in_prepare
        self.cache = cache

        if isinstance(logger, str):
            self.logger = logger.lower().strip()

        # load properties
        self.__cache_frames = dict()
        self.__size = None
        self.__cache_full = False
        self.__quit = False
        self.__ready = False
        self.__play = False
        self.__pause = False
        self.__index = 0
        self.__loops = 0
        self.__video_loops = 0
        self.__frame_index = 0
        self.__audio_offset = 0
        self.__volume = 0
        self.__alpha = 255

        # initialize moviepy video clip
        if isinstance(filename_or_clip, _VideoFileClip):
            self.clip = filename_or_clip
        else:
            self.clip = _VideoFileClip(
                filename=filename_or_clip,
                has_mask=has_mask,
                target_resolution=target_resolution,
                verbose=bool(self.logger == 'verbose')
            )

        # save an original clip
        self.__original_clip = self.clip.copy()

        # load the temporary audio
        self.__load_audio(load_file=True)

        # add Video to global
        global _GLOBAL_VIDEO
        _GLOBAL_VIDEO.append(self)

    def __getitem__(self, index: _typing.SupportsIndex | slice):
        # get the maximum total frames
        # this is not 100% accurate total of all the frames in the Video
        total_frame = self.get_total_frame()

        # for slice case
        if isinstance(index, slice):
            result: list[_pygame.Surface] = []
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
            index = index if index >= 0 else total_frame + index

            if 0 <= index < total_frame:
                return self.get_frame(index * (1 / self.clip.fps))
            else:
                # indeks di luar area frame
                raise IndexError('Frame index out of range')

        # other will be raises a TypeError
        raise TypeError(f'Frame index indices must be integers or slices, not {_name(index)}')

    def __iter__(self) -> _typing.Self:
        # reset index every time a new iteration starts
        self.__index = 0
        # returns the object itself as an iterator
        return self

    def __enter__(self) -> _typing.Self:
        # returns an instance of the class itself
        return self

    def __next__(self) -> _pygame.Surface:
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
        if hasattr(self, 'clip'):
            if isinstance(self.clip, _VideoFileClip):
                self.quit()

    def __mul__(self, value: _utils.RealNumber | tuple | list) -> _typing.Self:
        return self.__operator(self.resize, value)

    def __truediv__(self, value: _utils.RealNumber | tuple | list) -> _typing.Self:
        if isinstance(value, _utils.RealNumber):
            return self.__operator(self.resize, 1 / value)
        return self.__operator(self.resize, value)

    def __pow__(self, value: _utils.RealNumber) -> _typing.Self:
        return self.__operator(self.set_speed, value)

    def __floordiv__(self, value: _utils.RealNumber) -> _typing.Self:
        return self.__operator(self.set_speed, 1 / value)

    def __add__(self, value: _utils.RealNumber) -> _typing.Self:
        return self.__operator(self.add_volume, value)

    def __sub__(self, value: _utils.RealNumber) -> _typing.Self:
        return self.__operator(self.sub_volume, value)

    def __rshift__(self, value: _utils.RealNumber) -> _typing.Self:
        return self.__operator(self.next, value)

    def __lshift__(self, value: _utils.RealNumber) -> _typing.Self:
        return self.__operator(self.previous, value)

    def __xor__(self, value: _utils.RealNumber) -> _typing.Self:
        return self.__operator(self.jump, value)

    def __matmul__(self, value: _utils.RealNumber) -> _typing.Self:
        return self.__operator(self.rotate, value)

    def __mod__(self, value: _pygame.Rect) -> _typing.Self:
        return self.__operator(self.crop, value)

    def __or__(self, value: _typing.Literal['x', 'y']) -> _typing.Self:
        return self.__operator(self.mirror, value)

    def __invert__(self) -> _typing.Self:
        return self.__operator(self.reset)

    def __eq__(self, value: _typing.Union[_utils.MilisecondsValue, _VideoFileClip, 'Video']) -> bool:
        return self.__comparison('==', value)

    def __ne__(self, value: _typing.Union[_utils.MilisecondsValue, _VideoFileClip, 'Video']) -> bool:
        return self.__comparison('!=', value)

    def __lt__(self, value: _typing.Union[_utils.MilisecondsValue, _VideoFileClip, 'Video']) -> bool:
        return self.__comparison('<', value)

    def __gt__(self, value: _typing.Union[_utils.MilisecondsValue, _VideoFileClip, 'Video']) -> bool:
        return self.__comparison('>', value)

    def __le__(self, value: _typing.Union[_utils.MilisecondsValue, _VideoFileClip, 'Video']) -> bool:
        return self.__comparison('<=', value)

    def __ge__(self, value: _typing.Union[_utils.MilisecondsValue, _VideoFileClip, 'Video']) -> bool:
        return self.__comparison('>=', value)

    def __bool__(self) -> bool:
        return not self.__quit

    def __list__(self) -> list[_pygame.Surface]:
        return self[::]

    def __tuple__(self) -> tuple[_pygame.Surface]:
        return tuple(self[::])

    def __len__(self) -> int:
        return self.get_total_frame()

    def __repr__(self) -> str:
        return (
            f'{".".join(self.__get_mod())}('
            f'filename_or_clip={repr(self.clip.filename)},'
            f' target_resolution={repr(self.target_resolution)},'
            f' logger={repr(self.logger)},'
            f' has_mask={repr(self.has_mask)},'
            f' load_audio_in_prepare={repr(self.load_audio_in_prepare)},'
            f' cache={repr(self.cache)})'
        )

    def __str__(self) -> str:
        return f'<{".".join(self.__get_mod())} filename={repr(self.clip.filename)}>'

    def __copy__(self) -> 'Video':
        return self.copy()

    def __load_audio(self, load: bool | None = None, load_file: bool = False) -> None:

        def write_audio():
            # trim audio to avoid excess audio duration
            audio = self.clip.audio#.subclip(0, self.clip.duration - 0.15)
            # check if the video has audio, otherwise it will raise an error
            _assert(
                audio is not None,
                _pygame.error('video format has no audio. Video only supports video formats with audio')
            )
            logger = 'bar' if self.logger == 'bar' else None
            audio.write_audiofile(self.__audio_file, logger=logger)

        if load_file:
            # create temporary audio file
            path = _Path(_os.environ.get('PYGAME_VIDEO_TEMP', ''))
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
        self.release()

        # delete audio temporary file if the file are still there
        if self.__audio_file.exists():
            try:
                _os.remove(self.__audio_file)
            except PermissionError:
                # access denied, if audio is in use
                pass

    def __check_video_initialized(self) -> None:
        _assert(
            not self.__quit,
            _pygame.error('Video not initialized')
        )

    def __check_audio_loaded(self) -> None:
        _assert(
            self.__ready,
            _pygame.error('Video not ready yet')
        )

    def __stop(self) -> None:
        if not self.__play:
            return

        self.__play = False
        self.__pause = False
        self.__frame_index = 0
        self.__audio_offset = 0

        _pygame.mixer.music.stop()

    def __set_effect(self) -> None:
        self.__check_video_initialized()

        # stop video to stop the video
        self.__stop()

        # clear existing frame cache
        self.clear_cache_frame()

    def __operator(self, method: _typing.Callable, *args, **kwargs) -> _typing.Self:
        method(*args, **kwargs)
        return self

    def __comparison(self, operator: _typing.Literal['==', '!=', '<', '>', '<=', '>='], value: _typing.Union[_utils.MilisecondsValue, _VideoFileClip, 'Video']) -> bool:
        clip_duration = self.get_duration()

        method = {
            '==': clip_duration.__eq__,
            '!=': clip_duration.__ne__,
            '<': clip_duration.__lt__,
            '>': clip_duration.__gt__,
            '<=': clip_duration.__le__,
            '>=': clip_duration.__ge__
        }

        if isinstance(value, _utils.RealNumber):
            return method[operator](value)
        elif isinstance(value, _VideoFileClip):
            return method[operator](value.duration * 1000)
        elif isinstance(value, Video):
            return method[operator](value.get_duration())

        raise TypeError(f"{repr(operator)} not supported between instances of '{'.'.join(self.__get_mod())}' and '{_name(value)}'")

    def __add_cache(self, frame_index: _utils.RealNumber, frame: _pygame.Surface) -> None:
        if not self.__cache_full and self.cache:
            try:
                self.__cache_frames[frame_index] = frame
            except MemoryError:
                self.__cache_full = True

    def __get_mod(self) -> tuple[str, str]:
        cls = self.__class__
        return (cls.__module__, cls.__qualname__)

    def reinit(self) -> None:
        if not self.__quit:
            return

        # quit or close then re-init
        self.quit()
        self.__init__(
            filename_or_clip=self.filename_or_clip,
            target_resolution=self.target_resolution,
            logger=self.logger,
            has_mask=self.has_mask,
            load_audio_in_prepare=self.load_audio_in_prepare,
            cache=self.cache
        )

    def copy(self) -> 'Video':
        return Video(
            filename_or_clip=self.clip.copy(),
            target_resolution=self.target_resolution,
            logger=self.logger,
            has_mask=self.has_mask,
            load_audio_in_prepare=self.load_audio_in_prepare,
            cache=self.cache
        )

    def get_original_clip(self) -> _VideoFileClip:
        return self.__original_clip

    def get_clip(self) -> _VideoFileClip:
        return self.clip

    def get_filename(self) -> _utils.Path:
        return self.clip.filename

    def get_temp_audio(self) -> _Path:
        return self.__audio_file

    def get_total_cache_frame(self) -> int:
        self.__check_video_initialized()
        return len(self.__cache_frames)

    def get_original_size(self) -> tuple[int, int]:
        self.__check_video_initialized()
        return (self.__original_clip.w, self.__original_clip.h)

    def get_clip_size(self) -> tuple[int, int]:
        self.__check_video_initialized()
        return (self.clip.w, self.clip.h)

    def get_size(self) -> tuple[int, int]:
        self.__check_video_initialized()
        return self.__size

    def get_file_size(self, unit: _typing.Literal['b', 'kb', 'mb', 'gb']) -> None | _utils.RealNumber:
        unit = unit.lower().strip()
        try:
            # get file size in bytes
            file_size = _os.path.getsize(self.clip.filename)
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
                _pygame.error(f'unknown unit named {repr(unit)}')

    def get_original_width(self) -> int:
        self.__check_video_initialized()
        return self.__original_clip.w

    def get_clip_width(self) -> int:
        self.__check_video_initialized()
        return self.clip.w

    def get_width(self) -> int:
        self.__check_video_initialized()
        return self.__size[0]

    def get_original_height(self) -> int:
        self.__check_video_initialized()
        return self.__original_clip.h

    def get_clip_height(self) -> int:
        self.__check_video_initialized()
        return self.clip.h

    def get_height(self) -> int:
        self.__check_video_initialized()
        return self.__size[1]

    def get_loops(self) -> int:
        self.__check_video_initialized()
        return self.__video_loops

    def get_pos(self) -> _utils.FloatMilisecondsValue | _typing.Literal[-1, -2]:
        self.__check_video_initialized()

        if not self.__ready:
            return -1
        elif not self.__play:
            return -2
        elif self.is_play():
            return float(self.__audio_offset + _pygame.mixer.music.get_pos())

        return self.get_duration()

    def get_alpha(self) -> int:
        self.__check_video_initialized()
        return self.__alpha

    def get_duration(self) -> _utils.FloatMilisecondsValue:
        self.__check_video_initialized()
        return float(self.clip.duration * 1000)

    def get_start(self) -> _utils.FloatMilisecondsValue:
        self.__check_video_initialized()
        return float(self.clip.start * 1000)

    def get_end(self) -> _utils.FloatMilisecondsValue:
        self.__check_video_initialized()
        return float(self.clip.end * 1000)

    def get_total_frame(self) -> int:
        self.__check_video_initialized()
        return int(self.clip.duration * self.clip.fps)

    def get_fps(self) -> float:
        self.__check_video_initialized()
        return self.clip.fps

    def get_volume(self) -> float:
        self.__check_video_initialized()
        self.__check_audio_loaded()
        return _pygame.mixer.music.get_volume()

    def get_frame_index(self) -> int:
        self.__check_video_initialized()
        return self.__frame_index

    def get_frame(self, index_time: _utils.RealNumber, get_original: bool = False) -> _pygame.Surface:
        self.__check_video_initialized()

        frame = self.clip.get_frame(index_time)
        frame_surface = _pygame.surfarray.make_surface(frame.swapaxes(0, 1))

        if not get_original:
            if self.__size:
                frame_surface = _pygame.transform.scale(frame_surface, self.__size)
            frame_surface.set_alpha(self.__alpha)

        return frame_surface

    def get_frame_array(self, index_time: _utils.RealNumber, get_original: bool = False):
        frame = self.get_frame(index_time, get_original)
        array = _pygame.surfarray.pixels3d(frame)

        return _np.transpose(array, (1, 0, 2))

    def iter_chunk_cache_frame(self) -> _typing.Generator[tuple[_pygame.Surface, int | _typing.Literal[-1], range], None, None]:
        self.__check_video_initialized()
        _assert(
            self.cache,
            _pygame.error("cache doesn't apply")
        )

        range_iterable = range(self.get_total_frame())
        range_ = range_iterable
        is_bar = self.logger == 'bar'
        logger = _proglog.default_bar_logger(self.logger if is_bar else None)
        blank_surface = _pygame.Surface((self.clip.w, self.clip.h), _pygame.SRCALPHA)
        if is_bar:
            range_iterable = _tqdm.tqdm(range_iterable, desc='create cache frame', unit='frame', leave=False)

        blank_surface.fill('black')

        logger(message='Video - Create cache frame')

        for frame_index in range_iterable:
            try:
                frame = self.get_frame(frame_index * (1 / self.clip.fps), get_original=True)
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

    def is_cache_full(self) -> bool:
        return self.__cache_full

    def is_ready(self) -> bool:
        return self.__ready

    def is_pause(self) -> bool:
        return self.__pause

    def is_play(self) -> bool:
        if self.__pause:
            return self.__play
        elif not self.__ready:
            return False
        return self.__play and _pygame.mixer.music.get_busy()

    def is_mute(self) -> bool:
        # self.__volume if it is float type it means the audio is muted
        return isinstance(self.__volume, float)

    def is_quit(self) -> bool:
        return self.__quit

    def is_close(self) -> bool:
        return self.__quit

    def draw_and_update(self, screen_surface: _typing.Optional[_pygame.Surface] = None, pos: _typing.Any | _pygame.Rect = (0, 0)) -> _pygame.Surface:
        self.__check_video_initialized()
        _assert(
            self.__play,
            _pygame.error('the video is not playing yet. Use the .play() method before call this method')
        )

        music_pos = _pygame.mixer.music.get_pos()

        if music_pos != -1:
            self.__frame_index = int(((self.__audio_offset + music_pos) / 1000) * self.clip.fps)
        else:
            self.__frame_index = self.get_total_frame()

        # logic loops
        if not self.is_play() and self.__loops != 0:
            self.__audio_offset = 0
            self.__video_loops += 1
            self.stop()
            self.play(self.__loops - 1)

        try:
            # check if the frame index is already in cache_frames, if not it will be loaded and saved to cache_frames
            if self.__frame_index in self.__cache_frames:
                frame_surface = self.__cache_frames[self.__frame_index]
            else:
                frame_surface = self.get_frame(self.__frame_index * (1 / self.clip.fps), get_original=True)
                self.__add_cache(self.__frame_index, frame_surface)

            if self.__size:
                frame_surface = _pygame.transform.scale(frame_surface, self.__size)
        except:
            # if there is an error in the frame index, it will load an empty surface image
            size_surface = self.__size if self.__size else (self.clip.w, self.clip.h)
            frame_surface = _pygame.Surface(size_surface)
            frame_surface.fill('black')

        frame_surface.set_alpha(self.__alpha)

        if screen_surface:
            screen_surface.blit(frame_surface, pos)

        return frame_surface

    def preview(self, *args, **kwargs) -> None:
        # clip.preview() in moviepy uses pygame window. So this method
        # can be loaded to see the clip result without executing the main pygame program
        self.clip.preview(*args, **kwargs)

    def prepare(self) -> None:
        self.__check_video_initialized()
        # check if video class object is in use, if it is in use it will raise error message
        _assert(
            _os.environ["PYGAME_VIDEO_USED"] != "1",
            _pygame.error('cannot use 2 videos at the same time')
        )

        if self.__ready:
            return

        # if the audio temp is lost or deleted, it will automatically load the audio
        if not self.__audio_file.exists():
            self.__load_audio(load=True)

        # load audio ke mixer
        _pygame.mixer.music.load(self.__audio_file)

        self.__ready = True
        self.__video_loops = 0

        _os.environ["PYGAME_VIDEO_USED"] = "1"

    def release(self) -> None:
        if not self.__ready:
            return

        self.__stop()

        self.__ready = False

        # unload audio
        _pygame.mixer.music.unload()

        _os.environ["PYGAME_VIDEO_USED"] = "0"

    def play(self, loops: int = 0, start: _utils.SecondsValue = 0) -> None:
        self.__check_video_initialized()
        self.__check_audio_loaded()
        _assert(
            isinstance(loops, int),
            TypeError('loops must be integers type, not ' + _name(loops))
        )

        if self.is_play():
            return

        self.__play = True
        self.__loops = loops
        self.__frame_index = 0
        self.__audio_offset = start * 1000

        _pygame.mixer.music.play(start=start)

    def stop(self) -> None:
        self.__check_video_initialized()
        self.__check_audio_loaded()

        self.__stop()

    def pause(self) -> None:
        self.__check_video_initialized()
        self.__check_audio_loaded()

        if not self.__play or self.__pause:
            return

        self.__pause = True

        _pygame.mixer.music.pause()

    def unpause(self) -> None:
        self.__check_video_initialized()
        self.__check_audio_loaded()

        if not self.__pause:
            return

        self.__pause = False

        _pygame.mixer.music.unpause()

    def mute(self) -> None:
        if self.is_mute():
            return

        self.__volume = self.get_volume()
        self.set_volume(0, set=True)

    def unmute(self) -> None:
        if not self.is_mute():
            return

        self.set_volume(self.__volume, set=True)
        self.__volume = 0

    def jump(self, ratio: _utils.RealNumber) -> None:
        _assert(
            isinstance(ratio, _utils.RealNumber),
            TypeError('ratio must be integers or floats, not ' + _name(ratio))
        )
        _assert(
            0 <= ratio <= 1,
            ValueError(f'ratio must be in the range of 0 to 1, not {ratio}')
        )
        self.set_pos(self.clip.duration * ratio)

    def next(self, distance: _utils.SecondsValue) -> None:
        _assert(
            isinstance(distance, _utils.RealNumber),
            TypeError('distance must be integers or floats, not ' + _name(distance))
        )
        _assert(
            distance >= 0,
            ValueError('distance cannot be negative values')
        )
        if (move := self.get_pos() + distance * 1000) <= self.get_duration():
            self.set_pos(move / 1000)
        else:
            self.set_pos(self.clip.duration)

    def previous(self, distance: _utils.SecondsValue) -> None:
        _assert(
            isinstance(distance, _utils.RealNumber),
            TypeError('distance must be integers or floats, not ' + _name(distance))
        )
        _assert(
            distance >= 0,
            ValueError('distance cannot be negative values')
        )
        if (move := self.get_pos() - distance * 1000) >= 0:
            self.set_pos(move / 1000)
        else:
            self.set_pos(0)

    def create_cache_frame(self, max_frame: int | None = None) -> None:
        _assert(
            isinstance(max_frame, int | None),
            TypeError('max_frame must be integers or None, not ' + _name(max_frame))
        )

        if max_frame is None:
            max_frame = float('inf')
        else:
            if max_frame <= 0:
                return

            # subtract 2 because the index value is offset by 2 indices
            max_frame -= 2

        func = self.iter_chunk_cache_frame()

        try:
            for _, index, _ in func:
                if index > max_frame and index != -1:
                    func.send('Maximum frame reached.')
                    func.close()
                    return
        except:
            pass

    def clear_cache_frame(self) -> None:
        self.__cache_frames.clear()
        self.__cache_full = False

    def reset(self) -> None:
        self.__set_effect()

        self.clip = self.__original_clip.copy()
        self.__size = None
        self.__alpha = 255

        self.__unload_audio()
        self.__load_audio()

    def custom_effect(self, func: _utils.MoviePyFx | _utils.NameMethod, *args, **kwargs) -> None:
        self.__set_effect()

        if not isinstance(func, _utils.NameMethod):
            self.clip = func(self.clip, *args, **kwargs)
            _assert(
                isinstance(self.clip, _VideoFileClip),
                _pygame.error('function unexpectedly returns value other than VideoFileClip')
            )
        else:
            method = getattr(self.clip, func)
            self.clip = method(*args, **kwargs)

        self.__unload_audio()
        self.__load_audio()

    def invert_colors(self) -> None:
        self.custom_effect('invert_colors')

    def grayscale(self) -> None:
        self.custom_effect(_vfx.blackwhite)

    def crop(self, rect: _pygame.Rect) -> None:
        _assert(
            isinstance(rect, _pygame.Rect),
            TypeError('rect must be rects, not ' + _name(rect))
        )
        self.custom_effect('crop',
            x1 = rect.left,
            y1 = rect.top,
            width = rect.width,
            height = rect.height
        )
        self.resize(rect.size)

    def rotate(self, rotate: _utils.RealNumber) -> None:
        self.custom_effect('rotate', rotate)

    def resize(self, scale_or_size: _utils.RealNumber | tuple[_utils.RealNumber, _utils.RealNumber] | list[_utils.RealNumber, _utils.RealNumber]) -> None:
        if isinstance(scale_or_size, _utils.RealNumber):
            self.custom_effect('resize', scale_or_size)
        else:
            self.custom_effect('resize', newsize=scale_or_size)

    def mirror(self, axis: _typing.Literal['x', 'y']) -> None:
        if axis == 'x':
            self.custom_effect(_vfx.mirror_x)
        elif axis == 'y':
            self.custom_effect(_vfx.mirror_y)
        else:
            raise _pygame.error('unknown axis')

    def fade(self, type: _typing.Literal['in', 'out'], duration: _utils.SecondsValue) -> None:
        if type == 'in':
            self.custom_effect('fadein', duration=duration)
        elif type == 'out':
            self.custom_effect('fadeout', duration=duration)
        else:
            raise _pygame.error('unknown type')

    def cut(self, start: _utils.SecondsValue, end: _utils.SecondsValue) -> None:
        self.custom_effect('subclip', start, end)

    def add_volume(self, add: _utils.RealNumber, max_volume: _utils.RealNumber = 1, set: bool = False) -> None:
        _assert(
            isinstance(add, _utils.RealNumber),
            TypeError('add must be integers or floats, not ' + _name(add))
        )
        _assert(
            isinstance(max_volume, _utils.RealNumber),
            TypeError('max_volume must be integers or floats, not ' + _name(max_volume))
        )
        _assert(
            add >= 0,
            ValueError('add cannot be negative values')
        )

        self.set_volume(min(self.get_volume() + add, max_volume), set=set)

    def sub_volume(self, sub: _utils.RealNumber, min_volume: _utils.RealNumber = 0, set: bool = False) -> None:
        _assert(
            isinstance(sub, _utils.RealNumber),
            TypeError('sub must be integers or floats, not ' + _name(sub))
        )
        _assert(
            isinstance(min_volume, _utils.RealNumber),
            TypeError('min_volume must be integers or floats, not ' + _name(min_volume))
        )
        _assert(
            sub >= 0,
            ValueError('sub cannot be negative values')
        )

        self.set_volume(max(self.get_volume() - sub, min_volume), set=set)

    def set_alpha(self, value: int) -> None:
        self.__check_video_initialized()
        _assert(
            isinstance(value, int),
            TypeError('value must be integers, not ' + _name(value))
        )
        _assert(
            0 <= value <= 255,
            ValueError(f'value must be in the range of 0 to 255, not {value}')
        )

        self.__alpha = value

    def set_size(self, size: tuple[_utils.RealNumber, _utils.RealNumber] | list[_utils.RealNumber, _utils.RealNumber] | None) -> None:
        self.__check_video_initialized()

        if size is None:
            self.__size = None
            return

        size_len = len(size)

        _assert(
            isinstance(size, tuple | list),
            'must be tuples, lists or None, not ' + _name(size)
        )
        _assert(
            size_len == 2,
            f'size must contain 2 values, not {size_len}'
        )

        self.__size = tuple(map(int, size))

    def set_speed(self, speed: _utils.RealNumber) -> None:
        self.custom_effect('speedx', speed)

    def set_fps(self, fps: _utils.RealNumber) -> None:
        self.custom_effect('set_fps', fps)

    def set_volume(self, volume: _utils.RealNumber, set: bool = False) -> None:
        self.__check_video_initialized()
        self.__check_audio_loaded()

        # if the audio is currently muted with .mute(), then it will
        # not be able to be changed unless the `set` parameter is True
        if not self.is_mute() or set:
            _pygame.mixer.music.set_volume(volume)

    def set_pos(self, pos: _utils.SecondsValue) -> None:
        self.__check_video_initialized()
        self.__check_audio_loaded()

        self.__audio_offset = pos * 1000

        if 0 <= self.__audio_offset <= self.get_duration():
            _pygame.mixer.music.pause()
            _pygame.mixer.music.play(start=pos)
            if self.__pause:
                _pygame.mixer.music.pause()
        else:
            raise _pygame.error(f'pos {self.__audio_offset} is out of music range')

    def quit(self) -> None:
        if self.__quit:
            return

        # close up all assets
        self.clear_cache_frame()
        self.clip.close()
        self.__original_clip.close()
        self.__unload_audio()

        self.__quit = True
        self.__play = False
        self.__ready = False
        self.__pause = False

    def close(self) -> None:
        # same as .quit()
        self.quit()

_GLOBAL_VIDEO: _global_video[Video] = _global_video()

def quit(show_log: bool = True) -> None:
    # stop the audio
    _pygame.mixer.music.stop()
    # loop all existing videos
    video: Video
    global _GLOBAL_VIDEO
    for video in _GLOBAL_VIDEO:
        try:
            video.quit()
        except Exception as e:
            if show_log:
                print(f'Error durring quit / close Video: {video}: {_name(e)}: {e}')

    _GLOBAL_VIDEO.clear()

def close(*args, **kwargs) -> None:
    quit(*args, **kwargs)