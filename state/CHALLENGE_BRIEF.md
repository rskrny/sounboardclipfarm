CHALLENGE:     Enhance the soundboardclipfarm tool with a non-technical Web UI and broader authorized media discovery (official clips/trailers).
CONTEXT:       The CLI MVP is functional but inaccessible to the target client. Sourcing is currently too narrow for mainstream titles without local files. Phase 2 must bridge the "usability gap" with a GUI and the "content gap" with smarter authorized searches.
IMPACT:        Non-technical users can independently generate assets. Increased success rate for commercial titles via official promotional media.
ROOT CAUSE:    CLI-only interface is a barrier for the client; sourcing logic is biased toward full movies, missing legitimate authorized clips.
SCOPE:         
- IN: FastAPI/Flask backend, Vanilla JS frontend, official YouTube clip/trailer discovery, provenance tracking (which source/query worked), Aeneas alignment research.
- OUT: Commercial DRM bypass, unauthorized scraping, complex user auth (local only).
SUCCESS CRITERIA: 
- 1. Client can perform extraction via a local browser interface.
- 2. "Bee Movie" and similar titles resolve via official promotional clips without manual file paths.
- 3. UI displays clear, actionable diagnostics for sourcing and matching failures.
