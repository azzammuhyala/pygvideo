"""
PyGVideo, video for PyGame. Using MoviePy video module to read and organize videos.
"""

import os

# Imports all pygvideo
from . import _version as pygvideo_ver
from ._pygvideo import __all__ as _pygvideo_all
from ._pygvideo import *

__version__ = pygvideo_ver.pygvideo_version
__all__ = _pygvideo_all + ['pygvideo_ver']

if 'PYGAME_VIDEO_HIDE_SUPPORT_PROMPT' not in os.environ:
    print(
        f'PyGVideo {pygvideo_ver.pygvideo_version} ('
        f'MoviePy {pygvideo_ver.moviepy_version}, '
        f'PyGame {pygvideo_ver.pygame_version}, '
        f'PyGame-SDL {pygvideo_ver.pygameSDL_version}, '
        f'Python {pygvideo_ver.python_version})'
    )

del os, _pygvideo_all