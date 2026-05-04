# Adding a New Streaming Source

This folder contains source adapters used by AniFlow to:

- search streaming providers for anime titles,
- match AniFlow anime entries to provider entries, and
- build direct episode URLs for play/resume flows.

## Quick Overview

To add a new source (example: Netflix), you usually do four things:

1. create a new adapter in this folder,
2. register it in `apps/streaming/sources/__init__.py`,
3. seed the source in the database with a migration,
4. verify matching and playback flow end-to-end.

---

## 1) Create the Adapter

Create `apps/streaming/sources/netflix_source.py`.

Your adapter should follow the same contract as `base_source.py` and other adapters in this folder.

Implement these methods:

- `search(query: str) -> list[StreamingCandidate]`
- `build_search_url(query: str) -> str`
- `build_episode_url(source_identifier: str, episode_number: int) -> str`

### What `search()` must return

For each candidate, return:

- `title` (required)
- `slug` (required stable identifier)
- `year` (optional)
- `episodes` (optional)
- `studio` (optional)

`slug` is critical because it is stored as `source_identifier` in mapping records.

---

## 2) Register the Adapter

Update `apps/streaming/sources/__init__.py`:

- import your adapter class,
- add a branch in `get_adapter_for_source(...)` for source name aliases:
  - `"netflix"`,
  - any other aliases you want to support.

If this step is missed, AniFlow will fall back to `TemplateSourceAdapter`.

---

## 3) Seed the Source in the Database

Create a new migration in `apps/streaming/migrations/` to insert a `StreamingSource` row.

Recommended fields:

- `name="Netflix"`
- `base_url`
- `search_url_template`
- `episode_pattern`
- `priority`
- `is_active=True`

After creating the migration, run migrations so the source is available to routing/search.

---

## 4) Validate End-to-End

Check these user flows:

1. **Search page:** source appears with a working provider search link.
2. **Play/Resume:** mapping is created if a candidate is found.
3. **Confidence behavior:** high-confidence match auto-verifies; uncertain match goes to manual confirmation.
4. **Episode URL:** final redirect opens the expected episode page.

---

## Matching Notes

Matching logic lives in:

- `apps/streaming/matcher.py`
- `apps/streaming/services.py`
- `apps/anime/views.py` (confirmation flow entry)

Current behavior:

- low confidence: no mapping,
- medium confidence: mapping created but requires manual confirmation,
- high confidence: mapping created and auto-verified.

If provider data quality differs (naming style, metadata coverage), adapt extraction/normalization in your source adapter before changing global matcher thresholds.

---

## Minimal Adapter Checklist

- [ ] `netflix_source.py` added
- [ ] `search()` returns real candidates (not empty placeholders)
- [ ] adapter registered in `__init__.py`
- [ ] source seeded via migration
- [ ] play/resume tested for at least one title
- [ ] uncertain mapping confirmation tested

