-- Negotiate fullscreen HDR from the SDR desktop without swapping display profiles.
-- HDMI timings, routing and recovery belong to the local display coordinator.
hl.config({ render = { cm_auto_hdr = 1 }, quirks = { prefer_hdr = 2 } })

-- Big Picture otherwise inherits Steam's floating-window placement, which can
-- be outside the visible output after a desk/TV transition. Let the compositor
-- place it fullscreen on its workspace's current monitor.
hl.window_rule({
    match = { class = "^steam$", title = "^Steam Big Picture Mode$" },
    fullscreen = true,
})
