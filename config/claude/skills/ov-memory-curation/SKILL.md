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

## Moving and deleting are safe now

Both were once one-way doors, and older notes in this store still say so. As of
2026-09-05 the ov-mcp server repairs the index around them, so a real
reorganisation is an ordinary pass rather than a decision to escalate.

What the server actually does, and why the tools compensate:

- **`POST /fs/mv` half-updates the vector index.** It rewrites the records of the
  files it can list, but each document's hidden `.abstract.md` and
  `.overview.md` are filtered out of that listing, so their records keep pointing
  at the old URI, outrank the live note, and resolve to nothing. `memory_mv`
  prunes those orphans after every move and, by default, re-ingests the moved
  documents so their abstracts index at the new URI.
- **`DELETE /fs` removes the node before it cleans the index**, so it fails on a
  node that is already gone and cannot repair an orphan. `memory_index_prune`
  does that repair; `memory_index_audit "<query>"` finds the orphans by running
  the query, resolving every hit and reporting the ones with no node behind them,
  and `fix=True` prunes them.
- **`memory_rm` does clear the index** for the note it deletes, and also prunes
  the hidden records the server leaves behind. It takes `dry_run=True`; use it,
  because there is still no undo.
- **`memory_reindex`** rebuilds a note's chunks, abstract and index records from
  its current content. Use it when a note was moved with `reindex=False`, or when
  search returns a URI that no longer matches where the note lives.

The one cost to weigh: re-ingestion regenerates the abstract through the model,
so a move of a large namespace is not free. `memory_mv` skips re-ingestion above
twenty documents and says so.
## What a pass can do

1. **Audit, and report.** `memory_tree "viking://resources" level_limit=2` for
   the shape; `memory_overview` on anything unclear. Produce a findings list:
   duplicate subjects, `upload_<uuid>` names, namespaces holding one stray file,
   documents that have outgrown their subject.
2. **Check the index against the store.** Run `memory_index_audit` on the
   questions the store is supposed to answer. A hit that resolves to nothing is
   an orphaned record, and `fix=True` removes it.
3. **Reorganise.** `memory_mv` a badly named namespace or note, then confirm with
   `memory_index_audit` on a query the moved note should answer. Move a whole
   namespace in one call rather than note by note; each call re-ingests what it
   moved.
4. **Correct additively.** When a note is wrong or superseded, write the
   corrected note into the right namespace and say in its text which URI it
   supersedes. `memory_write(..., archived=True)` files the old version under
   `archive/`, where it stops competing with the live note in search.
5. **Delete what is genuinely dead**, with `dry_run=True` first, and only what the
   user has agreed to lose. There is no undo.
6. **Leave a decision list.** End the pass with what could not be fixed and what
   it would cost, rather than half-applying a reorganisation.
## Known drift (as of 2026-09-05)

- `resources/homeassistant` and `resources/iryzhkov/homeassistant` are two
  namespaces for one subject.
- `resources/iryzhkov/*` nests three subjects under a username.
- `resources/projects/*` mixes with top-level project namespaces.

Fixed on 2026-09-05, and left here as a record of what these tools now handle:
the cooking guide that sat under `resources/upload_864a4583ab504fe2ab2f688df6c17977`
left an orphaned abstract record behind when it was moved, which ranked first for
cooking questions and read as empty; `memory_index_prune` removed it, and an audit
across fourteen subject queries found no other orphan in the store.

`memory_relations` no longer returns `[]` for a note with `[[wikilinks]]`: the
links are parsed and resolved by ov-mcp, and recorded in OpenViking as real links
when a note is written.
