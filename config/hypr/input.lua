-- Click to focus, rather than focus following the pointer.
--
-- Omarchy defaults to follow_mouse = 1, where focus tracks the cursor. Two
-- separate settings are needed to actually get click-to-focus, because they
-- govern different things:
--
--   input.follow_mouse = 0            the window under the cursor is not
--                                     focused until it is clicked
--   misc.mouse_move_focuses_monitor   still applies when follow_mouse is 0:
--     = false                         without it, moving the pointer onto
--                                     another display focuses that display
--
-- The monitor half matters beyond preference: Hyprland opens new windows on
-- the focused monitor, so with the default a stray pointer decides where an
-- app launches, which is disruptive on a multi-monitor desk.
hl.config({
  input = {
    follow_mouse = 0,
  },

  misc = {
    mouse_move_focuses_monitor = false,
  },
})
