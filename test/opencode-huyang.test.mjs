import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";
import test from "node:test";

const sourcePath = process.env.HUYANG_PLUGIN_SOURCE
  ?? fileURLToPath(new URL("../config/opencode/plugins/huyang-profiles.js", import.meta.url));
const source = await readFile(sourcePath, "utf8");
const { default: plugin } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const clone = (value) => structuredClone(value);
const legacy = { type: "local",
  command: ["/review/tools/huyang", "mcp", "--reply-style", "plain-v1", "--profile", "edit"],
  cwd: "/review/project", environment: { HUYANG_SOCKET: "fixture-only", TOKEN: "DO-NOT-LOG" },
  timeout: { startup: 1000 }, protocol: "legacy" };
const foreign = { type: "remote", url: "https://example.invalid/mcp" };

async function fixture(initial = { huyang: legacy, unrelated: foreign }, version = "2.0.30") {
  const base = new Map(Object.entries(clone(initial)));
  const hooks = new Map();
  const transforms = [];
  let configured = new Map();
  let registry = [];
  let transformsRun = 0;
  const dispose = () => ({ dispose: async () => {} });
  function replay() {
    configured = new Map([...base].map(([key, value]) => [key, clone(value)]));
    for (const transform of transforms) {
      transformsRun++;
      transform({
        get: (key) => configured.get(key), list: () => [...configured],
        set: (key, value) => configured.set(key, clone(value)),
        remove: (key) => configured.delete(key),
      });
    }
    registry = [...configured].flatMap(([server, config]) => {
      if (config.disabled) return [];
      return ["read", "edit_apply"].map((name) => ({
        id: server.replace(/[^a-zA-Z0-9_-]/g, "_") + "_" + name, name,
        description: name, input: { type: "object" },
        options: { namespace: server.replace(/[^a-zA-Z0-9_-]/g, "_"), codemode: config.codemode ?? true },
      }));
    });
  }
  const ctx = {
    app: { version },
    session: { hook: async (kind, callback) => { hooks.set(kind, callback); return dispose(); } },
    tool: { list: async () => { await Promise.resolve(); return registry; } },
    mcp: { transform: async (callback) => { transforms.push(callback); replay(); return dispose(); } },
  };
  replay();
  const cleanup = await plugin.setup(ctx);
  function request(providerID, kind = "context", sessionID = "same-session", catalog) {
    const tools = catalog ?? Object.fromEntries(registry.filter((tool) => tool.options.codemode === false)
      .map((tool) => [tool.id, Object.freeze({ description: tool.description, input: tool.input })]));
    tools.execute ??= Object.freeze({ description: "unrelated code mode", input: {} });
    tools.huyang_fullish_read = Object.freeze({ description: "unrelated lookalike", input: {} });
    return { sessionID, model: { providerID, modelID: "same-model-name" }, tools, kind };
  }
  return {
    hooks, cleanup, request,
    run: async (event) => { await hooks.get(event.kind)(event); return event; },
    inject: (name, config) => { base.set(name, clone(config)); replay(); },
    configured: () => configured,
    registry: () => registry,
    setRegistry: (next) => { registry = next; },
    transformsRun: () => transformsRun,
  };
}

test("V2 plugin identity, path policy and narrow MCP replacement", async () => {
  const f = await fixture();
  assert.equal(plugin.id, "fleet.huyang-profiles");
  assert.deepEqual([...f.hooks.keys()], ["context", "compaction", "generate"]);
  const connections = f.configured();
  assert.equal(connections.has("huyang"), false);
  assert.deepEqual(connections.get("unrelated"), foreign);
  for (const profile of ["lean", "full"]) {
    const config = connections.get("huyang_" + profile);
    assert.equal(config.codemode, false);
    assert.deepEqual(config.command, ["/review/tools/huyang", "mcp", "--reply-style", "plain-v1", "--profile", profile]);
    assert.deepEqual(config.environment, legacy.environment);
    assert.equal(config.cwd, legacy.cwd);
    assert.deepEqual(config.timeout, legacy.timeout);
  }
  const empty = await fixture({});
  assert.equal(empty.configured().get("huyang_full").command[0],
    homedir() + "/.local/share/huyang/bin/huyang");
  await f.cleanup();
});

for (const kind of ["context", "compaction", "generate"]) {
  test(kind + " uses each request's resolved model in both switch directions", async () => {
    const f = await fixture();
    for (const providers of [["ollama", "anthropic", "ollama"], ["openai", "ollama", "openai"]]) {
      for (const provider of providers) {
        const event = f.request(provider, kind);
        const selected = provider === "ollama" ? "lean" : "full";
        const original = event.tools["huyang_" + selected + "_read"];
        const unrelated = event.tools.execute;
        await f.run(event);
        assert.equal(event.tools["huyang_" + selected + "_read"], original);
        assert.equal(event.tools.execute, unrelated);
        assert.ok(event.tools.huyang_fullish_read);
        assert.equal(Object.keys(event.tools).filter((name) => name.startsWith("huyang_")
          && name !== "huyang_fullish_read").length, 2);
        assert.equal(event.tools["huyang_" + (selected === "lean" ? "full" : "lean") + "_read"], undefined);
      }
    }
    // No provider aliases or model-name/endpoint guesses.
    for (const provider of ["Ollama", "ollama-local"]) {
      const event = await f.run(f.request(provider, kind));
      assert.ok(event.tools.huyang_full_read);
      assert.equal(event.tools.huyang_lean_read, undefined);
    }
  });
}

test("simultaneous sessions do not mutate MCP, registry or definition objects", async () => {
  const f = await fixture();
  const before = clone([...f.configured()]);
  const runs = f.transformsRun();
  const left = f.request("ollama", "context", "left");
  const right = f.request("anthropic", "context", "right");
  const lean = left.tools.huyang_lean_read;
  const full = right.tools.huyang_full_read;
  await Promise.all([f.run(left), f.run(right)]);
  assert.equal(left.tools.huyang_lean_read, lean);
  assert.equal(right.tools.huyang_full_read, full);
  assert.equal(left.tools.huyang_full_read, undefined);
  assert.equal(right.tools.huyang_lean_read, undefined);
  assert.deepEqual([...f.configured()], before);
  assert.equal(f.transformsRun(), runs);
  assert.ok(f.registry().some((tool) => tool.id === "huyang_full_read"));
  assert.ok(f.registry().some((tool) => tool.id === "huyang_lean_read"));
});

test("unavailable or denied selected tools never fall back or break unrelated requests", async () => {
  for (const [provider, missing] of [["ollama", "huyang_lean"], ["openai", "huyang_full"]]) {
    for (const kind of ["context", "compaction", "generate"]) {
      const f = await fixture();
      f.setRegistry(f.registry().filter((tool) => tool.options.namespace !== missing));
      const event = f.request(provider, kind);
      const unrelated = event.tools.execute;
      const absent = await f.run(event);
      assert.equal(absent.tools.huyang_full_read, undefined);
      assert.equal(absent.tools.huyang_lean_read, undefined);
      assert.equal(absent.tools.execute, unrelated);
    }
  }
  const permitted = await fixture();
  const denied = permitted.request("ollama");
  delete denied.tools.huyang_lean_edit_apply;
  await permitted.run(denied);
  assert.equal(denied.tools.huyang_lean_edit_apply, undefined);
});

test("late ACP legacy registration is replaced, not duplicated", async () => {
  const f = await fixture();
  f.inject("huyang", { ...legacy, command: ["/review/tools/huyang", "mcp", "--profile", "full"] });
  assert.equal(f.configured().has("huyang"), false);
  assert.equal([...f.configured().keys()].filter((name) => name.startsWith("huyang")).length, 2);
  // ACP switchModel's resolved provider is the next context event; no agent selection.
  assert.ok((await f.run(f.request("ollama"))).tools.huyang_lean_read);
  assert.ok((await f.run(f.request("openai"))).tools.huyang_full_read);
});

test("unsupported version withholds only Huyang and preserves normal chat and unrelated tools", async () => {
  const direct = { type: "local", command: ["/review/other-server"], codemode: false };
  const f = await fixture({ huyang: legacy, unrelated: foreign, direct }, "2.0.31");
  assert.equal(f.configured().has("huyang"), false);
  assert.equal(f.configured().has("huyang_lean"), false);
  assert.equal(f.configured().has("huyang_full"), false);
  assert.deepEqual(f.configured().get("unrelated"), foreign);
  assert.deepEqual(f.configured().get("direct"), direct);
  const empty = await fixture({}, "2.0.31");
  assert.equal(empty.configured().size, 0);
  await empty.run({ kind: "context", model: { providerID: "openai" }, tools: {} });
  const runs = f.transformsRun();
  for (const kind of ["context", "compaction", "generate"]) {
    for (const provider of ["ollama", "openai"]) {
      const event = f.request(provider, kind);
      const directTool = event.tools.direct_read;
      assert.ok(directTool);
      const execute = event.tools.execute;
      // A stale direct catalog cannot restore Huyang after containment.
      event.tools.huyang_full_read = { description: "stale", input: {} };
      event.tools.huyang_lean_read = { description: "stale", input: {} };
      await f.run(event);
      assert.equal(event.tools.huyang_full_read, undefined);
      assert.equal(event.tools.huyang_lean_read, undefined);
      assert.equal(event.tools.direct_read, directTool);
      assert.equal(event.tools.execute, execute);
      const chat = { kind, model: { providerID: provider }, tools: {} };
      await f.run(chat);
      assert.deepEqual(chat.tools, {});
    }
  }
  assert.equal(f.transformsRun(), runs);
  f.inject("huyang", legacy);
  assert.equal(f.configured().has("huyang"), false);
  assert.ok((await f.run(f.request("ollama"))).tools.direct_read);

  // Do not delete another owner's reserved-name connection on a newer release.
  const collision = await fixture({ huyang_full: foreign, direct }, "2.0.31");
  assert.deepEqual(collision.configured().get("huyang_full"),
    { ...foreign, disabled: true, codemode: false });
  assert.equal(collision.configured().has("huyang_lean"), false);
  assert.ok((await collision.run(collision.request("openai"))).tools.direct_read);
});

test("ACP duplicate latch disables only Huyang and keeps connection records and chat", async () => {
  const f = await fixture();
  f.inject("acp_huyang", legacy);
  assert.deepEqual(f.configured().get("acp_huyang"),
    { ...legacy, disabled: true, codemode: false });
  assert.deepEqual(f.configured().get("unrelated"), foreign);
  assert.equal(f.configured().has("huyang"), false);
  for (const kind of ["context", "compaction", "generate"]) {
    const event = f.request("ollama", kind);
    const execute = event.tools.execute;
    await f.run(event);
    assert.equal(event.tools.execute, execute);
    assert.equal(event.tools.huyang_full_read, undefined);
    assert.equal(event.tools.huyang_lean_read, undefined);
    assert.equal(event.tools.acp_huyang_read, undefined);
  }
  f.inject("acp_huyang", { ...legacy, disabled: true });
  assert.ok((await f.run(f.request("openai"))).tools.execute);
});

test("conflicts contain reserved Huyang exposure without deleting foreign connections", async () => {
  const wrapper = { type: "local", command: ["sh", "-c", "huyang mcp"] };
  const cases = [
    { huyang: foreign },
    { huyang: wrapper },
    { huyang: { ...legacy, command: ["huyang", "mcp", "--profile", "experimental"] } },
    { huyang: legacy, huyang_full: foreign },
    { huyang: legacy, "huyang.lean": foreign },
  ];
  for (const initial of cases) {
    const f = await fixture({ ...initial, unrelated: foreign });
    assert.deepEqual(f.configured().get("unrelated"), foreign);
    for (const [name, config] of Object.entries(initial)) {
      if (name === "huyang" && config !== foreign && config !== wrapper) {
        assert.equal(f.configured().has(name), false);
      } else {
        assert.deepEqual(f.configured().get(name), { ...config, disabled: true, codemode: false });
      }
    }
    const event = await f.run(f.request("ollama"));
    assert.equal(event.tools.huyang_lean_read, undefined);
    assert.equal(event.tools.huyang_full_read, undefined);
    assert.ok(event.tools.execute);
    // The latch also contains Huyang after a later unrelated configuration replay.
    f.inject("another", foreign);
    assert.ok((await f.run(f.request("openai"))).tools.execute);
  }
});

test("unknown Huyang definitions and identity drift withhold only Huyang", async () => {
  const f = await fixture();
  const event = f.request("ollama");
  const execute = event.tools.execute;
  event.tools.huyang_lean_invented = { description: "not registered", input: {} };
  await f.run(event);
  assert.equal(event.tools.huyang_lean_invented, undefined);
  assert.equal(event.tools.execute, execute);
  f.setRegistry(f.registry().map((tool) => tool.id === "huyang_lean_read"
    ? { ...tool, name: "different_tool" } : tool));
  const drift = await f.run(f.request("ollama"));
  assert.equal(drift.tools.huyang_lean_read, undefined);
  assert.equal(drift.tools.huyang_full_read, undefined);
  assert.ok(drift.tools.execute);
});

test("native normalization, explicit disablement and missing resolved model stay guarded", async () => {
  const f = await fixture();
  f.setRegistry([...f.registry(), {
    id: "huyang_full_path_explain", name: "path.explain",
    options: { namespace: "huyang_full", codemode: false },
    description: "normalization fixture", input: { type: "object" },
  }, {
    id: "huyang_full_backup_read", name: "read",
    options: { namespace: "huyang_full_backup", codemode: false },
    description: "unrelated namespace with a shared prefix", input: { type: "object" },
  }]);
  const full = await f.run(f.request("openai"));
  assert.ok(full.tools.huyang_full_path_explain);
  assert.equal(full.tools.huyang_full__path_explain, undefined);
  const lean = await f.run(f.request("ollama"));
  assert.ok(lean.tools.huyang_full_backup_read);
  assert.equal(lean.tools.huyang_full_read, undefined);
  const unresolved = await f.run(f.request(undefined));
  assert.equal(unresolved.tools.huyang_full_read, undefined);
  assert.equal(unresolved.tools.huyang_lean_read, undefined);
  assert.ok(unresolved.tools.huyang_full_backup_read);
  assert.ok(unresolved.tools.execute);
  const disabled = await fixture({ huyang: { ...legacy, disabled: true } });
  assert.equal(disabled.configured().get("huyang_lean").disabled, true);
  assert.equal(disabled.configured().get("huyang_full").disabled, true);
  const request = await disabled.run(disabled.request("ollama"));
  assert.equal(request.tools.huyang_lean_read, undefined);
  assert.equal(request.tools.huyang_full_read, undefined);
});
