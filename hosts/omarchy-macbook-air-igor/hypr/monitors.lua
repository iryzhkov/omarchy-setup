-- MacBook Air (Asahi), internal panel.
--
-- Omarchy sets these via `local` variables near the top of monitors.lua, which
-- a block appended at the bottom cannot reassign -- so re-call the setters
-- instead. hl.monitor() and hl.env() are last-wins.

hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1.33333 })

-- GTK only honours whole numbers; keep XWayland windows unscaled and crisp.
hl.env("GDK_SCALE", "1")
