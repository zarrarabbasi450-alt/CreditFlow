import { cpSync, existsSync, mkdirSync } from "node:fs";

const standalone = ".next/standalone";

if (existsSync(standalone)) {
  mkdirSync(`${standalone}/.next`, { recursive: true });
  cpSync(".next/static", `${standalone}/.next/static`, { recursive: true });
  if (existsSync("public")) cpSync("public", `${standalone}/public`, { recursive: true });
}
