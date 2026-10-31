import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"
import ts from "typescript"

const source = await readFile(new URL("../lib/area-layout.ts", import.meta.url), "utf8")
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText
const { resolveAreaOverlap } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`)
const area = (name, rect, mode = "translate") => ({ name, rect, mode })

const merged = resolveAreaOverlap([area("One", [0, 0, 20, 20]), area("Two", [15, 0, 35, 20]), area("Three", [30, 0, 50, 20])], 0, 100, 100)
assert.equal(merged.regions.length, 1)
assert.deepEqual(merged.regions[0].rect, [0, 0, 50, 20])

const moved = resolveAreaOverlap([area("One", [0, 0, 20, 20]), area("Two", [10, 0, 30, 20])], 1, 100, 100, true)
assert.equal(moved.regions.length, 2)
assert.deepEqual(moved.regions[1].rect, [20, 0, 40, 20])

const protectedArea = resolveAreaOverlap([area("One", [0, 0, 20, 20]), area("Amount", [5, 5, 15, 15], "preserve")], 1, 100, 100)
assert.equal(protectedArea.regions.length, 2)
assert.equal(protectedArea.adjusted, false)

const full = resolveAreaOverlap([area("One", [0, 0, 100, 100]), area("Two", [10, 10, 30, 30])], 1, 100, 100, true)
assert.equal(full.regions.length, 1)
assert.equal(full.selected, 0)
assert.deepEqual(full.regions[0].rect, [0, 0, 100, 100])
console.log("Area layout: transitive merge, movement snap, protected overlap, and full-page fallback passed.")
