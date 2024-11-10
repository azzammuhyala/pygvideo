import pygame
import typing

from ._utils import asserter as _assert
from ._utils import name as _name
from . import _utils

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

        video,
        width_height: typing.Optional[tuple[int, int] | list[int, int]] = None,
        fps: typing.Optional[_utils.Number] = None,
        screen: typing.Optional[pygame.Surface] = None,
        show_log: bool = True

    ) -> None:

    _assert(
        isinstance(width_height, tuple | list | None),
        TypeError(f'width_height must be tuples, lists or None, not {_name(width_height)}')
    )
    _assert(
        isinstance(fps, _utils.Number | None),
        TypeError(f'fps must be integers, floats or None, not {_name(fps)}')
    )
    _assert(
        isinstance(screen, pygame.Surface | None),
        TypeError(f'screen must be surfaces or None, not {_name(screen)}')
    )

    # initialize pygame
    pygame.init()
    pygame.mixer.init()

    if width_height is None:
        width_height = (500, 500)
    else:
        wh_len = len(width_height)
        _assert(
            wh_len == 2,
            ValueError(f'width_height must contain 2 values, not {wh_len}')
        )
        width_height = tuple(map(int, width_height))

    if screen is None:
        screen = pygame.display.set_mode(width_height, pygame.RESIZABLE)

    pygame.display.set_caption('PyGVideo - Preview')

    log = lambda message : print(message) if show_log else None
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

                if (key := video.handle_event(event)) is not None:

                    if key == pygame.K_UP:
                        log(f'[INFO] add_volume 0.05, current volume: {video.get_volume()}')
                    elif key == pygame.K_DOWN:
                        log(f'[INFO] sub_volume 0.05, current volume: {video.get_volume()}')
                    elif key == pygame.K_LEFT:
                        log(f'[INFO] previous 5, current pos: {video.get_pos()}')
                    elif key == pygame.K_RIGHT:
                        log(f'[INFO] next 5, current pos: {video.get_pos()}')
                    elif key == pygame.K_0:
                        log(f'[INFO] jump 0, current pos: {video.get_pos()}')
                    elif key == pygame.K_1:
                        log(f'[INFO] jump 0.1, current pos: {video.get_pos()}')
                    elif key == pygame.K_2:
                        log(f'[INFO] jump 0.2, current pos: {video.get_pos()}')
                    elif key == pygame.K_3:
                        log(f'[INFO] jump 0.3, current pos: {video.get_pos()}')
                    elif key == pygame.K_4:
                        log(f'[INFO] jump 0.4, current pos: {video.get_pos()}')
                    elif key == pygame.K_5:
                        log(f'[INFO] jump 0.5, current pos: {video.get_pos()}')
                    elif key == pygame.K_6:
                        log(f'[INFO] jump 0.6, current pos: {video.get_pos()}')
                    elif key == pygame.K_7:
                        log(f'[INFO] jump 0.7, current pos: {video.get_pos()}')
                    elif key == pygame.K_8:
                        log(f'[INFO] jump 0.8, current pos: {video.get_pos()}')
                    elif key == pygame.K_9:
                        log(f'[INFO] jump 0.9, current pos: {video.get_pos()}')
                    elif key in (pygame.K_SPACE, pygame.K_p):
                        if video.is_pause():
                            log('[INFO] video unpaused')
                        else:
                            log('[INFO] video paused')
                    elif key == pygame.K_m:
                        if video.is_mute():
                            log('[INFO] video unmuted')
                        else:
                            log('[INFO] video muted')

            frame = video.draw_and_update()
            frame = pygame.transform.scale(frame, video_rect.size)

            screen.blit(frame, video_rect.topleft)

            pygame.display.flip()

            clock.tick(fps)

    finally:
        video.release()
        pygame.display.set_caption('pygame window')
        pygame.quit()