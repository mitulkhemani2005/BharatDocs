import { spawnSync } from "node:child_process"
import { resolve } from "node:path"

const nextCli = resolve("node_modules/next/dist/bin/next")
const result = spawnSync(process.execPath, [nextCli, "build"], {
  stdio: "inherit",
  env: {
    ...process.env,
    BHARATDOCS_DESKTOP_BUILD: "1",
    NEXT_PUBLIC_DESKTOP_APP: "1",
    NEXT_PUBLIC_API_URL: "",
  },
})

if (result.error) throw result.error
process.exit(result.status ?? 1)
