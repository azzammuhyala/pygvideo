import sys
import pygame
import moviepy

__all__ = [
    'pygvideo_version',
    'moviepy_version',
    'pygame_version',
    'pygameSDL_version',
    'python_version'
]

pygvideo_version: str = '1.4.0'
moviepy_version: str = moviepy.__version__
pygame_version: str = pygame.__version__
pygameSDL_version: str = '.'.join(map(str, pygame.get_sdl_version()))
python_version: str = '.'.join(map(str, sys.version_info[0:3]))

del sys, pygame, moviepy