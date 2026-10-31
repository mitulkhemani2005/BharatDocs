import { spawnSync } from "node:child_process"
import { resolve } from "node:path"

const environment = { ...process.env }
environment.BHARATDOCS_DESKTOP_BUILD = "0"
environment.NEXT_PUBLIC_DESKTOP_APP = "0"

const nextCli = resolve("node_modules/next/dist/bin/next")
const result = spawnSync(process.execPath, [nextCli, "build"], {
  stdio: "inherit",
  env: environment,
})

if (result.error) throw result.error
process.exit(result.status ?? 1)
