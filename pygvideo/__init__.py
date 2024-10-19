"""
PyGVideo, video for Pygame. Using MoviePy video module to read and organize videos.
"""

__all__ = ['Video', 'quit', 'close']
__version__ = '1.0.0'

from ._pygvideo import (
    Video as Video,
    quit as quit,
    close as close
)
import os
import sys
import pygame
import moviepy

if 'PYGAME_VIDEO_HIDE_SUPPORT_PROMPT' not in os.environ:
    print(
        f"pygvideo {__version__} ("
        f"Moviepy {moviepy.__version__}, "
        f"Pygame {pygame.__version__}, "
        f"Pygame-SDL {'.'.join(map(str, pygame.get_sdl_version()))}, "
        f"Python {'.'.join(map(str, sys.version_info[0:3]))})"
    )

del os, sys, pygame, moviepy