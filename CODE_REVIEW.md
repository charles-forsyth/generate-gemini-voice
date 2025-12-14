# Code Review Report for `generate-gemini-voice`

## Executive Summary
The codebase is generally well-structured and uses modern Python practices (`pydantic`, `concurrent.futures`). However, there is a **critical security vulnerability** involving a hardcoded API key check that renders the tool unusable for general users. Additionally, the current memory management strategy poses a significant stability risk for large workloads (e.g., the requested 350-page processing).

## 1. Critical Security Vulnerability
**Severity: CRITICAL**
- **Location:** `src/generate_gemini_voice/core.py` (Lines 13, 22-24, 33-38)
- **Issue:** The code strictly validates the `GOOGLE_API_KEY` against a hardcoded value (`EXPECTED_API_KEY`).
    ```python
    EXPECTED_API_KEY = "AIzaSyCTSY0AKGrDHmzSyuV_9MyTBpMGKOKQl2M"
    ...
    if api_key == EXPECTED_API_KEY:
        # ... logic ...
    else:
        raise RuntimeError(f"An unexpected GOOGLE_API_KEY was loaded...")
    ```
- **Impact:** This prevents *any* user from using their own API key. The tool is effectively locked to a single (likely invalid or compromised) key.
- **Recommendation:** **Immediate removal** of `EXPECTED_API_KEY` and the associated `if/else` block. The application should accept any valid string provided by the user's environment.

## 2. Stability & Performance (Large Workloads)
**Severity: HIGH**
- **Location:** `src/generate_gemini_voice/core.py` -> `generate_speech`
- **Issue:** The application accumulates all generated audio chunks in memory (`audio_data_list`) before stitching and writing to disk.
    - **Scenario:** For 350 pages (~175,000 words), the resulting WAV file could be 500MB - 1GB+. Storing this entirely in RAM is risky and inefficient.
- **Recommendation:** Implement **streaming writes**.
    - For **WAV**: Write a placeholder header, append chunks to the file as they complete (must ensure order!), and patch the header size at the end.
    - For **MP3**: Append chunks directly to the file as they arrive (ordered).

## 3. Robustness
**Severity: MEDIUM**
- **Location:** `src/generate_gemini_voice/utils.py` -> `combine_audio_data`
- **Issue:** The WAV stitching logic assumes `audio_chunks[0]` is a valid WAV file with a 44-byte header. If the first chunk is empty or malformed (e.g., due to an API error returning empty bytes), the stitching will fail or produce corrupt audio.
- **Recommendation:** Add validation to ensure chunks are not empty and start with `RIFF` before processing.

## 4. Usability
**Severity: MEDIUM**
- **Issue:** No progress feedback. For long tasks (350 pages), the user sees a blank screen for potentially minutes.
- **Recommendation:** Add a simple progress indicator (e.g., "Processing chunk X/Y...").

## 5. Code Quality
**Severity: LOW**
- **Location:** `src/generate_gemini_voice/config.py`
- **Issue:** The `ensure_config_exists` function writes a default config with placeholders. This is good, but it runs *every* time the module is imported.
- **Recommendation:** Ensure it checks for existence efficiently and maybe move it to a CLI `init` command or keep it as is if startup cost is negligible.

## Action Plan
1.  **Fix Security:** Remove `EXPECTED_API_KEY` logic immediately.
2.  **Fix Stability:** Refactor `generate_speech` to write to disk incrementally, avoiding OOM on large files.
3.  **Improve UX:** Add a lightweight progress logger.
