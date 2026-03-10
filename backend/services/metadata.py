import asyncio
from pathlib import Path


VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv"}
AUDIO_EXTS = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".svg"}
SUBTITLE_EXTS = {".srt", ".vtt", ".ass", ".sub", ".ssa", ".txt"}


def classify_asset_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in SUBTITLE_EXTS:
        return "subtitle"
    return "video"


async def extract_metadata(file_path: str, asset_type: str) -> dict:
    if asset_type == "video":
        return await _extract_video_metadata(file_path)
    if asset_type == "audio":
        return await _extract_audio_metadata(file_path)
    if asset_type == "image":
        return await _extract_image_metadata(file_path)
    # subtitle / unknown
    return {
        "duration_seconds": None,
        "width": None,
        "height": None,
        "format": Path(file_path).suffix.lstrip("."),
        "metadata_extra": None,
    }


def _empty_result(file_path: str) -> dict:
    return {
        "duration_seconds": None,
        "width": None,
        "height": None,
        "format": Path(file_path).suffix.lstrip("."),
        "metadata_extra": None,
    }


async def _extract_video_metadata(file_path: str) -> dict:
    loop = asyncio.get_event_loop()

    def _read():
        try:
            from moviepy import VideoFileClip

            clip = VideoFileClip(file_path)
            result = {
                "duration_seconds": round(clip.duration, 3),
                "width": clip.size[0],
                "height": clip.size[1],
                "format": Path(file_path).suffix.lstrip("."),
                "metadata_extra": {
                    "fps": clip.fps,
                },
            }
            clip.close()
            return result
        except Exception:
            return _empty_result(file_path)

    return await loop.run_in_executor(None, _read)


async def _extract_audio_metadata(file_path: str) -> dict:
    loop = asyncio.get_event_loop()

    def _read():
        try:
            from moviepy import AudioFileClip

            clip = AudioFileClip(file_path)
            result = {
                "duration_seconds": round(clip.duration, 3),
                "width": None,
                "height": None,
                "format": Path(file_path).suffix.lstrip("."),
                "metadata_extra": {
                    "fps": clip.fps,
                    "nchannels": clip.nchannels,
                },
            }
            clip.close()
            return result
        except Exception:
            return _empty_result(file_path)

    return await loop.run_in_executor(None, _read)


async def _extract_image_metadata(file_path: str) -> dict:
    loop = asyncio.get_event_loop()

    def _read():
        try:
            from PIL import Image

            with Image.open(file_path) as img:
                return {
                    "duration_seconds": None,
                    "width": img.width,
                    "height": img.height,
                    "format": (img.format or "").lower() or None,
                    "metadata_extra": {"mode": img.mode},
                }
        except Exception:
            return _empty_result(file_path)

    return await loop.run_in_executor(None, _read)
