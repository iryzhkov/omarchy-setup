# Who owns the resident instruction layer

The resident layer is the text an agent already holds before it reads anything: the shared
`CLAUDE.md` a Claude Code session imports, the `AGENTS.md` that Codex and OpenCode load
into every session, and the reference files those point at. It is the most-read
documentation on this fleet and it used to be the least reviewed, because nothing
installed it and nothing noticed when a host's copy stopped matching this repository.

This document says which file is authoritative for each installed artifact, which command
derives it, which module installs it, how it reaches the other machines, and what to do
when a host has drifted.

## The map

| Installed artifact | Authoritative source | Derived by | Installed by |
|---|---|---|---|
| `~/.claude/omarchy-setup/CLAUDE.md` | `config/claude/CLAUDE.md` | a byte-for-byte copy | `modules/common/31-agent-instructions.sh` |
| `~/.config/agents/AGENTS.md` | the heredoc in `config/bin/agents-instructions-gen` | `agents-instructions-gen` | the same module |
| `~/.config/agents/huyang.md` | the "Reading and editing code" section of `config/claude/CLAUDE.md`, plus `config/claude/skills/huyang/SKILL.md` | `agents-instructions-gen` | the same module |
| `~/.config/agents/jocasta.md` | the "Working documents: Jocasta" section of `config/claude/CLAUDE.md` | `agents-instructions-gen` | the same module |
| `~/.config/agents/ov-memory.md` | `config/claude/skills/ov-memory/SKILL.md` and `.../ov-memory-curation/SKILL.md` | `agents-instructions-gen` | the same module |
| `~/.config/agents/t3-steward.md` | `config/claude/skills/t3-backlog`, `t3-campaign` and `t3-wait` | `agents-instructions-gen` | the same module |
| the `<!-- fleet:start -->` block of `~/.codex/AGENTS.md` | `~/.config/agents/AGENTS.md` | `agents-instructions-gen` | the same module |
| the `instructions` list of `~/.config/opencode/opencode.json` | `~/.config/agents/AGENTS.md` | `agents-instructions-gen` | the same module |
| `~/.claude/skills/<name>/...` and `~/.agents/skills/<name>/...`, for the skills this repository carries | `config/claude/skills/<name>/...` | source projection | UpKeeper, from its release manifest |
| `~/.claude/CLAUDE.md` | the host's own `# This machine` section, plus the fleet block UpKeeper owns | nothing; it is authored | UpKeeper, merging into its fenced block |

One command regenerates everything in the middle of that table:

```sh
agents-instructions-gen --root /path/to/omarchy-setup
```

It reads the checkout and never `$HOME`. Given no `--root` it uses
`$OMARCHY_SETUP_ROOT`, and failing that the checkout it is running from; a copy installed
in `~/.local/bin` is not in a checkout, so it needs one of the first two. When it cannot
find a checkout it names the paths it looked for and changes nothing. That refusal is
deliberate: reading the installed copies back is how a hand-edit on one machine became
the whole fleet's instructions.

## How a change reaches the other machines

1. Edit the authoritative file in this repository, on a branch, and get it reviewed.
2. Converge the generated resident instructions on the machine you are working on:
   `run.sh`, or the module alone, or `agents-instructions-gen --root .` after copying
   `config/claude/CLAUDE.md` into place.
3. Confirm those generated resident instructions match:
   `agents-instructions-gen --root . --check` must exit 0.
4. Publish with `upkeeper push` from that machine, following the `publish-agent-tooling`
   skill. UpKeeper reads repository-owned skills from the pinned omarchy-setup checkout
   rather than from installed home-directory copies. It projects the complete skill trees
   to `~/.claude/skills` for Claude/OpenCode and `~/.agents/skills` for Codex. UpKeeper
   captures other agent-environment files under its own validation rules.
5. Other hosts converge on their next self-pull and receive those bytes.

Step 3 is the one that is easy to skip and the one that matters. A capture is a photograph
of the pushing host, so whatever that host is holding becomes the fleet's instructions,
reviewed or not. The 2026-09-18 release republished this machine's months-old copy while
the corrected text sat on `origin/main`. Running the check before the push is what makes
"a capture publishes derived bytes only" true.

## What the arrangement does and does not promise

It promises that a host that converges matches the repository, and that a host that has
diverged can be told so. It does not promise that any given host is current: nothing here
forces a converge, and a machine that has not pulled for a month is a month behind.

Nothing resident is authored on a host. A host keeps host-local text only where the merge
mode allows one, which today is the `# This machine` section of `~/.claude/CLAUDE.md`.
Everything else is replaced wholesale on the next convergence, so an edit made in place is
lost at best and published fleet-wide at worst.

## When a host has diverged

```sh
agents-instructions-gen --root /path/to/omarchy-setup --check
```

It writes nothing anywhere. It prints one line per artifact that differs, naming the path
and the direction: the host copy differs from a named source, or is absent and would be
installed, or is present in `~/.config/agents` and generated by nothing. Exit 0 means the
host matches, 3 means it has diverged, 1 means the check itself could not run. The three
codes are distinct so that CI can treat any divergence as a failure while a person on a
machine that is deliberately behind reads the report and decides.

When it reports a difference, decide which side is right before touching anything.

- **The host is behind.** Converge generated resident instructions with `run.sh` or
  `modules/common/31-agent-instructions.sh`. Skills are different: omarchy-setup is their
  reviewed source, but it never installs or publishes them. UpKeeper reads the pinned source
  tree while preparing the agent-environment component and is the only process that projects
  those bytes to harness discovery roots. Never copy or edit an installed skill to prepare a
  release; installed copies are outputs, not publication inputs.
- **The host holds an improvement nobody committed.** Copy the text into the authoritative
  file in this repository, review it, commit it, and then converge the host so that its
  copy is derived rather than original. Never publish from the host to keep the change.
- **The host holds something this repository has never seen and nobody wants.** Converge
  it. A file in `~/.config/agents` that nothing generates is deleted by the next
  generation only if the generator knows about it; otherwise remove it by hand.

Do not edit an installed copy to fix a report. The next convergence overwrites it, and an
UpKeeper capture taken from that host in the meantime publishes it to every machine.

## Where the checks run

- `test/run.sh` exercises the module against a throwaway `HOME` and asserts that the check
  passes on a converged host, exits 3 on a diverged one, names each difference, and
  changes nothing.
- `test/agents-instructions.py` builds a fixture checkout and a home whose installed copies
  all carry text the checkout never says, and asserts that none of it reaches the output.
- Both run in `.github/workflows/test.yml` on every push and pull request.
