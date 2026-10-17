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

// Guard failures contain Huyang, never the model request or shared execute tool.
function containHuyang(editor, state) {
  for (const [name, config] of editor.list()) {
    const ns = namespace(name);
    if (!state.namespaces.has(ns) && !isHuyang(config)) continue;
    state.namespaces.add(ns);
    if (name === "huyang" && isHuyang(config)) {
      editor.remove(name);
    } else {
      // Keep colliding/aliased entries and all their settings. Only their runtime
      // Huyang exposure is disabled; never delete somebody else's connection.
      editor.set(name, { ...structuredClone(config), disabled: true, codemode: false });
    }
  }
}

// Only deletes Huyang request entries. Surviving SDK objects retain their identity.
export function filterRequest(event, registry, state) {
  let blocked = Boolean(state.error || state.duplicates.size)
    || typeof event.model?.providerID !== "string";
  const known = new Map();
  const byID = new Map(registry.map((tool) => [tool.id, tool]));
  for (const tool of registry) {
    const ns = tool.options?.namespace;
    if (!state.namespaces.has(ns)) continue;
    known.set(tool.id, ns);
    if (!SERVERS.includes(ns) || tool.options.codemode !== false || tool.id !== effectiveName(tool)) {
      blocked = true;
    }
  }
  const selected = event.model?.providerID === "ollama" ? "huyang_lean" : "huyang_full";
  for (const name of Object.keys(event.tools)) {
    const server = known.get(name);
    if (!server) {
      // Preserve registered unrelated namespaces even when their text prefix matches.
      if (!byID.has(name) && [...state.namespaces].some((id) => id !== "huyang" && name.startsWith(id + "_"))) {
        delete event.tools[name];
      }
      continue;
    }
    if (blocked || server !== selected) delete event.tools[name];
  }
  // Missing/permission-filtered selected tools stay absent; never restore the other profile.
}

/** @satisfies {import("@opencode/plugin").Plugin.Plugin} */
export default {
  id: "fleet.huyang-profiles",
  async setup(ctx) {
    const state = { error: ctx.app.version === "2.0.30" ? "" : "requires OpenCode 2.0.30",
      duplicates: new Set(), namespaces: new Set(["huyang", ...SERVERS]) };
    const registrations = [];
    const hook = async (event) => {
      let registry;
      try {
        registry = await ctx.tool.list();
      } catch {
        // Registry failure also withholds only Huyang; normal chat must keep working.
        registry = [];
      }
      filterRequest(event, registry, state);
    };
    // Validation failures must not disable the plugin group or fail unrelated requests.
    registrations.push(await ctx.session.hook("context", hook));
    registrations.push(await ctx.session.hook("compaction", hook));
    registrations.push(await ctx.session.hook("generate", hook));
    registrations.push(await ctx.mcp.transform((editor) => {
      if (state.error || state.duplicates.size) {
        containHuyang(editor, state);
        return;
      }
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
        containHuyang(editor, state);
        return;
      }
      // Latch containment of duplicate Huyang connections until owner cleanup/reload.
      state.duplicates = new Set([...state.duplicates, ...duplicates]);
      if (state.duplicates.size) {
        containHuyang(editor, state);
        return;
      }
      editor.remove("huyang");
      editor.set("huyang_lean", lean);
      editor.set("huyang_full", full);
    }));
    return async () => {
      for (const registration of registrations.reverse()) await registration.dispose();
    };
  },
};
