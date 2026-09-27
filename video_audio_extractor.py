#!/usr/bin/env python3
"""
Video Audio Extractor
======================

Downloads a video from a URL using one of two methods:
  1. "ytdlp"  - uses yt-dlp, which supports YouTube and hundreds of other
                streaming sites (handles HLS/DASH, redirects, cookies, etc.)
  2. "direct" - a plain HTTP(S) streamed download using `requests`, meant
                for direct links to a video file (e.g. a CDN link ending
                in .mp4 that yt-dlp's generic extractor struggles with,
                or that times out because of network/CDN restrictions).

Method "auto" (default) tries yt-dlp first and automatically falls back
to a direct HTTP download if yt-dlp fails or the URL clearly points to a
raw media file.

After the video is downloaded, ffmpeg is used to extract the audio track
into a standalone file (mp3 by default).

Usage
-----
    python video_audio_extractor.py "<video_url>" [options]

Examples
--------
    # Auto-detect the best download method
    python video_audio_extractor.py "https://www.youtube.com/watch?v=XXXX"

    # Force the direct-download method for a CDN link with a token
    python video_audio_extractor.py "https://cdn.example.com/video.mp4?token=..." --method direct

    # Extract audio as WAV instead of MP3
    python video_audio_extractor.py "<url>" --audio-format wav

See README.md for full documentation.
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from tqdm import tqdm
except ImportError:  # tqdm is optional; fall back to no progress bar
    tqdm = None


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

VIDEO_EXTENSIONS = (
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".ts", ".m3u8", ".wmv",
)


class DownloadError(RuntimeError):
    """Raised when both download methods fail."""


def looks_like_direct_media_url(url: str) -> bool:
    """Heuristic: does the URL path end in a known video extension?"""
    path = urlparse(url).path.lower()
    return path.endswith(VIDEO_EXTENSIONS)


def build_requests_session(retries: int = 5, backoff_factor: float = 2.0) -> requests.Session:
    """Create a requests Session configured with sane retry behaviour."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def download_direct(url: str, output_dir: Path, timeout: int = 60) -> Path:
    """
    Download a video via a plain streamed HTTP(S) GET request.

    This bypasses yt-dlp entirely and is the most reliable method for
    direct links to a media file (CDN links, signed/tokenized URLs, etc.).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    session = build_requests_session()
    headers = {"User-Agent": DEFAULT_USER_AGENT}

    print(f"[direct] Connecting to {url}")
    with session.get(url, headers=headers, stream=True, timeout=timeout) as response:
        response.raise_for_status()

        # Try to guess a sensible file extension from the Content-Type header,
        # falling back to the URL path, then finally to .mp4.
        content_type = response.headers.get("Content-Type", "")
        guessed_ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) if content_type else None
        url_path_ext = Path(urlparse(url).path).suffix
        ext = url_path_ext if url_path_ext else (guessed_ext or ".mp4")
        if ext == ".mpga":  # mimetypes quirk for some video types
            ext = ".mp4"

        video_path = output_dir / f"video{ext}"
        total_size = int(response.headers.get("Content-Length", 0))

        progress = None
        if tqdm and total_size:
            progress = tqdm(total=total_size, unit="B", unit_scale=True, desc="Downloading")

        with open(video_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                if progress:
                    progress.update(len(chunk))

        if progress:
            progress.close()

    print(f"[direct] Saved video to {video_path}")
    return video_path


def download_with_ytdlp(url: str, output_dir: Path) -> Path:
    """Download a video using yt-dlp (supports YouTube and many other sites)."""
    from yt_dlp import YoutubeDL

    output_dir.mkdir(parents=True, exist_ok=True)
    ydl_opts = {
        "outtmpl": str(output_dir / "video.%(ext)s"),
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": False,
        "noprogress": False,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_path = Path(ydl.prepare_filename(info))
        if not video_path.exists():
            # merge_output_format may have changed the final extension to mp4
            alt = video_path.with_suffix(".mp4")
            if alt.exists():
                video_path = alt

    print(f"[ytdlp] Saved video to {video_path}")
    return video_path


def download_video(url: str, output_dir: Path, method: str) -> Path:
    """
    Dispatch to the requested download method.

    method: "auto" | "ytdlp" | "direct"
    """
    if method == "direct":
        return download_direct(url, output_dir)

    if method == "ytdlp":
        return download_with_ytdlp(url, output_dir)

    # method == "auto"
    if looks_like_direct_media_url(url):
        print("[auto] URL looks like a direct media file, using the 'direct' method.")
        try:
            return download_direct(url, output_dir)
        except Exception as direct_err:  # noqa: BLE001
            print(f"[auto] Direct download failed ({direct_err}), falling back to yt-dlp.")
            return download_with_ytdlp(url, output_dir)

    print("[auto] Trying yt-dlp first.")
    try:
        return download_with_ytdlp(url, output_dir)
    except Exception as ytdlp_err:  # noqa: BLE001
        print(f"[auto] yt-dlp failed ({ytdlp_err}), falling back to a direct HTTP download.")
        try:
            return download_direct(url, output_dir)
        except Exception as direct_err:  # noqa: BLE001
            raise DownloadError(
                f"Both download methods failed.\nyt-dlp error: {ytdlp_err}\ndirect error: {direct_err}"
            ) from direct_err


def find_ffmpeg() -> str:
    """Locate an ffmpeg binary, using imageio-ffmpeg as a portable fallback."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise RuntimeError(
            "ffmpeg was not found on PATH and imageio-ffmpeg is not installed. "
            "Install ffmpeg (e.g. `apt-get install ffmpeg`) or `pip install imageio-ffmpeg`."
        ) from exc


def extract_audio(video_path: Path, output_dir: Path, audio_format: str = "mp3") -> Path:
    """Extract the audio track from a video file using ffmpeg."""
    ffmpeg_bin = find_ffmpeg()
    audio_path = output_dir / f"audio.{audio_format}"

    codec_map = {
        "mp3": ["-vn", "-acodec", "libmp3lame", "-q:a", "2"],
        "wav": ["-vn", "-acodec", "pcm_s16le"],
        "aac": ["-vn", "-acodec", "aac", "-b:a", "192k"],
        "flac": ["-vn", "-acodec", "flac"],
    }
    codec_args = codec_map.get(audio_format, ["-vn"])

    cmd = [ffmpeg_bin, "-y", "-i", str(video_path), *codec_args, str(audio_path)]
    print(f"[ffmpeg] Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr}")

    print(f"[ffmpeg] Audio extracted to {audio_path}")
    return audio_path


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a video and extract its audio track.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("url", help="URL of the video to download")
    parser.add_argument(
        "--method",
        choices=["auto", "ytdlp", "direct"],
        default="auto",
        help="Download method: 'auto' picks the best one automatically",
    )
    parser.add_argument(
        "--output-dir",
        default="downloads",
        help="Directory where the video and extracted audio will be saved",
    )
    parser.add_argument(
        "--audio-format",
        choices=["mp3", "wav", "aac", "flac"],
        default="mp3",
        help="Output audio format",
    )
    parser.add_argument(
        "--keep-video",
        action="store_true",
        help="Keep the downloaded video file (by default it is kept too; use --delete-video to remove it)",
    )
    parser.add_argument(
        "--delete-video",
        action="store_true",
        help="Delete the downloaded video file after audio extraction to save disk space",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)

    try:
        video_path = download_video(args.url, output_dir, args.method)
        audio_path = extract_audio(video_path, output_dir, args.audio_format)
    except DownloadError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.delete_video and video_path.exists():
        os.remove(video_path)
        print(f"Deleted video file {video_path}")

    print("\n=== DONE ===")
    print(f"Audio file: {audio_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
