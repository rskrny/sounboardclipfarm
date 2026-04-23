# Pipeline Handoff

## Active Engagement
Creating a high-fidelity movie audio extraction tool (soundboardclipfarm). MVP (CLI) is delivered. Phase 2 (Web UI + Advanced Sourcing) is initiating.

## Pipeline Status
- Phase 1 (CLI MVP): **DELIVERED**
- Phase 2 (Web UI + Advanced Sourcing): **Stage 1 (Define Challenge)**

## Key Decisions
- Adopted 8-stage developer pipeline per `AGENTS.md`.
- Sourcing: Prioritize Local -> Public Domain (IA) -> Authorized YouTube.
- Extraction: 16-bit PCM WAV ≤15s.
- Matcher: `token_set_ratio` for short quotes; aggressive text normalization.
- UI: Minimal local web UI (FastAPI/Flask + Vanilla JS).

## Open Items
- [ ] Broaden authorized YouTube search to include official trailers and clips.
- [ ] Implement local Web UI for non-technical users.
- [ ] Integrate Aeneas for high-precision alignment fallback.

## Deliverables
- `clipfarm/`: Core pipeline logic.
- `cli.py`: CLI interface.
- `test_samples/`: Deterministic verification fixtures.
- `state/`: Full 8-stage documentation.

## Domain Context
- `media-sourcing.md`: Policy-driven media acquisition.
- `audio-engineering.md`: DSP and extraction standards.
- `ai-ml-engineering.md`: Quote matching and alignment (needs project-specific update).
- `software-architecture.md`: System modularity and UI/Backend boundary.

## Resume Instructions
1. Load `state/CHALLENGE_BRIEF.md` for Phase 2.
2. Coordinate with @Copilot on Web UI architecture.
3. Broaden `YouTubeSource` to capture official clips.
