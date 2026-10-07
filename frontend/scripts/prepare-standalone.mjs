import { cp, mkdir } from "node:fs/promises";
import { resolve } from "node:path";

// Next's standalone output omits public assets and static chunks by default.
const root = process.cwd();
await mkdir(resolve(root, ".next/standalone/.next"), { recursive: true });
await cp(resolve(root, "public"), resolve(root, ".next/standalone/public"), { recursive: true });
await cp(resolve(root, ".next/static"), resolve(root, ".next/standalone/.next/static"), { recursive: true });
