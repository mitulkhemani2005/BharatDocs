import { spawnSync } from "node:child_process"
import { copyFile, mkdir, readdir, readFile, writeFile } from "node:fs/promises"
import { dirname, relative, resolve, sep } from "node:path"

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
if (result.status !== 0) process.exit(result.status ?? 1)

const exportRoot = resolve(".next-desktop")
const publicFont = resolve("public/fonts/NotoSansDevanagari-Regular.ttf")
const exportedFont = resolve(exportRoot, "fonts/NotoSansDevanagari-Regular.ttf")
await mkdir(dirname(exportedFont), { recursive: true })
await copyFile(publicFont, exportedFont)

async function rewriteCss(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const entryPath = resolve(directory, entry.name)
    if (entry.isDirectory()) {
      await rewriteCss(entryPath)
    } else if (entry.isFile() && entry.name.endsWith(".css")) {
      const css = await readFile(entryPath, "utf8")
      const fontUrl = relative(dirname(entryPath), exportedFont).split(sep).join("/")
      const updated = css.replace(/url\((?:["'])?\/fonts\/NotoSansDevanagari-Regular\.ttf(?:["'])?\)/g, `url("${fontUrl}")`)
      if (updated !== css) await writeFile(entryPath, updated)
    }
  }
}

await rewriteCss(resolve(exportRoot, "_next/static"))
