"""
PyGVideo, video for Pygame. Using MoviePy video module to read and organize videos.
"""

import os

from . import version as version
from ._pygvideo import (
    Video as Video,
    quit as quit,
    close as close
)

__version__ = version.pygvideo_version
__all__ = [
    'Video',
    'quit',
    'close',
    'version'
]

if 'PYGAME_VIDEO_HIDE_SUPPORT_PROMPT' not in os.environ:
    print(
        f'pygvideo {version.pygvideo_version} ('
        f'MoviePy {version.moviepy_version}, '
        f'Pygame {version.pygame_version}, '
        f'Pygame-SDL {version.pygameSDL_version}, '
        f'Python {version.python_version})'
    )

del os