---
name: ov-memory
description: >
  Long-term memory shared by this machine's agents, held in OpenViking on homelab
  and reached through the ov-memory MCP tools. Use when the user refers to past
  work, decisions, infrastructure or credentials that are not in the current repo
  or conversation ("how did we set up X", "what did I decide about Y", "where does
  Z live"), when a question touches the homelab, and whenever the user asks you to
  remember something. Triggers: remember this, what do we know about, prior
  decision, homelab, infrastructure notes, project knowledge base, memory search.
---

# OV memory

An OpenViking store on homelab (`http://192.168.70.223:1933`), exposed by the
`ov-memory` MCP server. It is memory for *agents*, not a chat log: durable facts
about infrastructure, decisions and projects.

## Search before you assume

Anything about the homelab, past setup work, or "how did we do this last time"
is likely already recorded. Search first, answer second. `memory_search` is
cheap; being confidently wrong about a machine you cannot see is not.

## The store's shape

Four scopes live under the root (`memory_ls "/"`):

| Scope | Holds | Writable here |
| --- | --- | --- |
| `viking://resources/` | Documents and per-project knowledge bases (`homeassistant`, `projects`, `cv-site`, …) | **yes** |
| `viking://user/` | Distilled memories about the user | no |
| `viking://agent/` | Per-agent instructions, memories, skills | no |
| `viking://session/` | Raw session transcripts | no |

## Documents are directories

OpenViking ingests a document as a *directory* named for the file, holding its
chunk files plus hidden `.abstract.md` / `.overview.md`. So
`viking://resources/projects/ov-agent-access.md` is a directory, not a file.

- `memory_read` walks that directory and returns the parts joined in document
  order, so a note reads back as one text however it was chunked. It never
  answers with an empty string for a node that has content: when a node really
  holds no text it says so and lists what it does hold.
- `memory_abstract` and `memory_overview` want the *directory*; a plain file has
  neither.
- Search hits are grouped by document, so a result names the note rather than one
  chunk inside it. Pass `group=False` to see the raw records.
- Notes under an `archive/` namespace are hidden from results; pass
  `include_archived=True` when the history is the point.
## Which tool

- `memory_search` — concepts and questions. First stop.
- `memory_find` — same, but also ranks stored resources; use when hunting for a
  document rather than a fact.
- `memory_grep` / `memory_glob` — exact strings and filename patterns, when you
  already know what you are looking for.
- `memory_tree` / `memory_ls` / `memory_overview` — orienting in an unfamiliar
  area before reading anything.
- `memory_abstract` — triage a search hit without paying for the whole file.
- `memory_read` — the full document, once you know you want it.
- `memory_stat` — how big a document is, and how many parts, before reading it.
- `memory_relations` — stored links, the `[[wikilinks]]` in a note, and the notes
  that link back to it.
- `memory_status` — when calls fail, before blaming the network.

Work top-down: search, triage abstracts, then read only what earns it.

Reorganising and repair belong to the [ov-memory-curation] skill: `memory_mv`,
`memory_rm`, `memory_reindex`, `memory_index_audit` and `memory_index_prune` all
change the store, so they are for a pass the user has asked for, not for normal
reading and writing.
## What goes where

`viking://resources/` is flat, one namespace per subject. As of 2026-08-29:
`asahi/`, `omarchy/`, `emby/`, `gaming-pc/`, `homeassistant/`, `cooking/`,
`cv-site/`, `personal-site/`, `openviking/`, `projects/` (holds `forever-home/`),
`iryzhkov/` (homelab-infrastructure, nvim-configuration, a Home Assistant
config dump) and `volcengine/` (an OpenViking source checkout).

- `memory_ls "viking://resources"` before writing. Reuse a namespace; create one
  only for a genuinely new subject, named for the subject in lowercase. Never
  leave content under an `upload_<uuid>` name -- nothing will find it later.
- **OV is the primary store.** Everything durable goes here: infrastructure,
  services, project knowledge, machine quirks, decisions and their reasons.
- **`~/.claude/projects/-home-igor/memory/`** is a cache of the subset that is
  about this laptop, kept because its `MEMORY.md` index loads automatically each
  session. A note that belongs there is written to *both* places.
- **The repo** holds what the code already says. Do not mirror it; point at it.
- Credentials: prefer a pointer ("key in the GNOME keyring, service=X") over the
  secret itself. Some older memories embed real credentials; do not add more.

## Writing

`memory_write` only, and only when the user asks for something to be remembered.
This store is curated on purpose: nothing is written automatically, so it stays
small enough to be worth searching.

- `to` must be under `viking://resources/`. The agent and user scopes are
  written solely by OpenViking's own session extraction, and `/resources`
  rejects writes elsewhere.
- Put the note in an existing namespace where one fits (`memory_ls
  "viking://resources"` to see them); create one with `memory_mkdir` only for a
  genuinely new area.
- Write the fact and *why it is true*, not the conversation around it. A note
  that will not make sense in six months is not worth storing.
- Indexing costs OpenAI embedding calls, so do not mirror things that live in a
  repo or in git history — link to them instead.
- The write is verified: it is read back and compared with what was sent, and the
  reply says so. A `WARNING` there means the stored text differs from what you
  wrote — keep the original in the conversation until that is understood.
- Superseding an existing note: write the new one, and store the old version with
  `archived=True`, which files it under `archive/` so it stops competing with the
  live note in search. Link related notes with `[[note-name]]`; those are resolved
  and recorded as real links on write.
- Ingestion reshapes long content. A Markdown note keeps every line, but its title
  becomes the name of the directory holding it and its sections come back in name
  order; a note written under another extension (`config.yaml`, `output.txt`)
  keeps every word but loses whitespace where the chunks were cut. For content
  that has to come back character-for-character -- configuration, command output,
  anything quoted -- pass `verbatim=True`, which stores it in parts that rejoin
  exactly.

## Machine-local memory is a cache of OV

`~/.claude/projects/-home-igor/memory/` holds this machine's own notes and loads
automatically each session. Its notes were mirrored into OV on 2026-08-29, so
the two stores now agree. Keep them agreeing: a new note about this laptop is
written to OV first and copied there second (with its one-line pointer added to
`MEMORY.md`); everything else lives in OV alone.

Do not treat the auto-loaded `MEMORY.md` index as the extent of what is known.
It is one line per laptop note, and OV holds far more, so search OV anyway.
