-- Personal keybindings, layered on top of Omarchy's defaults.
--
-- Rebinding a default takes hl.unbind first, then o.bind: Omarchy's own
-- binding for the key is already registered by the time this file loads.
-- See the current set with `omarchy menu keybindings --print`.
--
-- Everything here is behaviour, not appearance -- theme, scale and bar layout
-- are machine-specific and stay out of this repo (see README, Non-goals).

-- Music: SUPER+SHIFT+M defaults to { omarchy = "spotify" }, which runs
-- omarchy-launch-spotify. That is a dead end on aarch64 -- Spotify ships no
-- ARM64 Linux build, so omarchy-pkg-add silently skips it. Point the key at
-- spotify-player instead; `focus = true` re-focuses the window if it's open.
hl.unbind("SUPER + SHIFT + M")
o.bind("SUPER + SHIFT + M", "Music", { tui = "spotify_player", focus = true })

-- Passwords: SUPER+SHIFT+SLASH defaults to { omarchy = "1password" }. Use
-- Bitwarden instead -- the vault here is bitwarden-cli (`bw`), surfaced by the
-- qs-bitwarden-cli bar plugin (config/plugins.txt), so this toggles that panel
-- via its IPC handler rather than launching a desktop app.
hl.unbind("SUPER + SHIFT + SLASH")
o.bind("SUPER + SHIFT + SLASH", "Passwords", "omarchy-shell io.github.elevate08.qs-bitwarden-cli toggle")

-- Email: SUPER+SHIFT+E defaults to { webapp = "https://app.hey.com" } and
-- SUPER+SHIFT+ALT+E to HEY's compose URL. Use Omamail (config/plugins.txt)
-- instead -- it runs inside the omarchy-shell process rather than as a browser
-- webapp. The IPC target is `shell`, not the plugin id: the window is summoned
-- by the shell, which is what loads the plugin in the first place (see the
-- omamail README). Payload `{"compose":true}` opens an empty draft.
hl.unbind("SUPER + SHIFT + E")
o.bind("SUPER + SHIFT + E", "Email", [[omarchy shell shell toggle omamail '{}']])

hl.unbind("SUPER + SHIFT + ALT + E")
o.bind("SUPER + SHIFT + ALT + E", "New email", [[omarchy shell shell toggle omamail '{"compose":true}']])

-- Select all: SUPER+A sends CTRL+A to the focused surface, mirroring the
-- universal copy/paste/cut keys in default/hypr/bindings/clipboard.lua.
-- The window target is omitted so it reaches layer-shell panels too, and the
-- down/up split works around Hyprland leaving synthetic key state stuck.
-- https://github.com/hyprwm/Hyprland/discussions/14099
o.bind("SUPER + A", "Universal select all", function()
  hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "A", state = "down" }))

  hl.timer(function()
    hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = "A", state = "up" }))
  end, { timeout = 50, type = "oneshot" })
end)

-- Workspace layout: SUPER+L defaults to omarchy-hyprland-workspace-layout-toggle,
-- which only flip-flops dwindle <-> scrolling and can never reach master. Cycle
-- through all three instead. The script is installed from config/bin by
-- modules/client/28-scripts.sh; the path is spelled out because Hyprland's
-- exec PATH is not guaranteed to include ~/.local/bin.
hl.unbind("SUPER + L")
o.bind("SUPER + L", "Cycle workspace layout", os.getenv("HOME") .. "/.local/bin/omarchy-workspace-layout-cycle")


-- Force close: SUPER+W asks nicely (close_window); a hung client ignores it.
-- SUPER+ALT+W kills the client outright.
o.bind("SUPER + ALT + W", "Force close window", hl.dsp.window.kill())
