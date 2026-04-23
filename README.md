# soundboardclipfarm

Extract any movie or TV quote as a WAV audio clip. Give it a title and a line — it finds the timestamp, sources the audio legally, and exports a clean clip under 15 seconds.

## Quick start

```bash
pip install -r requirements.txt
# Requires ffmpeg installed on PATH

python cli.py --movie "The Big Lebowski" --quote "The dude abides" --output dude_abides.wav --file lebowski.mp4
```

> **Windows users:** Always wrap paths that contain spaces in double quotes.
> ```
> python cli.py --movie "Bee Movie" --quote "Ya like jazz" --output "C:\Users\name\clip farm\output\clip.wav"
> ```

## Usage

```
python cli.py --movie TITLE --quote PHRASE --output FILE [options]

Required:
  --movie       Movie or TV show title
  --quote       Line or phrase to find
  --output      Output .wav file path

Options:
  --file        Path to local media file you already have (skips sourcing)
  --srt         Path to local .srt subtitle file (skips transcript fetch)
  --sample-rate Output sample rate in Hz (default: 44100)
  --channels    1=mono, 2=stereo (default: 1)
  --pad-before  Milliseconds of audio before the line (default: 200)
  --pad-after   Milliseconds of audio after the line (default: 200)
  --language    Subtitle language code (default: en)
```

## Media sources (in priority order)

1. **Local file** (`--file`) — your own media, most reliable, always use this for mainstream titles
2. **Internet Archive** — public domain films only (pre-1928 and similar); mainstream titles will not be found here
3. **YouTube** — searches YouTube via yt-dlp and downloads the best audio match

For any well-known copyrighted film (Big Lebowski, Bee Movie, etc.) the tool
cannot guarantee finding it automatically. Pass `--file` with a copy you already
have for a guaranteed result:

```
python cli.py --movie "The Big Lebowski" --quote "The dude abides" --output clip.wav --file lebowski.mp4
```

## Transcript sources (in priority order)

1. **Local SRT** (`--srt`) — your own subtitle file
2. **OpenSubtitles API** — requires `OPENSUBTITLES_API_KEY`, `OPENSUBTITLES_USER`, `OPENSUBTITLES_PASS` env vars
3. **faster-whisper** — local transcription fallback (optional install)

## Environment variables

```
OPENSUBTITLES_API_KEY=your_key
OPENSUBTITLES_USER=your_username
OPENSUBTITLES_PASS=your_password
```

## Output format

- Container: WAV (PCM)
- Bit depth: 16-bit
- Sample rate: configurable (default 44100 Hz)
- Channels: configurable (default mono)
- Max duration: 15 seconds

## Requirements

- Python 3.9+
- ffmpeg + ffprobe on PATH
