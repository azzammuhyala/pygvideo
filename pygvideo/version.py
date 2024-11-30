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

pygvideo_version = '1.4.0.dev2'
moviepy_version = moviepy.__version__
pygame_version = pygame.__version__
pygameSDL_version = '.'.join(map(str, pygame.get_sdl_version()))
python_version = '.'.join(map(str, sys.version_info[0:3]))

del sys, pygame, moviepy