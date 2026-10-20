-- Negotiate fullscreen HDR from the SDR desktop without swapping display profiles.
-- HDMI timings, routing and recovery belong to the local display coordinator.
hl.config({ render = { cm_auto_hdr = 1 }, quirks = { prefer_hdr = 2 } })
