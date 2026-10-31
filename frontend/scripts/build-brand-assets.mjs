import { mkdir, readFile, writeFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import sharp from "sharp"

const root = resolve(import.meta.dirname, "../..")
const svgPath = resolve(root, "frontend/public/brand-mark.svg")
const svg = await readFile(svgPath)
const iconPng = await sharp(svg, { density: 512 }).resize(256, 256).png().toBuffer()
const applePng = await sharp(svg, { density: 512 }).resize(180, 180).png().toBuffer()

function wrapPngAsIco(png) {
  const header = Buffer.alloc(22)
  header.writeUInt16LE(0, 0)
  header.writeUInt16LE(1, 2)
  header.writeUInt16LE(1, 4)
  header.writeUInt8(0, 6) // 256 pixels
  header.writeUInt8(0, 7) // 256 pixels
  header.writeUInt8(0, 8)
  header.writeUInt8(0, 9)
  header.writeUInt16LE(1, 10)
  header.writeUInt16LE(32, 12)
  header.writeUInt32LE(png.length, 14)
  header.writeUInt32LE(header.length, 18)
  return Buffer.concat([header, png])
}

const assets = [
  ["frontend/public/apple-icon.png", applePng],
  ["frontend/public/favicon.ico", wrapPngAsIco(iconPng)],
  ["desktop/assets/bharatdocs.ico", wrapPngAsIco(iconPng)],
]

for (const [relativePath, contents] of assets) {
  const target = resolve(root, relativePath)
  await mkdir(dirname(target), { recursive: true })
  await writeFile(target, contents)
  console.log(`Created ${relativePath}`)
}
