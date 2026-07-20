import { spawn } from "node:child_process";

const server = spawn(process.execPath, [".next/standalone/server.js"], {
  stdio: "ignore",
  env: { ...process.env, PORT: "3000", HOSTNAME: "localhost" },
});

async function waitForServer() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch("http://localhost:3000/login", { signal: AbortSignal.timeout(1000) });
      if (response.ok) return;
    } catch {}
    if (server.exitCode !== null) throw new Error(`CreditFlow test server exited with ${server.exitCode}`);
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("CreditFlow test server did not become ready");
}

try {
  await waitForServer();
  const runner = spawn(process.execPath, ["node_modules/@playwright/test/cli.js", "test"], {
    stdio: "inherit",
  });
  const exitCode = await new Promise((resolve) => runner.on("exit", resolve));
  process.exitCode = exitCode ?? 1;
} finally {
  server.kill();
}
