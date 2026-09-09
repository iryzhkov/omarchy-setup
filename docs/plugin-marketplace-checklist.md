# Omarchy plugin marketplace: pre-submission checklist

Distilled from every manual review comment the marketplace maintainer
(HANCORE-linux) left on the last 600 submissions to
`omacom/omarchy-plugin-marketplace` (737 comments across 372 plugins,
2026-08-31 to 2026-09-04), plus the four rounds each of glide-menus, omaperch
and omadeck went through. Counts are how many plugins were blocked on the item.

The reviewer's own approval formula, stated verbatim in dozens of threads:

> approval requires current HEAD = validation SHA = decoded baseline SHA =
> manually reviewed SHA

Everything below is about surviving the manual review that follows the
automated baseline. The automated baseline itself only catches curl-pipe-shell,
unpinned git execution, dangerous sudoers and PID files in `/tmp`; a `passed`
there means nothing about the manual pass.

## 0. How the review works, so the fixes land

- **One final commit, then revalidate.** The reviewer refuses to approve across
  mismatched SHAs, and re-validation with blockers still open just burns a
  round. Fix everything, push once, edit the issue body to trigger validation,
  then do not touch the branch until the review comes back. README-only and
  preview-only pushes also invalidate the snapshot. (~110 plugins hit this.)
- **Reply with the full 40-character SHA** and a point-by-point response to each
  finding, quoting what changed and what you measured on a live shell. The
  reviewer re-reads the whole tree, not just the diff.
- **Keep the labels.** Do not remove `needs-fixes`, `security-needs-fixes`,
  `security-review-required` or `manual-setup`; the maintainer restores them and
  says so.
- **Expect three to seven rounds** for anything that spawns processes, edits
  config files or talks to the network. Each fix exposes the next layer of the
  same boundary. Zero-round approvals happen only for pure-QML widgets that read
  shell state and write nothing.
- **The reviewer asks for adversarial tests as part of the fix**, not as
  optional extras: planted symlink/FIFO, oversized output, TERM-ignoring
  descendant, hostile `PATH`/`BASH_ENV`, interrupted write, PID reuse. A test that
  cannot actually perform the swap it claims to test is rejected as evidence.
- **The "narrower threat model" correction (2026-09-04 07:33)** downgraded two
  things to non-blocking hardening: same-UID pathname races on plugin-private
  state that no privileged or long-lived component consumes, and missing
  timeouts/streaming caps on trusted first-party Omarchy helpers. Everything else
  in this list was still blocking the same morning. Credential exposure,
  privilege changes and anything crossing a trust boundary got stricter, not
  looser.

## 1. Repository and payload

- [ ] `manifest.json` at repo root, `schemaVersion: 1`, unique namespaced id
      (`io.github.<user>.<name>`), `license` field present, version never
      regresses between commits, id never changes after validation.
- [ ] Root `README.md` with install (`omarchy plugin add <url> --enable`) and
      removal (`omarchy plugin remove <id>`) commands, every external dependency
      named with its package source, and every capability disclosed (captures
      the screen, reads clipboard, contacts which hosts, runs which binaries).
- [ ] Root `LICENSE`; upstream copyright and license notices preserved for any
      vendored or cloned code. `clonedFrom` does not waive anything.
- [ ] **No `AGENTS.md`, `CLAUDE.md`, `.cursorrules` or similar in the installed
      tree** (blocked ~17 plugins). Move contributor notes to
      `docs/DEVELOPMENT.md`. Same for `__pycache__`, `.scratch`, capture corpora,
      multi-megabyte GIFs, leaked `</invoke>` tool markup in generated files.
- [ ] `preview.png` at root, author-produced.
- [ ] Every README claim is true of the code: "no network" (an `Image.source`
      with an `https://` URL breaks it), "no external dependencies", "no sudo",
      "never sees credentials", "rollback on failure". The reviewer diffs claims
      against code and blocks on the mismatch (~30 plugins).
- [ ] Wording the baseline scanner will not misread: say "No sudo or pkexec is
      required" (negated form is whitelisted); do not print a package-manager
      command (`omarchy pkg add x`, `pacman -S x`) in the README unless you want
      the `package-manager` capability and a mandatory human review; say where
      the package lives instead.
- [ ] Ask for `manual-setup` yourself if the plugin needs any package, binding
      edit, daemon, credential, device group or build step to function.
- [ ] No README "clone a branch and run install.sh". No self-updater. No
      `git pull` from inside the installed plugin. If something must be fetched,
      pin a full 40-character commit and check it out detached.
- [ ] CI actions pinned to full commit SHAs with `permissions: contents: read`;
      containers pinned by digest. Bundled binaries need a reproducible build or
      attestation tying bytes to the reviewed commit, or ship source only.

## 2. Every process the plugin spawns

The largest finding family by far (~150 plugins on output bounds, ~140 on
deadlines and teardown). The reviewer's accepted shape for a helper is:

```
/usr/bin/env -i <explicit minimal env> \
  /usr/bin/timeout --kill-after=2 <seconds> \
  /bin/bash -c '<fixed script>' name <args...>
```

with the script piping its producer through `/usr/bin/head -c <cap+1>` and
reporting overflow out of band (exit status), and with a supervisor that owns
the process group to a verified end. Concretely:

- [ ] **Fixed absolute executables**, never PATH lookup: `/usr/bin/hyprctl`,
      `/usr/bin/curl`, `/bin/bash`, `/usr/bin/python3 -I`. This includes the
      tools inside your own scripts (`jq`, `head`, `stat`, `date`) and the
      shebang (`#!/usr/bin/env bash` is a PATH lookup). `bar.run("cmd")` is a
      login shell over PATH; avoid it for anything security-relevant.
- [ ] **Cleared environment** (`clearEnvironment: true` or `env -i`) rebuilt from
      an explicit allowlist. Named attack channels: `BASH_ENV`, `ENV`,
      `LD_PRELOAD`, `LD_LIBRARY_PATH`, `PYTHONPATH`, `PERL5OPT`, `GIT_DIR`,
      `MAGICK_*`. `bash -lc` is rejected outright.
- [ ] **No shell strings built from data.** Pass data as separate argv entries
      or over stdin. Where a nested grammar is unavoidable (Lua for
      `hyprctl eval`, nmcli, sudoers, systemd units, SSH, Pango, awk regex,
      Bash arithmetic) encode at that boundary with a proper escaper and
      test emoji, digits after escapes, lone surrogates and newlines.
- [ ] **Byte cap at the producer**, not the consumer. `StdioCollector`,
      `SplitParser`, `capture_output=True`, `communicate()`, `$(...)`,
      `FileView.text()` all allocate before you can check. Use `head -c cap+1`
      (or a bounded reader) in front, read `cap+1`, and **treat overflow as
      failure**, never as a truncated success. Byte caps compare bytes; a JS
      `String.length` is UTF-16 units and does not count.
- [ ] **One absolute deadline for the whole operation**, including DNS, connect,
      body, and every sub-process. `curl --max-time` bounds curl only;
      `timeout` without `--kill-after` lets a TERM-ignoring child survive;
      per-call timeouts inside a loop are not a deadline.
- [ ] **Process-group teardown with proof.** `running = false` and
      `Process.signal(15)` reach the direct child only. The accepted pattern:
      leader in its own group (GNU `timeout` does this), TERM to the group,
      KILL after a grace, sweep survivors, and only then report exit. Never
      signal a bare PID/PGID later from a timer: PIDs are reused. Bind any
      signal to identity (`/proc/<pid>/stat` start time, `pgrp == leader`, or a
      pidfd) and refuse on mismatch. Do not reap the leader before the group
      is confirmed empty.
- [ ] **`Component.onDestruction` cancels every process the component ever
      started**, including readers, long-lived pickers and the teardown worker
      itself, and cleanup must still complete after the QML owner is gone.
- [ ] **Generation binding**: a result is applied only if it belongs to the
      request that is still current; superseded runs are cancelled and reaped;
      one in-flight run per target (`if (proc.running) return` at every start
      site, or a queue).
- [ ] Detached launches (`execDetached`) only for GUI apps the user asked for,
      never for anything whose failure or lifetime matters.
- [ ] Bounded restart policy for anything that respawns; no fixed 20 ms polling
      loops; no fail-open where a failed helper reads as "healthy" or "clean".
- [ ] Privileged helpers (`pkexec`, `sudo`): never execute a file from the
      user-writable plugin checkout as root, never pass a program text or a
      caller-controlled path across the boundary, revalidate the target
      identity on the privileged side right before acting, and treat sudoers
      subjects as `#uid`, with `NOSETENV`. This category never gets downgraded
      and has kept plugins blocked through ten rounds.

## 3. Everything the plugin reads or writes on disk

Second largest family (~180 plugins). The reviewer's phrase is
"check-then-use pathname": any `[ -f ]`, `[ ! -L ]`, `realpath`, `stat`,
`os.path.exists` followed by a separate open of the same path.

- [ ] **Open first, validate the descriptor.** `O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC`,
      then `fstat`: regular file, owned by the user or root, link count 1,
      no group/world write, size under the cap. Read from that descriptor.
      In bash: `exec 3< "$p"` then `stat -L /proc/self/fd/3` and
      `readlink /proc/self/fd/3` compared to the physical path. `O_NONBLOCK`
      matters: a planted FIFO blocks the shell forever otherwise.
- [ ] **Ancestors too.** `O_NOFOLLOW` covers the leaf only; `mkdir -p` and
      `os.makedirs` follow symlinked parents. Walk from a trusted root with
      held directory descriptors (`openat(O_DIRECTORY|O_NOFOLLOW)`) or fail
      closed when the directory does not already exist.
- [ ] **Writes are exclusive, private and atomic**: random name in the same
      directory, `O_CREAT|O_EXCL|O_NOFOLLOW` mode 0600, full write loop,
      `fsync` the file, `renameat` relative to the held directory, `fsync` the
      directory. No `$file.tmp.$$`, no `> path` redirection onto a path that
      might be a symlink, no `chmod` after publication, no `ln -sfn` as
      "atomic".
- [ ] `FileView` is a watcher only; never call `.text()` on a file whose size and
      type you have not bounded through a helper first.
- [ ] Runtime state under `$XDG_RUNTIME_DIR/<plugin>` (0700) or
      `~/.local/state/<plugin>`, never `/tmp`, never a `/tmp` fallback.
- [ ] Deletion and cleanup by identity, not by name or glob: quarantine-rename
      through the held directory fd, verify inode, then unlink. Never
      `rm -rf` a path selected by a mutable name, never delete files you did
      not create (tracked by digest or exact list).
- [ ] Shared files you edit (`shell.json`, `bindings.lua`, `omarchy-menu.jsonc`,
      third-party app configs): compare-and-swap against the identity you read,
      exactly one ordered marker block validated before replacement, backup
      and byte-exact rollback (including mode) on any later failure, and
      restore the user's actual prior values, not stock defaults. Prefer the
      shell's own APIs (`updateEntryInline`, plugin registration) over editing
      the file.
- [ ] No mutation on load or enable. Any write to user configuration, any
      service enablement, any package install is an explicit, labelled,
      in-product action with visible scope and a reported result.
- [ ] Enumeration is bounded at the producer: no `sorted(listdir())[:N]`,
      no `find | sort | head`; stop scanning at the cap and fail closed.
- [ ] Executing data: never `dofile`/`source`/`eval` a user-writable file;
      parse it as data. `bash (( ))` on a file-derived field executes code.

## 4. Everything that crosses into QML

- [ ] **`textFormat: Text.PlainText` on every `Text` bound to non-constant
      content** (~120 plugins): window titles, workspace names, MPRIS metadata,
      SSIDs, device names, helper stderr, file names, settings, error strings,
      tooltips, accessibility text. Length-capping is not a substitute; the
      default `AutoText` renders markup and can load resources.
- [ ] Bound everything at ingress before it enters a model: item count,
      string length, nesting depth, numeric range (finite, clamped), closed
      schema. Sort after capping, not before. Reject the whole payload on any
      violation.
- [ ] Settings from `shell.json` and IPC arguments are untrusted input:
      re-enforce the manifest ranges in code, allowlist enum values, and
      check object keys against `__proto__`/`constructor`/`prototype` or use
      null-prototype maps. Use `hasOwnProperty` for id lookups.
- [ ] Ids that become paths (`Qt.resolvedUrl("x/" + id)`, plugin ids, entry
      points) are matched against the plugin-id grammar
      `^[A-Za-z0-9][A-Za-z0-9._-]*$`, no `..`, no leading `/`, resolved path
      checked to stay inside the plugin directory.
- [ ] Images: `Image.source` only from `image://` providers, `data:` URLs, or
      local regular files you validated; `sourceSize` set; no remote URLs
      straight from MPRIS or an API (redirects, SSRF to loopback, decode
      bombs). If remote artwork must exist, fetch through a bounded helper
      with a host allowlist into a verified private file.
- [ ] Repeater counts are capped independently of screen size and of input.
- [ ] Public IPC (`IpcHandler`) exposes nothing that writes to caller-supplied
      paths, launches apps, spends money or logs in; numeric and string
      arguments are clamped; no combo-wide or compositor-global side effects
      the plugin cannot prove it owns.

## 5. Network

- [ ] `curl -q` (or `--disable`) as the first option so `~/.curlrc` is ignored;
      `--proto =https`; `--max-time` plus an outer `timeout`; `--max-filesize`
      plus a producer `head -c cap+1`; no `-L` unless redirects are restricted
      to the same HTTPS origin; `--` before the URL; `--data-raw`, never
      `-d @`.
- [ ] Exact scheme/host/port allowlist parsed with a real URL parser (no
      `startsWith("https://")`, no substring host matching); reject userinfo,
      control characters and private/loopback/link-local destinations, and
      pin the resolved address through the connection (DNS rebinding).
- [ ] Secrets never in argv, URLs, logs, notifications or world-readable
      state; stdin or a private descriptor only; keyring for storage with a
      fail-closed path when it is unavailable; clear secret-bearing
      collectors and properties on every exit path.
- [ ] Any listener the plugin runs: loopback only, authenticated (capability
      token or `SO_PEERCRED`), bounded clients and message sizes, TLS on
      anything non-loopback.
- [ ] Location and telemetry lookups are opt-in and disclosed.

## 6. Compositor interaction (Hyprland Lua fork)

- [ ] Data going into `hyprctl eval` is encoded as inert Lua string literals
      at the Lua boundary; workspace/monitor/window names are not trusted.
- [ ] Rebinding keys: take a chord over only while it carries exactly the
      stock bind, record the bind identity from `hyprctl -j binds`
      (`dispatcher: "__lua"`, unique `arg`), and hand it back only while the
      chord still carries exactly that bind. Never use `HL.Keybind` handles
      after anything else may have unbound the combo: it segfaults the
      compositor.
- [ ] Workspace rules accumulate; reuse rules by handle instead of declaring
      new ones per action, and disable on release.
- [ ] Any window or state the plugin adopts carries an ownership marker
      (window tag) set by this plugin; undo restores the recorded prior state,
      not a default.
- [ ] Global input capture (`/dev/input`, `input` group) is a declared,
      opt-in capability, never a side effect.

## 7. Before you open the issue

- [ ] `omarchy plugin validate .` passes on a fresh clone.
- [ ] Grep the tree for `bash -lc`, `execDetached`, `StdioCollector`,
      `FileView`, `Text {` without `textFormat`, bare command names in
      `command: [`, `/tmp`, `.tmp.$$`, `mkdir -p`, `sudo`, `pkexec`, `curl`,
      `Image.source`, `JSON.parse`, `dofile`, `__proto__`, `AGENTS.md`,
      `CLAUDE.md`, and justify each hit against the sections above.
- [ ] Run the adversarial cases on a live shell and put the measurements in
      the submission notes: close the UI mid-helper and count survivors,
      plant a symlink and a FIFO where the plugin reads, feed 10 MB to every
      collector, rename the target between check and use, ignore TERM in a
      helper and time the KILL.
- [ ] Submission body: category, one to three tags, all five checklist boxes,
      and maintainer notes that pre-empt the review: what is captured, what
      is spawned (fixed paths), what is written where (and how it is torn
      down), what is contacted, and that no sudo or pkexec is required.
