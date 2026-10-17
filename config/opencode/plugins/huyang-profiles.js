// fleet-managed: huyang-profiles/v1
// Source: omarchy-setup/config/opencode/plugins/huyang-profiles.js
// OpenCode 2.0.30 V2 server plugin; see docs/opencode-huyang-profiles.md.
import { homedir } from "node:os";
import { basename, join } from "node:path";
import { isDeepStrictEqual } from "node:util";

const SERVERS = ["huyang_lean", "huyang_full"];
const normalize = (value) => value.replace(/[^a-zA-Z0-9_-]/g, "_");
const namespace = (server) => normalize(server);
const effectiveName = (tool) => tool.options?.namespace === undefined
  ? normalize(tool.name)
  : tool.options.namespace.replaceAll(".", "_") + "_" + normalize(tool.name);

function profileConfig(source, profile) {
  if (source?.type !== "local" || !Array.isArray(source.command)
      || source.command.some((arg) => typeof arg !== "string")
      || basename(source.command[0] ?? "") !== "huyang" || source.command[1] !== "mcp") {
    throw new Error("managed huyang must use a local Huyang executable and mcp command");
  }
  const args = [];
  let profiles = 0;
  for (let i = 2; i < source.command.length; i++) {
    const arg = source.command[i];
    if (arg === "--") throw new Error("managed huyang command has an unsupported argument separator");
    if (arg === "--profile" || arg.startsWith("--profile=")) {
      const value = arg === "--profile" ? source.command[++i] : arg.slice("--profile=".length);
      if (++profiles > 1 || !["lean", "full", "edit"].includes(value)) {
        throw new Error("managed huyang has an unsupported profile");
      }
    } else {
      args.push(arg);
    }
  }
  return { ...structuredClone(source),
    command: [source.command[0], "mcp", ...args, "--profile", profile], codemode: false };
}

function isHuyang(config) {
  return config?.type === "local" && Array.isArray(config.command)
    && basename(config.command[0] ?? "") === "huyang" && config.command[1] === "mcp";
}

// Only deletes request entries. Surviving SDK definition objects keep their identity.
// Registry metadata proves the namespace and direct exposure; names alone are insufficient.
export function filterRequest(event, registry, state) {
  if (state.error) throw new Error("Huyang profile guard: " + state.error);
  if (state.duplicates.size) {
    throw new Error("Huyang profile guard: duplicate Huyang registration; request refused");
  }
  if (typeof event.model?.providerID !== "string") {
    throw new Error("Huyang profile guard: resolved providerID is missing");
  }
  const known = new Map();
  const byID = new Map(registry.map((tool) => [tool.id, tool]));
  for (const tool of registry) {
    const ns = tool.options?.namespace;
    if (state.duplicates.has(ns) || ns === "huyang") {
      throw new Error("Huyang profile guard: duplicate Huyang registration; request refused");
    }
    if (!SERVERS.includes(ns)) continue;
    if (tool.options.codemode !== false || tool.id !== effectiveName(tool)) {
      throw new Error("Huyang profile guard: managed tool identity or direct exposure changed");
    }
    known.set(tool.id, ns);
  }
  const selected = event.model.providerID === "ollama" ? "huyang_lean" : "huyang_full";
  for (const name of Object.keys(event.tools)) {
    const server = known.get(name);
    if (!server) {
      // A different registered namespace may share a text prefix. Preserve it.
      if (!byID.has(name) && SERVERS.some((id) => name.startsWith(id + "_"))) {
        throw new Error("Huyang profile guard: stale or unknown managed tool");
      }
      continue;
    }
    if (server !== selected) delete event.tools[name];
  }
  // A missing/permission-filtered selected catalog stays absent; never restore the other one.
}

/** @satisfies {import("@opencode/plugin").Plugin.Plugin} */
export default {
  id: "fleet.huyang-profiles",
  async setup(ctx) {
    const state = { error: ctx.app.version === "2.0.30" ? "" : "requires OpenCode 2.0.30",
      duplicates: new Set() };
    const registrations = [];
    const hook = async (event) => filterRequest(event, await ctx.tool.list(), state);
    // Keep a refusing request hook even on a configuration conflict. Throwing from a
    // transform disables its entire plugin group in V2 and would remove the guard.
    registrations.push(await ctx.session.hook("context", hook));
    registrations.push(await ctx.session.hook("compaction", hook));
    registrations.push(await ctx.session.hook("generate", hook));
    if (!state.error) {
      registrations.push(await ctx.mcp.transform((editor) => {
        let lean, full;
        const duplicates = new Set();
        try {
          const source = editor.get("huyang") ?? {
            type: "local", command: [join(homedir(), ".local/share/huyang/bin/huyang"), "mcp"],
          };
          lean = profileConfig(source, "lean");
          full = profileConfig(source, "full");
          for (const [name, config] of editor.list()) {
            if (name === "huyang") continue;
            if (SERVERS.includes(name)) {
              const expected = name === "huyang_lean" ? lean : full;
              if (!isDeepStrictEqual(structuredClone(config), expected)) {
                throw new Error("reserved Huyang connection conflicts with managed configuration");
              }
            } else if (SERVERS.includes(namespace(name))) {
              throw new Error("MCP namespace collides with a managed Huyang connection");
            } else if (isHuyang(config)) {
              duplicates.add(namespace(name));
            }
          }
        } catch (error) {
          // All messages above are fixed text; never include command/environment values.
          state.error ||= error instanceof Error ? error.message : "invalid managed configuration";
          state.duplicates = new Set([...state.duplicates, ...duplicates]);
          return;
        }
        // Latch conflicts/aliases until reload: an older in-flight snapshot may
        // still contain their Code Mode inventory after the live registry changes.
        state.duplicates = new Set([...state.duplicates, ...duplicates]);
        editor.remove("huyang");
        editor.set("huyang_lean", lean);
        editor.set("huyang_full", full);
      }));
    }
    return async () => {
      for (const registration of registrations.reverse()) await registration.dispose();
    };
  },
};
