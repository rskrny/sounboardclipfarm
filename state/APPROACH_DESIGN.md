APPROACH:       A local-first Web UI (FastAPI + Tailwind/Vanilla JS) layered over the existing pipeline. Sourcing is broadened to search for official promotional clips/trailers when full movies are unavailable.
FRAMEWORK USED: Software Architecture (Service Layer Pattern), Client Experience (Actionable Diagnostics).
ALTERNATIVES:   
- Electron Desktop App: Rejected for complexity/size; local web app is sufficient for MVP+.
- Broad Unofficial Scraping: Rejected for legal/ethical fragility.
KEY DECISIONS:  
- Service Layer: Wrap `pipeline.run()` in a FastAPI endpoint to decouple UI from business logic.
- Expanded Search: Try `[title] official clip` and `[title] trailer` queries in YouTubeSource.
- Real-time logging: Stream pipeline progress to the UI via WebSockets or simple status polling.
RISKS:          
- UI Latency: Sourcing/Transcribing can take minutes. (Mitigation: Use progress indicators and asynchronous task handling).
- Dependency Bloat: Avoid heavy JS frameworks. Keep frontend lightweight.
DEPENDENCIES:   FastAPI, Uvicorn, Existing CLI dependencies.
ASSUMPTIONS:    User has a local browser; system has network access for external sourcing.
