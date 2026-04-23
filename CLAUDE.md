# soundboardclipfarm — Claude Code Bootstrap

## Project

Extract movie/TV quote audio clips as WAV files for a personal soundboard.
Three input modes: local file, title + quote, or just a quote (no title needed).

GitHub: https://github.com/rskrny/sounboardclipfarm

## Quick start

```bash
pip install -r requirements.txt   # ffmpeg + ffprobe must be on PATH
python serve.py                   # API at http://127.0.0.1:8000
# open ui.html in any browser
```

## Pipeline stages

| Stage | File | Notes |
|-------|------|-------|
| Quote identification | `clipfarm/quote_identify.py` | Title-free mode only |
| Preflight | `clipfarm/preflight.py` | Request classifier, advisory |
| Source media | `clipfarm/source_media.py` | 5-source chain |
| Fetch transcript | `clipfarm/fetch_transcript.py` | OpenSubtitles + Whisper fallback |
| Match quote | `clipfarm/match_quote.py` | rapidfuzz with normalization |
| Extract clip | `clipfarm/extract_clip.py` | ffprobe + ffmpeg PCM WAV |
| Orchestration | `clipfarm/pipeline.py` | All stages + progress callbacks |
| Service layer | `clipfarm/service.py` | FastAPI async job tracking |
| UI | `ui.html` | Self-contained, no build step |

## Source chain (priority order)

```
local_file → getyarn → internet_archive → youtube_cc → youtube_promo → youtube_official
```

GetYarn is approved for production (Ryan's decision, 2026-04-23).
All GetYarn clips carry `rights.policy = "review_needed"`.

## Shared data contracts

All inter-stage data flows through `clipfarm/models.py`.
Do not change `ClipRequest`, `ClipResult`, or `ProviderID` without coordinating.

ProviderID values: `local_file | getyarn | internet_archive | youtube_cc | youtube_promo | youtube_official`

## API endpoints

```
POST /upload                   Upload media/SRT file → { file_path }
POST /preflight                Classify request → { decision, user_message, blocking }
POST /extract                  Start job → { job_id }
GET  /jobs/{id}                Full job record (poll this)
GET  /jobs/{id}/download       Stream output WAV
GET  /config                   Providers, constraints, env vars
GET  /docs                     Swagger auto-docs
```

## Job record shape

```json
{
  "job_id": "...", "status": "queued|running|succeeded|failed",
  "stage": "identifying|preflight|sourcing|transcript|matching|extraction|done",
  "progress_message": "...", "result": { ...ClipResult... },
  "error": null, "actionable_hint": null,
  "diagnostics": [{ "stage": "...", "message": "..." }],
  "source": { "provider": "getyarn", "source_detail": "...",
              "provenance_evidence": "...", "rights_status": "review_needed",
              "conditions": "..." }
}
```

## Output spec

- Format: WAV, PCM little-endian
- Bit depth: 16-bit (fixed, pcm_s16le)
- Sample rate: configurable, default 44100 Hz
- Max duration: 15 seconds (enforced in extract_clip.py)

## Environment variables

```
OPENSUBTITLES_API_KEY   For subtitle fetch (optional — Whisper fallback if absent)
OPENSUBTITLES_USER      For subtitle fetch
OPENSUBTITLES_PASS      For subtitle fetch
CLIPFARM_SKIP_REMOTE=1  Skip all remote sources (testing only)
```

## External dependencies

- ffmpeg + ffprobe — must be on PATH
- beautifulsoup4 — GetYarn HTML scraping fallback (in requirements.txt)
- faster-whisper — optional no-subtitle transcription fallback
