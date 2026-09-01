---
name: ov-memory-curation
description: >
  Deliberate cleanup pass over the OpenViking memory store: find duplicate or
  contradictory notes, badly named namespaces, stale facts and overgrown
  documents, and fix what can be fixed safely. Use only when the user explicitly
  asks to tidy, audit, reorganise or refactor memory -- never during normal work.
  Triggers: curate memory, clean up memory, audit the knowledge base, reorganise
  OV, memory is stale, duplicate notes, rename namespace.
---

# Curating OV memory

A maintenance pass, run on request. Normal reading and writing is the
[ov-memory] skill; this one is about the shape of the store as a whole.

## Read this before moving anything

**`memory_mv` does not update the vector index.** Measured on 2026-08-28: after
moving `resources/iryzhkov/nvim-configuration` to `resources/nvim`, semantic
search kept returning the *old* URIs, which then read as empty. `/system/wait`
with idle queues did not heal it; the move had to be reverted to make search
results resolve again.

Consequences:

- **Never bulk-move indexed content.** Every move silently poisons search with
  dead URIs, and the damage is invisible until someone follows a hit.
- Moving is safe only for a namespace with nothing indexed under it yet.
- There is no `memory_delete` tool, and OpenViking exposes no re-index endpoint,
  so "move then re-ingest" cannot clean up after itself either.

Real reorganisation therefore needs `DELETE /api/v1/fs` plus re-ingestion, which
is a decision to put to the user, not something to improvise mid-pass.

## What a pass can safely do

1. **Audit, and report.** `memory_tree "viking://resources" level_limit=2` for
   the shape; `memory_overview` on anything unclear. Produce a findings list:
   duplicate subjects, `upload_<uuid>` names, namespaces holding one stray file,
   documents that have outgrown their subject.
2. **Correct additively.** When a note is wrong or superseded, write the
   corrected note into the right namespace and say in its text which URI it
   supersedes. Search surfaces both; the newer one explains itself.
3. **Fix naming at the source.** New content lands under a proper subject name.
   Bad names already indexed stay until a delete path exists.
4. **Leave a decision list.** End the pass with what could not be fixed and what
   it would cost, rather than half-applying a reorganisation.

## Known drift (as of 2026-08-28)

- `resources/homeassistant` and `resources/iryzhkov/homeassistant` are two
  namespaces for one subject.
- `resources/upload_864a4583ab504fe2ab2f688df6c17977` is a cooking guide in 16
  chunks under a raw upload id.
- `resources/iryzhkov/*` nests three subjects under a username.
- `resources/projects/*` mixes with top-level project namespaces.
- `memory_relations` returns `[]` everywhere: the relation graph is unused.

All of it is cosmetic-but-real, and all of it is blocked on the same missing
delete + re-index path.
