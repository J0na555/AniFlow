# Adding a New Streaming Source

This folder contains source adapters used by AniFlow to:

- search streaming providers for anime titles,
- match AniFlow anime entries to provider entries,
- store a provider-specific identifier for later reuse,
- build direct episode URLs for play/resume flows,
- generate fallback provider search links when no mapping exists.

## Overview

To add a new source such as `Netflix` or `AniWaves`, the full process is:

1. add an adapter file in `apps/streaming/sources/`,
2. implement the adapter contract from `base_source.py`,
3. define `source_names` aliases on the adapter class,
4. seed a `StreamingSource` row through a migration,
5. run migrations,
6. verify search, matching, confirmation, and playback behavior.


## Simple Add-Source Flow (Recommended)

Use this checklist if you just want the minimum steps:

1. **Create adapter file**
   - Add `apps/streaming/sources/<source>_source.py`
   - Subclass `StreamingSourceAdapter`
   - Implement `search()` + `build_episode_url()`
   - Add `source_names = (...)`
2. **Add one data migration**
   - Create migration that does `StreamingSource.objects.update_or_create(...)`
   - Fill `name`, `base_url`, `search_url_template`, `episode_pattern`, `priority`, `is_active`
3. **Run migrations**
   - `python manage.py migrate`
4. **Test**
   - Search page source link
   - `anime_play` redirect
   - confirmation flow for uncertain matches

That is enough for a new provider to be discoverable and usable.

### Source selection behavior

AniFlow evaluates all active sources, ordered by:

1. user preferred source (if set),
2. then source `priority` (lower number first),
3. then source `name`.

If you add a new source and want it considered, set `is_active=True` and give it
the right `priority`.

---

## How Source Resolution Works Now

`get_adapter_for_source()` in `apps/streaming/sources/__init__.py` now:

- scans the modules in `apps/streaming/sources/`,
- imports adapter classes dynamically,
- reads each adapter's `source_names`,
- normalizes the database source name and alias values,
- returns the matching adapter,
- falls back to `TemplateSourceAdapter` when nothing matches.

This means the adapter file itself is enough **only if**:

- the class subclasses `StreamingSourceAdapter`,
- the class is importable,
- the class implements the required methods,
- the source name in the database matches one of the adapter aliases.

## Where the Link Is Configured

There are two different kinds of links:

1. **Search link**
   Used when AniFlow cannot build or find a verified episode mapping yet.

2. **Episode/play link**
   Used for play/resume once a source identifier is known.

The raw provider URL pieces are stored on the `StreamingSource` database row:

- `base_url`
- `search_url_template`
- `episode_pattern`

Those values are usually seeded in a migration under
`apps/streaming/migrations/`.

Current flow:

- `apps/anime/views.py`
  - `search_anime()` builds source search links with `adapter.build_search_url(query)`
  - `confirm_streaming_mapping()` also builds a provider search link for manual confirmation
- `apps/streaming/router.py`
  - `resolve_streaming_route()` calls `adapter.build_episode_url(...)` for play/resume

So if you are asking "where do I put the actual website link?", the answer is:

- put the source URLs in the seeded `StreamingSource` row,
- then use the adapter to transform titles/slugs into final provider URLs.

---

## 1) Create the Adapter File

Create a file such as:

- `apps/streaming/sources/netflix_source.py`

The adapter should subclass `StreamingSourceAdapter` from `base_source.py`.

Example shape:

```python
from __future__ import annotations

from apps.streaming.types import StreamingCandidate

from .base_source import StreamingSourceAdapter


class NetflixSourceAdapter(StreamingSourceAdapter):
    source_names = ("netflix",)

    def search(self, query: str) -> list[StreamingCandidate]:
        ...

    def build_episode_url(self, slug: str, episode: int) -> str:
        ...
```

### Required Methods

Implement:

- `search(query: str) -> list[StreamingCandidate]`
- `build_episode_url(slug: str, episode: int) -> str`

You may also override:

- `build_search_url(query: str) -> str`

If you do not override `build_search_url()`, the base class uses
`self.source.search_url_template.format(query=quote(query))`.

### `source_names`

Set `source_names` on the adapter class when the provider may appear under
multiple names.

Example:

```python
source_names = ("aniwaves", "ani waves")
```

This should match how the source may be stored in the `StreamingSource.name`
field.

### What `search()` Must Return

For each candidate, return a `StreamingCandidate` with:

- `title` required
- `slug` required
- `year` optional
- `episodes` optional
- `studio` optional

`slug` is the most important field because it is stored in
`AnimeStreamingMapping.source_identifier` and later reused by
`build_episode_url()`.

### Adapter Expectations

Your adapter should:

- return stable slugs, not random session URLs,
- normalize provider-specific paths before storing them,
- strip HTML from scraped titles before returning them,
- handle HTTP failures by returning `[]` rather than crashing,
- support full URLs as input if the provider sometimes returns absolute links.

---

## 2) Avoid Alias Collisions

Only one adapter should own a given alias.

For example, if `AniWavesSourceAdapter` defines:

```python
source_names = ("aniwaves", "ani waves")
```

then another adapter should not also claim those names.

If two adapters use the same alias, the factory may resolve to the wrong one.
The current registry is deterministic, but duplicate aliases are still a
configuration mistake and should be avoided.

---

## 3) Seed the Source in the Database

Add or update a migration in `apps/streaming/migrations/` that inserts the new
provider into `StreamingSource`.

Typical fields:

- `name="AniWaves"`
- `base_url="https://example.com"`
- `search_url_template="https://example.com/search?q={query}"`
- `episode_pattern="watch/{slug}/ep-{episode}"`
- `priority=10`
- `is_active=True`

Use `update_or_create()` so rerunning migrations keeps the row in sync.

Example:

```python
StreamingSource.objects.update_or_create(
    name="AniWaves",
    defaults={
        "base_url": "https://aniwaves.example",
        "search_url_template": "https://aniwaves.example/search?keyword={query}",
        "episode_pattern": "watch/{slug}/ep-{episode}",
        "priority": 15,
        "is_active": True,
    },
)
```

### What Each Field Does

- `name`
  The source name stored in the database. This is matched against adapter aliases.

- `base_url`
  The provider root URL used when building final watch links.

- `search_url_template`
  The search URL template used by the base adapter or custom adapters.

- `episode_pattern`
  The per-provider path template used to build episode URLs. Adapters may use
  this directly or build a provider-specific fallback when it is blank.

- `priority`
  Lower numbers are tried first in `resolve_streaming_route()`.

- `is_active`
  Controls whether the source appears in routing and search links.

### Important

Adding the adapter file alone is not enough. If there is no matching
`StreamingSource` row in the database, the app has no active source to route to.

---

## 4) Run the Migration

After creating the migration:

1. run `python manage.py migrate`
2. confirm the source row exists
3. confirm `name` matches one of the adapter's aliases

If the source name does not match the adapter aliases, AniFlow will fall back to
`TemplateSourceAdapter`.

---

## 5) Understand the Runtime Flow

When a user searches:

1. `apps/anime/views.py::search_anime()` loads active `StreamingSource` rows.
2. Each source is converted into an adapter via `get_adapter_for_source(source)`.
3. `build_search_url(query)` is used to render outbound provider search links.

When a user clicks play/resume:

1. `apps/streaming/router.py::resolve_streaming_route()` loads active sources ordered by priority.
2. Each source is turned into an adapter.
3. `apps/streaming/services.py::get_or_create_mapping()` calls the matcher.
4. If a candidate is accepted, its `slug` is stored as `source_identifier`.
5. `build_episode_url(source_identifier, next_episode)` generates the redirect URL.
6. If the match is uncertain, the user is sent to `confirm_streaming_mapping()`.

This is why `search()` and slug normalization need to be reliable.

---

## 6) Validate End-to-End

Test at least these flows:

1. **Search page**
   The source appears and the outbound provider search link opens the right site.

2. **Automatic match**
   A clearly matching anime creates a mapping and redirects correctly.

3. **Uncertain match**
   A medium-confidence match goes to confirmation instead of redirecting immediately.

4. **Confirmed playback**
   Confirming the mapping redirects to the expected episode URL.

5. **Repeat playback**
   A second play/resume uses the stored mapping instead of re-searching.

6. **No results**
   Search failures or provider downtime do not crash the request.

---

## Matching Notes

Matching logic lives in:

- `apps/streaming/matcher.py`
- `apps/streaming/services.py`
- `apps/streaming/router.py`
- `apps/anime/views.py`

Current behavior:

- low confidence: no mapping
- medium confidence: mapping created but requires manual confirmation
- high confidence: mapping created and auto-verified

If a provider has weaker metadata quality, prefer improving normalization inside
that source adapter before changing global matcher thresholds.

---

## Suggested Checklist

- [ ] adapter file added
- [ ] adapter subclasses `StreamingSourceAdapter`
- [ ] `source_names` aliases defined
- [ ] `search()` returns real candidates
- [ ] titles are cleaned and slugs are normalized
- [ ] source migration added or updated
- [ ] migration run locally
- [ ] source appears in search page links
- [ ] play/resume redirects correctly
- [ ] uncertain mapping confirmation tested
- [ ] aliases do not collide with another adapter

