# pygvideo
PyGVideo, video for Pygame. Using MoviePy video module to read and organize videos.

## Description
PyGVideo or PyGameVideo is a Python library, particularly based on the Pygame library, for video playback or editing. You can process or edit videos and play them directly on a Pygame screen. With the MoviePy module or library, you can edit videos such as trimming, cropping, or adding effects available in MoviePy.

PyGVideo can play videos and sync audio playback. The supported formats by PyGVideo are video formats that contain audio, such as MP4, MOV, AVI, MKV, WMV, FLV, and WebM. Although MoviePy supports non-audio formats like GIF, PyGVideo currently does not support these. PyGVideo works only on Python versions >=3.10, Pygame >= 2.5.0, and MoviePy >= 1.0.3. Below is a simple usage example:

```py
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

In fact, the MoviePy module has some fairly complex methods, and I still need to learn more about this module, so this is what I can provide for you so far :)

## Installation
Installation is quite simple, you just need to use the pip method with the following command:
> pip install pygvideo

Wait for the download process and for MoviePy (automatically) to be downloaded until it is complete.

Alternatively, you can also download this module from [GitHub](https://github.com/azzammuhyala/pygvideo) or through [PyPi](https://pypi.org/project/pygvideo).

## Getting started with PyGVideo

Here is a complete documentation explanation regarding PyGVideo:

### Class `Video`

#### `__init__`
This functions similarly to `VideoFileClip` in MoviePy and also includes the necessary properties for [`Video`](#class-video). In this method, the following parameters are included:
- `filename_or_clip`: The video location or directly the `VideoFileClip` class. Ensure the video format is compatible and supported by [`Video`](#class-video).
- `target_resolution`: The target resolution. Similar to the [`resize`](#resize) method.
- `logger`: Logger type, consisting of:
    - `'bar'`: Displays a logger with a bar. Useful for tracking audio writing or caching.
    - `'verbose'`: Displays detailed information about events occurring in `VideoFileClip`. (I’m not sure if this works).
    - `None`: No logger is displayed.
- `has_mask`: Loads the video with alpha or transparency support. Only available for certain video formats such as WebM.
- `load_audio_in_prepare`: Creates or generates a temporary audio file when the [`prepare`](#prepare) method is called. If set to `False`, the temporary audio will be loaded earlier. However, it is less recommended if you want to edit the video first before calling [`prepare`](#prepare).
- `cache`: When set to `True`, this automatically stores video frames in the cache or places them in temporary frames. [`Video`](#class-video) will not need to retrieve frames from `get_frame` in `VideoFileClip`. This makes the video run more smoothly.

#### `reinit`
Reload the video or refresh the video. If for example you have quited or closed the video, you can call reinit to reinitialize it.

#### `copy`
Copies an instance of [`Video`](#class-video). All effect changes on the MoviePy clip will be copied.

#### `get_original_clip`
Retrieves the original clip instance.

#### `get_clip`
Retrieves the clip instance.

#### `get_filename`
Retrieves the video filename path.

#### `get_temp_audio`
Retrieves the temporary audio filename path.

#### `get_total_cache_frame`
Retrieves the total number of frames that have been stored in the cache.

#### `get_original_size`
Retrieves the original size of the video clip in raw form, without any clip modifications.

#### `get_clip_size`
Retrieves the original size of the video clip.

#### `get_size`
Retrieves the current video size.

#### `get_file_size`
Retrieves the video file size (uses `os.path.getsize` to get the file size, so there may be slight differences, meaning this is just an estimated file size).

#### `get_original_width`
Retrieves the original width of the video clip in raw form, without any clip modifications.

#### `get_clip_width`
Retrieves the original width of the video clip.

#### `get_width`
Retrieves the current video width.

#### `get_original_height`
Retrieves the original height of the video clip in raw form, without any clip modifications.

#### `get_clip_height`
Retrieves the original height of the video clip.

#### `get_height`
Retrieves the current video height.

#### `get_loops`
Retrieves the number of loops played by the video. The loop count will reset to 0 when [`prepare`](#prepare) is called.

#### `get_pos`
Retrieves the current position of the video while it's playing. Returns a floats or a value in milliseconds, or one of the following codes:
- `-1`: Video is not ready. [`prepare`](#prepare) has not been called.
- `-2`: Video has not started playing. [`play`](#play) has not been called.

#### `get_alpha`
Retrieves the alpha or transparency of the video.

#### `get_duration`
Retrieves the duration of the video.

#### `get_start`
Retrieves the start time of the video.

#### `get_end`
Retrieves the end time of the video.

#### `get_total_frame`
Retrieves the total number of video frames. Used this code: `int(clip.duration * clip.fps)`.

#### `get_fps`
Retrieves the frames per second (fps) of the video.

#### `get_volume`
Retrieves the volume of the video.

#### `get_frame_index`
Retrieves the current frame index (while the video is playing).

#### `get_frame`
Retrieves a frame at a specific time index. The parameters are as follows:
- `index_time`: The time index of the frame. If you want to get the frame using a regular index, use the code `x * (1 / video.get_fps())` or `x * (1 / video.clip.fps)`.
- `get_original`: To retrieve the raw frame from the clip or not.

#### `get_frame_array`
Similar to the [`get_frame`](#get_frame) method but returns the frame as an array using `numpy`.

#### `iter_chunk_cache_frame`
Loads the cache in the form of a generator function, allowing you to directly retrieve the frame surface and the ongoing index. This is suitable for debugging or as part of your project. Here's how to use it:

1. First, create an instance of the generator:

```py
func = video.iter_chunk_cache_frame()
```

2. Create a loop for the generator:
```py
for frame_surf, index, ran in func:
    # your code
```

The generator returns `yield` values as follows:

- `frame_surf`: The cached frame that has been saved. If the frame is completely black or blank, it means there was an error when retrieving the video frame.
- `index`: The current cache index. (It will return a value of -1, indicating that caching is complete).
- `ran`: The total cache range at that moment, or you can get this through [`get_total_frame`](#get_total_frame).

The generator also captures messages from the generator's `send` method, which, when called, will stop the generator process and display a message on the console:
> Video - Done with the generator stopped. Reason: {MESSAGE FROM SEND PARAMETER}

When you call the `send` function, you should also `close` it with stop to properly terminate the generator. Here's an example usage:
```py
func.send('Memory is full.')
func.close()
```
This will display a message on the console:
> Video - Done with the generator stopped. Reason: Memory is full.

#### `is_cache_full`
Indicates whether the cache memory is full.

#### `is_ready`
Indicates whether the video is ready or [`prepare`](#prepare) has been called and is ready to play.

#### `is_pause`
Indicates whether the video is paused.

#### `is_play`
Indicates whether the video is currently playing.

#### `is_mute`
Indicates whether the video is muted.

#### `is_quit`
Indicates whether the video has exited, or [`quit`](#quit) / [`close`](#close) has been called.

#### `is_close`
Same as the [`is_quit`](#is_quit) method.

#### `draw_and_update`
Updates the video while simultaneously drawing the displayed frame. This method returns the current frame surface. Here's an example usage:
```py
frame = video.draw_and_update(SCREEN, (0, 0))
```

This method has several parameters:
- `screen_surface`: The surface on which the frame will be drawn. This is optional.
- `pos`: The position where the frame will be drawn.

If you need to modify the video frame before it is finally drawn to the main surface, you can simply omit the parameters and store the return value of this method as follows:
```py
frame = video.draw_and_update()
# do something with the frame surface
```
This method is called when the video is ready and playing.

FYI, the frame obtained is not a raw frame.

#### `preview`
Displays a preview of the video. Equivalent to the code: `video.clip.preview(*args, **kwargs)`.

#### `prepare`
Prepares the video and audio. This method loads the temporary audio `__temp__.mp3` / `__temp_X__.mp3` and then loads the audio into `pygame.mixer.music`. It also checks whether other [`Video`](#class-video) class instances are active/ready, and if not, raises a `pygame.error`. exception. This method is called after all video editing or configuration is completed so that it only needs to be played with [`play`](#play).

#### `release`
Releases temporary audio resources, allowing other [`Video`](#class-video) class instances to call [`prepare`](#prepare) again.

#### `play`
Plays the video and audio. It has the following parameters:
- `loops`: Determines how many times the video will repeat. If set to -1 or a negative number, it will loop indefinitely.
- `start`: Specifies the starting point for playback.

This method cannot be called before [`prepare`](#prepare) is called because the audio must be ready.

#### `stop`
Stops the video and audio.

#### `pause`
Pauses the video and audio. The difference from the [`stop`](#stop) method is that you can still call the [`draw_and_update`](#draw_and_update) method, and the video won't reset to 0 when you call [`unpause`](#unpause).

#### `unpause`
Unpauses the video and audio.

#### `mute`
Mutes the audio. If you call the [`get_volume`](#get_volume) method, it will return 0.

#### `unmute`
Unmutes the audio.

#### `jump`
Skips the video to a specific ratio between 0 and 1. The `ratio` parameter determines the video’s skip position. For example, if you want to go to the middle of the video, you can set the parameter as `ratio=0.5` or `ratio=1/2`.

In addition to calling this method, you can also use the `xor` operator with the `^`. syntax. For example:
```py
# regular call
video.jump(0.5)
# calling with xor
video ^ 0.5
```

#### `next`
Skips the video forward by a specified time interval. The `distance` parameter determines the time in seconds to skip the video.

This method can also be called using the `rshift` operator with the `>>`. syntax. For example:
```py
# regular call
video.next(5)
# calling with rshift
video >> 5
```

#### `previous`
This method is almost the same as the [`next`](#next) method, except that it rewinds the video instead of skipping forward.

Similar to the [`next`](#next) method, you can call this with the `lshift` operator using the `<<` syntax. For example:
```py
# regular call
video.previous(5)
# calling with lshift
video << 5
```

#### `create_cache_frame`
Creates a cache of frames. The difference between this and [`iter_chunk_cache_frame`](#iter_chunk_cache_frame) is that this method is not a generator. You can set the maximum number of frames to cache by passing the `max_frame` parameter as an integer or `None` if you want to cache all frames.

#### `clear_cache_frame`
Deletes or clears the cache of frames. This method is called when you edit the video with [`custom_effect`](#custom_effect) or other [`Video`](#class-video) methods.

#### `reset`
Resets the video clip's effects back to its original state. You can call this method using the `invert` operator with the `~` syntax. For example:
```py
# regular call
video.reset()
# calling with invert
~video
```

#### `custom_effect`
Applies or customizes an `fx` effect from MoviePy or the clip’s methods. There is an important parameter:
- `func`: The `fx` function or method name as a string.

The remaining parameters are the arguments or keyword arguments for the `fx` function.

For xample:
```py
# set rotation to 180 degrees with clip.rotate(180)
video.custom_effect('rotate', 180)

# method from fx
import moviepy.video.fx.all as vfx
video.custom_effect(vfx.rotate, 180)
```

You can directly edit the video using `video.clip`, but it is strongly discouraged.

#### `invert_colors`
Inverts the video’s colors, making them negative.

#### `grayscale`
Converts the video to grayscale or black and white.

#### `crop`
Crops the video using `pygame.Rect`. The `rect` parameter determines the position and size of the cropped area.

Like before, this method can be called using the `modulus` operator with the `%` syntax. For example:
```py
# regular call
video.crop(pygame.Rect(0, 0, 100, 100))
# calling with modulus
video % pygame.Rect(0, 0, 100, 100)
```

#### `rotate`
Rotates the video frame. The `rotate` parameter specifies the degree of rotation.

Like before, this method can be called using the `matmul` operator with the `@` syntax. For example:
```py
# regular call
video.rotate(180)
# calling with matmul
video @ 180
```

#### `resize`
Resizes the video in the clip. The `scale_or_size` parameter can take different types:
- Integer type for scaling the video size. For example, 0.5 makes the video half its original size.
- List or tuple type for specific dimensions. For example, `[100, 100]` or `(100, 100)` resizes the video to 100x100.

Like before, this method can be called using the `mul` or `truediv` operators with the `*` and `/` syntax. For example:
```py
# regular call
video.resize(2)
# calling with mul
video * 2

# regular call
video.resize(1/2)
# or
video.resize(0.5)
# calling with truediv
video / 2

# both lists and tuples work similarly
# they yield the same output
video * (100, 100)
video / (100, 100)
```

#### `mirror`
Mirrors the video frame. The `axis` parameter determines the mirror axis: `'x'` for horizontal and `'y'` for vertical.

As before, you can call this method using the `or` operator with the `|` syntax. For
```py
# regular call
video.mirror('x')
# calling with or
video | 'x'
```

#### `fade`
Applies an intro or outro by fading to or from black. The parameters for this method are:
- `type`: The type of fade, either `'in'` for an intro or `'out'` for an outro.
- `duration`: The duration of the fade.

#### `cut`
Cuts the video's duration. The parameters for this method are:
- `start`: The starting point of the cut, in seconds.
- `end`: The ending point of the cut, in seconds.

#### `add_volume`
Increases the video's volume. The parameters for this method are:
- `add`: The amount to increase the volume.
- `max_volume`: The maximum volume increase allowed. The default is 1 (recommended).
- `set`: Allows volume adjustment even when the audio is muted. (It will not cause an exception, but no volume change will occur when called).

As before, you can call this method using the `add` operator with the `+` syntax. For example:
```py
# regular call
video.add_volume(0.05)
# calling with add
video + 0.05
```

#### `sub_volume`
This method is similar to [`add_volume`](#add_volume), but it is used to decrease the video's volume. The changes are as follows:
- The `add` parameter is renamed to `sub`.
- The `max_volume` parameter is renamed to `min_volume`, and its default is 0 (recommended).
- The operator call changes to `sub` with the `-` syntax.

Sebagai contoh:
```py
# regular call
video.sub_volume(0.05)
# calling with sub
video - 0.05
```

#### `set_alpha`
Sets the alpha or transparency for the frame surface. The `value` parameter defines the alpha level, ranging from 0 (fully transparent) to 255 (fully opaque).

#### `set_size`
Adjusts the size of the video frame surface. Unlike the [`resize`](#resize) method, this one only performs a scaling transformation on the surface. The `size` parameter specifies the desired video size. Set it to `None` if you want to reset the size.

#### `set_speed`
Sets the speed of the video clip. The `speed` parameter adjusts the video playback speed.

As before, you can call this method using the `pow` or `floordiv` operators with the `**` and `//` syntax, respectively. For example:
```py
# regular call
video.set_speed(2)
# calling with pow
video ** 2

# regular call
video.set_speed(1/2)
# or
video.set_speed(0.5)
# calling with floordiv
video // 2
```

#### `set_fps`
Sets the FPS (frames per second) of the video clip. The `fps` parameter defines the desired FPS. This method may reduce the number of frames in videos with many frames, which can use up a lot of RAM, especially if caching is enabled. It is recommended to set the FPS between 24 and 30 FPS.

#### `set_volume`
Sets the volume of the video. The parameters are:
- `volume`: The value for volume adjustment, ranging from 0 to 1.
- `set`: Allows volume adjustment even when the audio is muted. (It will not cause an exception, but no volume change will occur when called).

#### `set_pos`
Changes the position of the currently playing video in seconds. The `pos` parameter sets the position in seconds for the video to resume. This will raise an exception if the value exceeds the video duration.

#### `quit`
Exits, cleans up, and frees the video while also deleting the temporary audio file `__temp__.mp3` / `__temp_X__.mp3`. The `show_log` parameter to determine whether to display error messages or not during the video closing process.

#### `close`
This method is identical to [`quit`](#quit).

#### `__getitem__`
This method is used to retrieve a frame by its index. Similar to the [`get_frame`](#get_frame) method, it also returns a frame surface, but the index is a regular index instead of a time-based one. Additionally, this method supports slice indexing. It does not use caching to retrieve the video frame, so it may take some time. Below are some usage examples:
```py
# To get the first frame
first_frame = video[0]

# To get the last frame
last_frame = video[-1]

# To get frames from the 10th to the 100th
scene_frames = video[10:100]

# To get frames from the 10th to the 100th, with every 5th frame
scene_frames = video[10:100:5]
```

#### `__enter__` and `__exit__`
These methods are part of the Python _context manager_ syntax, which simplifies resource management. With this, the [`Video`](#class-video) class will automatically close or exit when outside the `with` block, or if an exception occurs inside it. This helps prevent file or memory leaks and releases the video file properly. Here are some usage examples:
```py
import random

with pygvideo.Video('myvideo.mp4') as video:
    random_index = random.randint(0, video.get_total_frame())
    thumbnail = video[random_index]
```

#### `__iter__` and `__next__`
These methods implement the _iterator protocol_, allowing the [`Video`](#class-video) class to loop using the `for` keyword and yielding frame surfaces. Here is an example:
```py
for frame in video:
    screen.blit(frame, (0, 0))
```

#### Comparison Operators
Several _comparison operators_ such as `__eq__`, `__ne__`, etc., are also available in the [`Video`](#class-video) class. The comparison is not based on object comparison or other criteria, but rather on the video duration. For example, if you want to compare the duration of an intro and outro video, you can use the following code:
```py
intro = pygvideo.Video('intro.mp4')
outro = pygvideo.Video('intro.mp4')

if intro == outro:
    print('Same duration!')
elif intro > outro:
    print('Intro is bigger duration than outro')
```

In addition to comparing the [`Video`](#class-video) instances, you can also compare with other objects such as `VideoFileClip` from MoviePy or with integers or floats representing milliseconds:
```py
clip = VideoFileClip('someclip.mp4')

if intro == 5000:
    print('Duration intro is 5s!')
if outro < clip:
    print('Outro is small than someclip duration')
```

#### `__bool__`, `__list__`, `__tuple__`, `__len__`, `__repr__`, `__str__`, and `__copy__`
The remaining methods have the following functions:
- `__bool__`: Returns `True` if the video is initialized.
- `__list__`: Returns a list of all video frames. (Not nearly all of them).
- `__tuple__`: Similar to `__list__`, but returns a tuple instead.
- `__len__`: Returns the total number of video frames.
- `__repr__`: Returns the string repr of the object.
- `__str__`: Returns brief information about the video.
- `__copy__`: For copying using the `copy` method.

### Function `quit`
Exits, cleans up, and releases the video globally. All the videos you have loaded will be released. This function is highly recommended once you no longer need the video or when you exit the Pygame window.

### Function `close`
This function is the same as the [`quit`](#function-quit) function.

## Environment Variables

These are the environment variables from the `os.environ` module.

### `PYGAME_VIDEO_HIDE_SUPPORT_PROMPT`
Set this environment variable to hide the support prompt in the console. This must be set before importing PyGVideo.

### `PYGAME_VIDEO_TEMP`
Set this environment variable to specify the directory path where audio or any temporary files are stored. For example, if you have a folder `./temp`, set this environment variable to `./temp`.

### `PYGAME_VIDEO_USED`
This variable checks whether a video is in use or not. It will have the value `'1'` when a video is being used and `'0'` when none are in use. This changes when the methods [`prepare`](#prepare) and [`release`](#release) are called. For safety and to avoid exceptions, do not alter this value manually.

## Additional Information

### What's new in version 1.0.0?
This is the first version of the PyGVideo module. There may be improvements and updates following this release.

## Kredit
* Me ([AzzamMuhyala](https://github.com/azzammuhyala))
* [ChatGPT](https://chatgpt.com) -- LOL