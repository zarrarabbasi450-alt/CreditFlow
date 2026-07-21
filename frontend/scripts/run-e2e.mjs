import { spawn } from "node:child_process";

const port = "3100";
const server = spawn(process.execPath, ["node_modules/next/dist/bin/next", "dev", "-p", port], {
  stdio: "ignore",
  env: {
    ...process.env,
    PORT: port,
    HOSTNAME: "localhost",
    NEXT_PUBLIC_ENV: "development",
    NEXT_PUBLIC_ENABLE_MOCKS: "true",
  },
});

async function waitForServer() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(`http://localhost:${port}/login`, { signal: AbortSignal.timeout(1000) });
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
    env: { ...process.env, E2E_PORT: port },
  });
  const exitCode = await new Promise((resolve) => runner.on("exit", resolve));
  process.exitCode = exitCode ?? 1;
} finally {
  server.kill();
}
