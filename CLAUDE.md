# soundboardclipfarm — Claude Code Bootstrap

## Project

Extract movie/TV quote audio clips as WAV files. User provides a title and a
line of dialogue. The tool locates the timestamp, sources audio legally, and
exports a clip under 15 seconds.

## Pipeline stages

| Stage | File | Owner |
|-------|------|-------|
| Source media | `clipfarm/source_media.py` | claude |
| Fetch transcript | `clipfarm/fetch_transcript.py` | claude + gemini |
| Match quote | `clipfarm/match_quote.py` | claude |
| Extract clip | `clipfarm/extract_clip.py` | codex |
| Orchestration | `clipfarm/pipeline.py` | claude |
| CLI | `cli.py` | claude |
| Data models | `clipfarm/models.py` | claude (shared contract) |

## Shared contracts

All inter-stage data flows through `clipfarm/models.py`. Do not change the
`ClipRequest` or `ClipResult` dataclasses without coordinating across agents.

## Legal sourcing rules

Only these sources are authorized:
- User-provided local files
- Internet Archive (public domain)
- Official studio YouTube channels via yt-dlp allowlist in `source_media.py`

Do not add scrapers, stream rippers, or unlicensed source fetchers.

## Output spec

- Format: WAV, PCM
- Bit depth: 16-bit (fixed)
- Sample rate: configurable, default 44100 Hz
- Max duration: 15 seconds (enforced in `extract_clip.py`)

## Environment variables required

```
OPENSUBTITLES_API_KEY
OPENSUBTITLES_USER
OPENSUBTITLES_PASS
```

## External dependencies

- ffmpeg + ffprobe must be on PATH
- faster-whisper is optional (no-subtitle fallback)
