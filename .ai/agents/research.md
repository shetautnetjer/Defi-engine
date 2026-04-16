# Research Lane

## Purpose

Find the cleanest supported way forward for the active story with the lowest
new cost and the strongest official evidence.

## Required skills

- `research-skill`
- `exa-search-skill`
- `crawl4ai-skill`

## Workflow

1. Read `activeStoryId` in `prd.json`.
2. Read `.ai/index/current_repo_map.md` so you do not rediscover existing repo
   surfaces.
3. Start with the cheapest path:
   - official repo docs
   - current code/docs
   - `research-skill`
4. Use `exa-search-skill` only when the first pass finds the right surface but
   needs deeper docs or examples.
5. Use `crawl4ai-skill` to pin important official pages into the Library when
   snippets are not enough.
6. When launched in `research-finder` mode, focus on missing evidence, stale
   assumptions, doctrine-vs-runtime mismatches, and stronger simpler
   precedents. Do not widen into broad redesign.

## What to research

- math and modeling choices
- policy design patterns
- risk gate patterns
- settlement and paper-session ownership patterns
- cheaper or already-available provider paths before any new paid API

## Output rules

Write only to `.ai/dropbox/research/`.

Preferred artifacts:

- `<story-id>__brief.md`
- `<story-id>__doc_refs.json`
- `<story-id>__qa.md`
- `<scope>__research_gap_scan.md`
- `<scope>__unknowns_and_needed_evidence.json`
- `<scope>__followon_story_candidates.json`

Each brief should include:

- current question
- strongest official sources
- recommended cleanest path
- lower-cost fallback
- open unknowns

## Do not

- do not edit runtime code
- do not update story state
- do not update canonical docs directly
- do not recommend new paid APIs until current local/provider surfaces are
  clearly insufficient
- do not treat finder outputs as promoted backlog truth
