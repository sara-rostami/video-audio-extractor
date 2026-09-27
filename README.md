# Video Audio Extractor

Download a video from a URL and extract its audio track — works both as a
command-line tool and inside Google Colab.

Two download methods are supported, and the tool can pick automatically:

| Method   | Best for                                                                 |
|----------|---------------------------------------------------------------------------|
| `ytdlp`  | YouTube and hundreds of other streaming sites (handles HLS/DASH, redirects, cookies, age-gates, etc.) |
| `direct` | Direct/CDN links straight to a media file (`.mp4`, `.mkv`, ...), including signed/tokenized URLs that yt-dlp's generic extractor sometimes fails or times out on |
| `auto`   | Tries the best guess first, and automatically falls back to the other method if it fails |

Audio is extracted with `ffmpeg` into `mp3`, `wav`, `aac`, or `flac`.

## Repository structure

```
video-audio-extractor/
├── video_audio_extractor.py     # Main script (CLI tool)
├── requirements.txt             # Python dependencies
├── Video_Audio_Extractor_Colab.ipynb  # Ready-to-run Google Colab notebook
├── .github/
│   └── workflows/
│       └── extract_audio.yml    # GitHub Actions workflow (run on github.com)
├── README.md                    # This file
└── .gitignore
```

## Requirements

- Python 3.8+
- `ffmpeg` installed and on your `PATH` (or the `imageio-ffmpeg` package,
  which is included in `requirements.txt` as a portable fallback and needs
  no system installation)

## Installation (local machine / server)

```bash
git clone https://github.com/YOUR_USERNAME/video-audio-extractor.git
cd video-audio-extractor
pip install -r requirements.txt

# Optional but recommended: install ffmpeg system-wide
# Debian/Ubuntu:
sudo apt-get install -y ffmpeg
# macOS (Homebrew):
brew install ffmpeg
```

## Usage

```bash
python video_audio_extractor.py "<video_url>" [options]
```

### Options

| Flag              | Description                                                        | Default     |
|-------------------|----------------------------------------------------------------------|-------------|
| `--method`        | `auto`, `ytdlp`, or `direct`                                          | `auto`      |
| `--output-dir`    | Directory to save the video and audio files                          | `downloads` |
| `--audio-format`  | `mp3`, `wav`, `aac`, or `flac`                                        | `mp3`       |
| `--delete-video`  | Delete the downloaded video file after extracting the audio          | off         |

### Examples

```bash
# Auto-detect the best method (e.g. for a YouTube link)
python video_audio_extractor.py "https://www.youtube.com/watch?v=XXXXXXXXXXX"

# Force the direct-download method for a CDN link with a signed token
python video_audio_extractor.py \
  "https://edge.example.com/files/movie/video_480p.mp4?token=eyJhbGciOi..." \
  --method direct

# Extract audio as WAV and remove the video afterwards
python video_audio_extractor.py "<url>" --audio-format wav --delete-video
```

The script prints the path to the extracted audio file at the end, e.g.:

```
=== DONE ===
Audio file: /home/user/video-audio-extractor/downloads/audio.mp3
```

## Usage in Google Colab

1. Open `Video_Audio_Extractor_Colab.ipynb` in Google Colab
   (`File → Upload notebook`, or open it directly from GitHub once pushed).
2. Run the cells in order:
   - Cell 1 clones this repo and installs dependencies.
   - Cell 2 asks for the video URL, method, and audio format.
   - Cell 3 runs the extractor.
   - Cell 4 triggers a browser download of the resulting audio file.

## Running it directly on GitHub (GitHub Actions)

You don't need Colab or a local machine — this repo includes a ready-made
GitHub Actions workflow (`.github/workflows/extract_audio.yml`) that runs
the extractor entirely on GitHub's own servers and gives you the resulting
audio file as a downloadable artifact.

### How to run it

1. Push this repo to GitHub (see the section below if you haven't yet).
2. Open your repository on GitHub and click the **Actions** tab.
   - If prompted, click **"I understand my workflows, go ahead and enable them"**.
3. In the left sidebar, click **"Extract Audio From Video"**.
4. Click the **"Run workflow"** dropdown (top right of the file list) and fill in:
   - **video_url**: the video link
   - **method**: `auto`, `ytdlp`, or `direct`
   - **audio_format**: `mp3`, `wav`, `aac`, or `flac`
5. Click the green **"Run workflow"** button.
6. Wait for the run to finish (refresh the page; a green checkmark means success).
7. Click into the finished run, scroll down to **"Artifacts"**, and download
   **`extracted-audio`** — a zip containing your audio file.

### Notes

- GitHub-hosted runners (`ubuntu-latest`) run on Microsoft Azure cloud IPs
  (mostly US/EU), so the same origin-blocking issue described below can
  still apply to some CDNs.
- Artifacts are kept for 7 days by default (configurable via `retention-days`
  in the workflow file) and count against your GitHub Actions storage quota.
- For very large videos, be mindful of the `timeout-minutes: 30` limit in
  the workflow — increase it if needed for longer videos.
- You can trigger the workflow via the GitHub CLI instead of the web UI:
  ```bash
  gh workflow run extract_audio.yml \
    -f video_url="https://example.com/video.mp4" \
    -f method="direct" \
    -f audio_format="mp3"
  ```

## Why direct links sometimes fail with `yt-dlp`

Some CDNs (especially ones geofenced to a specific country) reject or time
out connections coming from cloud/datacenter IP ranges such as Google
Colab's. If you see a `ConnectTimeoutError` or `Connection ... timed out`
error with `--method ytdlp` or `auto`, try `--method direct` explicitly —
it uses a plain streamed HTTP request with automatic retries, which is
more resilient for these links. If the direct method also times out, the
server itself is blocking the request's origin IP, which no client-side
code can bypass.

## How to create this repository on GitHub

If you received these files as a folder/zip rather than a live repo,
here is how to turn them into your own GitHub repository:

1. **Create a new empty repository on GitHub**
   - Go to https://github.com/new
   - Repository name: `video-audio-extractor` (or any name you like)
   - Leave "Initialize this repository with a README" **unchecked**
   - Click **Create repository**

2. **Initialize git locally and push the files**

   ```bash
   cd video-audio-extractor
   git init
   git add .
   git commit -m "Initial commit: video/audio downloader and extractor"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/video-audio-extractor.git
   git push -u origin main
   ```

   Replace `YOUR_USERNAME` with your actual GitHub username, and
   authenticate with a Personal Access Token or SSH key when prompted
   (GitHub no longer accepts plain passwords over HTTPS).

3. **(Optional) Update the notebook's clone URL**
   Open `Video_Audio_Extractor_Colab.ipynb` and replace
   `YOUR_USERNAME` in the `git clone` cell with your actual GitHub
   username, then commit and push the change.

4. **Done.** You (or anyone else) can now open the notebook directly in
   Colab via `File → Open notebook → GitHub`, paste your repo URL, and run it.

## License

Use and modify freely. Make sure you have the right to download and
process any video you use this tool with.
