-- Rebuild a node.software-dsp filter chain that has torn itself down.
--
-- WirePlumber's stock node/software-dsp.lua loads libpipewire-module-filter-chain
-- when a node matching a node.software-dsp rule appears, and unloads it when
-- that parent node goes away. It never looks at the filter again. But
-- module-filter-chain destroys itself whenever either of its streams reaches
-- PW_STREAM_STATE_UNCONNECTED (module-filter-chain.c, capture_state_changed /
-- playback_state_changed). With node.dont-fallback = true on the capture side,
-- one failed link activation -- "2 of 2 PipeWire links failed to activate",
-- "some node was destroyed before the link was created" -- is enough. The
-- parent ALSA node is still there, so nothing ever recreates the filter, and
-- the machine is left with no microphone until WirePlumber is restarted.
--
-- This script watches for the filter's capture node disappearing while its
-- parent still exists, and reloads the module from the same filter-path after
-- a short delay, with exponential backoff if it keeps failing.
--
-- Implementation notes:
--  * Uses an ObjectManager rather than node-added/node-removed hooks so that
--    nodes which already exist when this script loads (the HPAI mic card is
--    enumerated early) are tracked too.
--  * `node.id` in Lua is WirePlumber's own proxy id, not the daemon's global
--    id; `bound-id` is the global id but reads as SPA_ID_INVALID once the
--    node is removed. Tables are keyed by node.id; the global id is kept
--    separately for the existence check.

log = Log.open_topic ("s-node-dsp-rebuild")

local rules = Conf.get_section_as_json ("node.software-dsp.rules", Json.Array {})

local BASE_DELAY_MS = 1500
local MAX_DELAY_MS = 30000

-- parent node.id -> { path, capture_name, global_id, module, attempts, timer, capture_id }
local tracked = {}
-- filter capture node.name -> parent node.id
local by_capture_name = {}
-- filter capture node.id -> parent node.id
local by_capture_id = {}

nodes_om = ObjectManager {
  Interest { type = "node" },
}

local function load_graph (path)
  local conf = Conf (path, {
    ["as-section"] = "node.software-dsp.graph",
    ["no-fragments"] = true,
  })
  if conf:open () then
    return nil, nil
  end
  local json = conf:get_section_as_json ("node.software-dsp.graph")
  local graph = json:parse ()
  local cap = graph and graph["capture.props"] and graph["capture.props"]["node.name"]
  return json:to_string (), cap
end

local function node_exists (key, value)
  return nodes_om:lookup { Constraint { key, "=", value } } ~= nil
end

local function schedule_rebuild (parent_id)
  local t = tracked[parent_id]
  if not t or t.timer then
    return
  end
  local delay = math.min (BASE_DELAY_MS * (2 ^ t.attempts), MAX_DELAY_MS)
  log:notice (string.format ("filter %s vanished while its parent (global id %s) remains; rebuilding in %d ms (attempt %d)",
      t.capture_name, t.global_id, delay, t.attempts + 1))
  t.timer = Core.timeout_add (delay, function ()
    t.timer = nil
    if not tracked[parent_id] then
      return false
    end
    if not node_exists ("object.id", t.global_id) then
      log:info ("parent " .. t.global_id .. " is gone; not rebuilding " .. t.capture_name)
      return false
    end
    if node_exists ("node.name", t.capture_name) then
      log:info (t.capture_name .. " already exists again; nothing to do")
      return false
    end
    local args = load_graph (t.path)
    if not args then
      log:warning ("cannot read filter graph " .. t.path)
      return false
    end
    t.attempts = t.attempts + 1
    t.module = nil
    t.module = LocalModule ("libpipewire-module-filter-chain", args, {})
    log:notice ("reloaded filter chain " .. t.capture_name .. " for parent " .. t.global_id)
    return false
  end)
end

local function on_node_added (node)
  local props = node.properties
  local name = props["node.name"]
  local id = node.id

  -- A filter capture node appearing (or reappearing after a rebuild).
  local pid = by_capture_name[name]
  if pid and tracked[pid] then
    local t = tracked[pid]
    if t.capture_id then
      by_capture_id[t.capture_id] = nil
    end
    t.capture_id = id
    by_capture_id[id] = pid
    t.attempts = 0
    log:info ("filter " .. name .. " is up (global id " .. tostring (props["object.id"]) .. ")")
    return
  end

  JsonUtils.match_rules (rules, props, function (action, value)
    if action ~= "create-filter" then
      return
    end
    local fprops = value:parse (1)
    if not fprops["filter-path"] then
      return
    end
    local _, cap = load_graph (fprops["filter-path"])
    if not cap then
      log:warning ("no capture.props node.name in " .. fprops["filter-path"] .. "; cannot track it")
      return
    end
    tracked[id] = {
      path = fprops["filter-path"],
      capture_name = cap,
      global_id = tostring (props["object.id"]),
      attempts = 0,
    }
    by_capture_name[cap] = id
    log:info ("tracking filter " .. cap .. " on parent " .. name .. " (global id " .. tostring (props["object.id"]) .. ")")
  end)
end

local function on_node_removed (node)
  local id = node.id

  local t = tracked[id]
  if t then
    -- The parent itself went away: the stock script frees its module and
    -- will create a fresh one if the parent comes back. Drop ours too.
    if t.timer then
      t.timer:destroy ()
    end
    if t.capture_id then
      by_capture_id[t.capture_id] = nil
    end
    by_capture_name[t.capture_name] = nil
    tracked[id] = nil
    return
  end

  local pid = by_capture_id[id]
  if pid then
    by_capture_id[id] = nil
    if tracked[pid] then
      tracked[pid].capture_id = nil
    end
    schedule_rebuild (pid)
  end
end

nodes_om:connect ("installed", function (om)
  -- Parents first, so their filter nodes are recognised on the second pass.
  for node in om:iterate () do
    on_node_added (node)
  end
  for node in om:iterate () do
    local name = node.properties["node.name"]
    if by_capture_name[name] and not tracked[by_capture_name[name]].capture_id then
      on_node_added (node)
    end
  end
end)

nodes_om:connect ("object-added", function (_, node)
  on_node_added (node)
end)

nodes_om:connect ("object-removed", function (_, node)
  on_node_removed (node)
end)

nodes_om:activate ()
