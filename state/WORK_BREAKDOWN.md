DELIVERABLES:
  1. Service Layer (`clipfarm/service.py`) → method: direct | depends on: pipeline | STATUS: DONE
  2. Advanced Sourcing (`clipfarm/source_media.py` expansion) → method: direct | depends on: none | STATUS: DONE
  3. Web UI Backend (FastAPI endpoints) → method: codex | depends on: 1 | STATUS: TODO
  4. Web UI Frontend (HTML/CSS/JS) → method: codex/gemini | depends on: 3 | STATUS: TODO
  5. Aeneas Alignment Research → method: gemini | depends on: none | STATUS: TODO

PARALLEL GROUPS:
  Group A (Backend): Tasks 1, 2
  Group B (Frontend): Tasks 3, 4
  Group C (R&D): Task 5

CRITICAL PATH: 2 -> 1 -> 3 -> 4
COMPLEXITY:    Medium
EXIT GATE: Client can successfully extract a clip via browser.
