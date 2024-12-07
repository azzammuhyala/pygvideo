import pygame
import typing

from ._utils import asserter
from ._utils import name

from . import _utils
from . import _constants

if typing.TYPE_CHECKING:
    from ._pygvideo import Video

__all__ = [
    'video_preview'
]

AnsiStyle = typing.Literal['fg', 'bg']
ColorType = typing.Literal['RGBA', 'RGB', 'BGR', 'BGRA', 'CMYK']

# function color format color RGB ansi
def _color_rgb_ansi(r: int, g: int, b: int, style: AnsiStyle, luminance: bool) -> str:
    match style:
        case 'fg':
            return f'\u001b[38;2;{r};{g};{b}m'
        case 'bg':
            bg = f'\u001b[48;2;{r};{g};{b}m'

            if luminance:
                luminance_color = 0.299 * r + 0.587 * g + 0.114 * b

                if luminance_color > 128:
                    fg = _color_rgb_ansi(0, 0, 0, 'fg', False)
                else:
                    fg = _color_rgb_ansi(255, 255, 255, 'fg', False)

                return fg + bg

            return bg

        case _:
            raise ValueError(f'invalid style: {style!r}, expected one of {AnsiStyle.__args__!r}')

# function rgb to hex
def _rgb_to_hex(r: int, g: int, b: int, a: int | None, style: AnsiStyle, color: bool, luminance: bool) -> str:
    if a:
        fs = '#{:02x}{:02x}{:02x}{:02x}'.format(r, g, b, a)
    else:
        fs = '#{:02x}{:02x}{:02x}'.format(r, g, b)

    if color:
        return _color_rgb_ansi(r, g, b, style, luminance) + fs + '\033[0m'
    return fs

# function rgb to cmyk
def _rgb_to_cmyk(r, g, b):
    # RGB conversion to 0-1 scale
    r, g, b = r / 255, g / 255, b / 255

    # calculate Key (K)
    k = 1 - max(r, g, b)

    if k == 1: # full black color
        return (0, 0, 0, 100)

    # calculate C, M, Y
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)

    # convert to percentage
    return (round(c * 100),
            round(m * 100),
            round(y * 100),
            round(k * 100))

def _ansi_color(rgba: tuple[int, int, int, int], style: AnsiStyle, color_type: ColorType, color: bool, luminance: bool) -> str:
    r, g, b, a = rgba
    color_type = color_type.upper().strip() # convert to uppercase and strip whitespace

    match color_type:

        case 'RGBA':
            return 'RGBA({:>3},{:>3},{:>3},{:>3}) {}'.format(
                r, g, b, a,
                _rgb_to_hex(r, g, b, a, style, color, luminance))

        case 'RGB':
            return 'RGB({:>3},{:>3},{:>3}) {}'.format(
                r, g, b,
                _rgb_to_hex(r, g, b, None, style, color, luminance)
            )

        case 'BGR':
            return 'BGR({:>3},{:>3},{:>3}) {}'.format(
                b, g, r,
                _rgb_to_hex(r, g, b, None, style, color, luminance)
            )

        case 'BGRA':
            return 'BGRA({:>3},{:>3},{:>3},{:>3}) {}'.format(
                b, g, r, a,
                _rgb_to_hex(r, g, b, a, style, color, luminance)
            )

        case 'CMYK':
            return 'CMYK({:>3},{:>3},{:>3},{:>3}) {}'.format(
                *_rgb_to_cmyk(r, g, b),
                _rgb_to_hex(r, g, b, None, style, color, luminance)
            )

        case _:
            raise ValueError(f'invalid color_type: {color_type!r}, expected one of {ColorType.__args__!r}')

def _calculate_video_rect(canvas_wh: tuple[int, int], video_wh: tuple[int, int]) -> pygame.Rect:
    width_screen, height_screen = canvas_wh
    width_video, height_video = video_wh

    scale_factor = min(width_screen / width_video, height_screen / height_video)
    new_width = int(width_video * scale_factor)
    new_height = int(height_video * scale_factor)

    return pygame.Rect((width_screen - new_width) / 2,
                       (height_screen - new_height) / 2,
                       new_width, new_height)

def video_preview(

        video: 'Video',
        screen: typing.Optional[pygame.Surface] = None,
        width_height: typing.Optional[tuple[int, int] | list[int]] = None,
        background_color: tuple | list | str | pygame.Color = 'black',
        title: typing.Optional[str] = None,
        fps: typing.Optional[_utils.Number] = None,
        show_log: bool = True,
        color_log: bool = True,
        ansi_color_type: ColorType = 'RGBA',
        ansi_style: AnsiStyle = 'bg',
        ansi_luminance: bool = True

    ) -> None:

    asserter(
        isinstance(width_height, tuple | list | None),
        TypeError(f'width_height must be tuples, lists or None, not {name(width_height)}')
    )
    asserter(
        isinstance(fps, _utils.Number | None),
        TypeError(f'fps must be integers, floats or None, not {name(fps)}')
    )
    asserter(
        isinstance(screen, pygame.Surface | None),
        TypeError(f'screen must be surfaces or None, not {name(screen)}')
    )

    # initialize pygame
    pygame.init()
    pygame.mixer.init()

    s = screen

    if width_height is None:
        width_height = (500, 500)
    else:
        wh_len = len(width_height)
        asserter(
            wh_len == 2,
            ValueError(f'width_height must contain 2 values, not {wh_len}')
        )
        width_height = tuple(map(int, width_height))

    if screen is None:
        screen = pygame.display.set_mode(width_height, pygame.RESIZABLE)
        pygame.display.set_caption('PyGVideo - Preview{}'.format(f' ({title})' if title else ''))
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)

    log = lambda message : print(message) if show_log else None
    fwarn = lambda message : f'\033[33m(WARN: {message})\033[0m' if color_log else f'(WARN: {message})'
    frame = None
    running = True
    clock = pygame.time.Clock()
    fps = fps or video.get_fps()

    vsize = video.get_size()
    vcsize = video.get_clip_size()
    if vsize is not None:
        video_size = (max(vsize[0], vcsize[0]),
                      max(vsize[1], vcsize[1]))
    else:
        video_size = vcsize

    video_rect = _calculate_video_rect(screen.get_size(), video_size)

    video.preplay(-1)

    try:

        while running:

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.VIDEORESIZE:
                    screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                    video_rect = _calculate_video_rect(event.size, video_size)

                elif event.type == pygame.MOUSEBUTTONDOWN:

                    if event.button == 1:

                        preview_fps = clock.get_fps()
                        mouse_pos = pygame.mouse.get_pos()
                        hover_video = video_rect.collidepoint(mouse_pos)

                        if hover_video:
                            relative_pos = (mouse_pos[0] - video_rect.left,
                                            mouse_pos[1] - video_rect.top)
                            if frame:
                                r, g, b, a = frame.get_at(relative_pos)[0:4]
                                a = int(a * (video.get_alpha() / 255))  # alpha final
                                colour_str = _ansi_color(
                                    (r, g, b, a),
                                    ansi_style,
                                    ansi_color_type,
                                    color_log,
                                    ansi_luminance
                                )
                            else:
                                colour_str = ''

                        log(
                            ('[INFO] Time:     {:.03f}s\n'
                             '       FPS:      Preview={:.03f}{}, Video={:.03f}\n'
                             '       Position: {}\n'
                             '       {}').format(
                                video.get_pos() / 1000,
                                preview_fps,
                                (' ' + fwarn('FPS to low!')) if preview_fps < _constants.MIN_LOW_FPS else '',
                                video.get_fps(),
                                mouse_pos,
                                f'Relative: {relative_pos}\n       Color:    {colour_str}' if hover_video else fwarn('Mouse position out of video area.')
                            )
                        )

                if (key := video.handle_event(event)) is not None:

                    seconds_pos = video.get_pos() / 1000

                    if key == pygame.K_UP:
                        log(f'[INFO] add_volume 0.05, Current volume: {video.get_volume()}')

                    elif key == pygame.K_DOWN:
                        log(f'[INFO] sub_volume 0.05, Current volume: {video.get_volume()}')

                    elif key == pygame.K_LEFT:
                        log(f'[INFO] previous 5, Current time: {seconds_pos}s')

                    elif key == pygame.K_RIGHT:
                        log(f'[INFO] next 5, Current time: {seconds_pos}s')

                    elif key == pygame.K_0:
                        log(f'[INFO] jump 0, Current time: {seconds_pos}s')

                    elif key == pygame.K_1:
                        log(f'[INFO] jump 0.1, Current time: {seconds_pos}s')

                    elif key == pygame.K_2:
                        log(f'[INFO] jump 0.2, Current time: {seconds_pos}s')

                    elif key == pygame.K_3:
                        log(f'[INFO] jump 0.3, Current time: {seconds_pos}s')

                    elif key == pygame.K_4:
                        log(f'[INFO] jump 0.4, Current time: {seconds_pos}s')

                    elif key == pygame.K_5:
                        log(f'[INFO] jump 0.5, Current time: {seconds_pos}s')

                    elif key == pygame.K_6:
                        log(f'[INFO] jump 0.6, Current time: {seconds_pos}s')

                    elif key == pygame.K_7:
                        log(f'[INFO] jump 0.7, Current time: {seconds_pos}s')

                    elif key == pygame.K_8:
                        log(f'[INFO] jump 0.8, Current time: {seconds_pos}s')

                    elif key == pygame.K_9:
                        log(f'[INFO] jump 0.9, Current time: {seconds_pos}s')

                    elif key in (pygame.K_SPACE, pygame.K_p):
                        if video.is_pause:
                            log('[INFO] Video paused')
                        else:
                            log('[INFO] Video unpaused')

                    elif key == pygame.K_m:
                        if video.is_mute:
                            log('[INFO] Video muted')
                        else:
                            log('[INFO] Video unmuted')

            frame = video.draw_and_update()
            frame = pygame.transform.scale(frame, video_rect.size)

            screen.fill(background_color)
            screen.blit(frame, video_rect.topleft)

            pygame.display.flip()

            clock.tick(fps)

    finally:
        video.release()
        if s is None:
            # clear and set to default pygame
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
            pygame.display.set_caption('pygame window')
            pygame.mixer.quit()
            pygame.quit()