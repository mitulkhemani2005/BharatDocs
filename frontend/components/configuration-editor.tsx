"use client"

import { useEffect, useRef, useState, type PointerEvent } from "react"
import { Plus, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { configurationRequest, getPagePreview, type Configuration, type ConfigurationDraft, type PagePreview, type Rect, type TranslationArea } from "@/lib/api-client"

import { resolveAreaOverlap } from "@/lib/area-layout"

type Props = { configuration: Configuration | null; initialUploadId?: string | null; onClose: () => void; onSaved: (configuration: Configuration) => void; onDeleted: (id: string) => void }
type Tool = "add" | "source" | "move"
const field = "h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm"
const empty: ConfigurationDraft = { name: "", page_width: 0, page_height: 0, font_size: 18, regions: [] }

function InlineFontSize({ value, defaultValue, label, disabled, onFocus, onCommit }: { value: number; defaultValue: number; label: string; disabled: boolean; onFocus: () => void; onCommit: (value: number | null) => void }) {
  const [text, setText] = useState(String(value))
  const edited = useRef(false)
  useEffect(() => setText(String(value)), [value])
  return <input aria-label={label} type="number" min={8} max={32} step="any" inputMode="decimal" disabled={disabled} value={text} className="w-8 appearance-none bg-transparent p-0 text-center text-xs font-medium outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none" onFocus={event => { edited.current = false; onFocus(); event.currentTarget.select() }} onChange={event => { edited.current = true; setText(event.target.value) }} onBlur={event => {
    if (!edited.current) return
    const raw = event.currentTarget.value
    if (raw === "") { onCommit(null); setText(String(defaultValue)) }
    else if (Number.isFinite(Number(raw)) && Number(raw) >= 8 && Number(raw) <= 32) onCommit(Number(raw))
    else setText(String(value))
  }} onKeyDown={event => {
    if (event.key === "Enter") { event.preventDefault(); event.currentTarget.blur() }
    if (event.key === "Escape") { event.stopPropagation(); edited.current = false; setText(String(value)); event.currentTarget.blur() }
  }} />
}

export default function ConfigurationEditor({ configuration, initialUploadId, onClose, onSaved, onDeleted }: Props) {
  const [draft, setDraft] = useState<ConfigurationDraft>(() => configuration ? structuredClone(configuration) : empty)
  const uploadId = initialUploadId || null
  const [page, setPage] = useState(1)
  const [preview, setPreview] = useState<PagePreview | null>(null)
  const [selected, setSelected] = useState(0)
  const [tool, setTool] = useState<Tool>("add")
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [dirty, setDirty] = useState(false)
  const [pending, setPending] = useState<Rect | null>(null)
  const svg = useRef<SVGSVGElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  const drag = useRef<{ start: [number, number]; rect?: Rect; index: number; target: "rect" | "text_rect" } | null>(null)

  useEffect(() => {
    closeButton.current?.focus()
    const previous = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => { document.body.style.overflow = previous }
  }, [])

  useEffect(() => {
    if (!uploadId) return
    let cancelled = false
    setLoading(true)
    setError("")
    getPagePreview(uploadId, page).then(result => {
      if (cancelled) return
      setPreview(result)
      setDraft(previous => {
        const sx = previous.page_width ? result.width / previous.page_width : 1
        const sy = previous.page_height ? result.height / previous.page_height : 1
        const scale = (rect: Rect): Rect => rect.map((v, i) => v * (i % 2 === 0 ? sx : sy)) as Rect
        return { ...previous, page_width: result.width, page_height: result.height,
          regions: previous.regions.map(region => ({ ...region, rect: scale(region.rect), text_rect: region.text_rect ? scale(region.text_rect) : null })) }
      })
    }).catch(caught => { if (!cancelled) setError(caught.message) }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [uploadId, page])

  const change = (update: (previous: ConfigurationDraft) => ConfigurationDraft) => { setDraft(update); setDirty(true) }
  const close = () => { if (!dirty || window.confirm("Discard unsaved configuration changes?")) onClose() }
  const area = draft.regions[selected]
  const point = (event: PointerEvent<SVGSVGElement>): [number, number] => {
    const bounds = svg.current!.getBoundingClientRect()
    return [Math.max(0, Math.min(draft.page_width, (event.clientX - bounds.left) / bounds.width * draft.page_width)), Math.max(0, Math.min(draft.page_height, (event.clientY - bounds.top) / bounds.height * draft.page_height))]
  }
  const start = (event: PointerEvent<SVGSVGElement>) => {
    if (loading || busy || event.button !== 0) return
    event.preventDefault()
    const position = point(event)
    if (tool === "move" && area && !(position[0] >= area.rect[0] && position[0] <= area.rect[2] && position[1] >= area.rect[1] && position[1] <= area.rect[3])) {
      const hit = draft.regions.findIndex(region => position[0] >= region.rect[0] && position[0] <= region.rect[2] && position[1] >= region.rect[1] && position[1] <= region.rect[3])
      if (hit >= 0) setSelected(hit)
      return
    }
    const index = (tool === "add") ? draft.regions.length : selected
    if (index >= 32) { setError("You can add up to 32 translation areas."); return }
    if (tool !== "add" && !area) return
    const target = "rect" as const
    drag.current = { start: position, index, target, rect: tool === "move" ? [...area.rect] : undefined }
    setPending(tool === "move" ? [...area.rect] : [...position, ...position] as Rect)
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  const move = (event: PointerEvent<SVGSVGElement>) => {
    const active = drag.current
    if (!active) return
    const [x, y] = point(event)
    const [sx, sy] = active.start
    if (active.rect) {
      const [x0, y0, x1, y1] = active.rect
      const dx = Math.max(-x0, Math.min(draft.page_width - x1, x - sx))
      const dy = Math.max(-y0, Math.min(draft.page_height - y1, y - sy))
      setPending([x0 + dx, y0 + dy, x1 + dx, y1 + dy])
    } else setPending([Math.min(sx, x), Math.min(sy, y), Math.max(sx, x), Math.max(sy, y)])
  }
  const finish = () => {
    const active = drag.current
    if (active && pending && pending[2] - pending[0] >= 2 && pending[3] - pending[1] >= 2) {
      const rect = pending
      let regions = [...draft.regions]
      if (tool === "add") {
        let number = regions.length + 1
        while (regions.some(region => region.name === `Area ${number}`)) number++
        regions.push({ name: `Area ${number}`, rect, mode: "translate" })
      } else regions[active.index] = { ...regions[active.index], rect, text_rect: null }
      const result = resolveAreaOverlap(regions, active.index, draft.page_width, draft.page_height, tool === "move")
      change(previous => ({ ...previous, regions: result.regions }))
      setSelected(result.selected)
      setNotice(result.adjusted ? "Area snapped to the nearest free position." : "")
      setTool("move")
    }
    drag.current = null
    setPending(null)
  }

  const save = async (asNew = false) => {
    setBusy(true); setError("")
    try {
      // Send only editable fields; an existing layout's id is never part of its body.
      let regions = draft.regions.map(region => ({ ...region, text_rect: null })) as TranslationArea[]
      const names = new Set<string>()
      regions = regions.map((region, index) => {
        const base = region.name.trim() || `Area ${index + 1}`
        let name = base, suffix = 2
        while (names.has(name)) name = `${base.slice(0, 70)} (${suffix++})`
        names.add(name)
        return { ...region, name }
      })
      const body: ConfigurationDraft = { name: draft.name, page_width: draft.page_width, page_height: draft.page_height, font_size: draft.font_size, regions }
      const id = configuration && !asNew ? configuration.id : null
      const saved = await configurationRequest<Configuration>(id ? `/configurations/${id}` : "/configurations", id ? "PUT" : "POST", body)
      onSaved(saved)
    } catch (caught) { setError(caught instanceof Error ? caught.message : "The configuration could not be saved.") }
    finally { setBusy(false) }
  }
  const remove = async () => {
    if (!configuration || !window.confirm(`Delete configuration “${configuration.name}”?`)) return
    setBusy(true); setError("")
    try { await configurationRequest(`/configurations/${configuration.id}`, "DELETE"); onDeleted(configuration.id) }
    catch (caught) { setError(caught instanceof Error ? caught.message : "The configuration could not be deleted.") }
    finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-slate-50 text-slate-900" role="dialog" aria-modal="true" aria-labelledby="configuration-title" onKeyDown={event => {
      if (event.key === "Escape" && !busy) close()
      if (event.key === "Tab") {
        const items = event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex="0"]')
        if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items[items.length - 1]?.focus() }
        else if (!event.shiftKey && document.activeElement === items[items.length - 1]) { event.preventDefault(); items[0]?.focus() }
      }
    }}>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b bg-white px-5 py-3">
        <div><h2 id="configuration-title" className="text-lg font-semibold">{configuration ? "Edit configuration" : "New configuration"}</h2><p className="text-xs text-slate-500">Select areas on any page. They repeat on every page.</p></div>
        <div className="flex flex-wrap gap-2">
          {configuration && <Button className="border border-red-300 bg-red-50 text-red-700 hover:bg-red-100" disabled={busy} onClick={() => void remove()}>Delete configuration</Button>}
          <Button ref={closeButton} variant="outline" onClick={close} disabled={busy}>Close</Button>
          {configuration && <Button variant="outline" onClick={() => void save(true)} disabled={busy || !draft.regions.length || loading}>Save as new</Button>}
          <Button className="bg-[#17365d] text-white" onClick={() => void save()} disabled={busy || !draft.regions.length || !draft.page_width || loading}>{busy ? "Please wait…" : "Save configuration"}</Button>
        </div>
      </header>
      {notice && <p role="status" className="border-b border-blue-200 bg-blue-50 px-5 py-2 text-sm text-blue-800">{notice}</p>}
      {error && <p role="alert" className="border-b border-red-200 bg-red-50 px-5 py-3 text-sm text-red-800">{error}</p>}
      <div className="grid min-h-0 flex-1 overflow-auto md:grid-cols-[300px_1fr]">
        <aside className="space-y-5 border-r bg-white p-5 md:overflow-auto">
          <label className="grid gap-1.5 text-sm font-medium">Configuration name<input className={field} maxLength={80} value={draft.name} onChange={event => change(previous => ({ ...previous, name: event.target.value }))} placeholder="For example, shop bills" /></label>
          <label className="grid gap-1.5 text-sm font-medium">Default Hindi size (maximum)<input className={field} type="number" min={8} max={32} value={draft.font_size} onChange={event => change(previous => ({ ...previous, font_size: Number(event.target.value) }))} /><span className="text-xs font-normal leading-5 text-slate-500">8–32 pt maximum. Text gets smaller automatically when needed to fit.</span></label>
          <div className="space-y-2 border-t pt-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">PDF areas <span className="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{draft.regions.length}</span></h3>
              <Button size="sm" className="gap-1.5 rounded-lg bg-[#17365d] text-white shadow-sm hover:bg-[#102846]" aria-pressed={tool === "add"} onClick={() => { setTool("add"); setNotice("Drag on the PDF to add a new area.") }} disabled={!preview || busy || draft.regions.length >= 32}><Plus className="size-3.5" aria-hidden="true" />Add area</Button>
            </div>
            {draft.regions.length === 0 && <p className="text-xs leading-5 text-slate-500">Load a PDF, then drag a rectangle around English text.</p>}
            {draft.regions.map((region, index) => <div key={index} className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${selected === index ? "border-blue-600 bg-blue-50" : "border-slate-200"}`}>
              <button className="shrink-0 text-sm" aria-label={`Select area ${index + 1}`} onClick={() => { setSelected(index); setTool("move") }}>{index + 1}.</button>
              <input aria-label={`Rename area ${index + 1}`} className="min-w-0 w-full bg-transparent text-sm outline-none focus:ring-2 focus:ring-blue-500" maxLength={80} value={region.name} onFocus={() => { setSelected(index); setTool("move") }} onChange={event => change(previous => ({ ...previous, regions: previous.regions.map((item, i) => i === index ? { ...item, name: event.target.value } : item) }))} />
              {region.mode === "preserve" && <span className="text-xs text-red-700">Protected</span>}
              {region.mode !== "preserve" && <div className="flex shrink-0 items-center gap-1">
                <label className="flex h-7 cursor-text items-center gap-0.5 rounded-md border border-transparent bg-slate-100 px-1.5 text-slate-700 transition hover:border-slate-300 focus-within:border-blue-400 focus-within:bg-white focus-within:ring-2 focus-within:ring-blue-100" title={region.font_size == null ? "Default maximum size. Auto-fits inside the area. Click to edit." : "Maximum size for this area. Auto-fits when needed. Click to edit."}>
                  <InlineFontSize label={`Font size for area ${index + 1}`} disabled={busy} value={region.font_size ?? draft.font_size} defaultValue={draft.font_size} onFocus={() => { setSelected(index); setTool("move") }} onCommit={value => change(previous => ({ ...previous, regions: previous.regions.map((item, i) => i === index ? { ...item, font_size: value } : item) }))} />
                  <span className="text-[10px] text-slate-400" aria-hidden="true">pt</span>
                </label>
                {region.font_size != null && region.font_size !== draft.font_size && <button type="button" disabled={busy} aria-label={`Use default font size for area ${index + 1}`} title={`Reset to default (${draft.font_size} pt)`} className="grid size-6 place-items-center rounded text-slate-400 hover:bg-slate-100 hover:text-[#17365d] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500" onClick={() => change(previous => ({ ...previous, regions: previous.regions.map((item, i) => i === index ? { ...item, font_size: null } : item) }))}><RotateCcw className="size-3" aria-hidden="true" /></button>}
              </div>}
            </div>)}
            {draft.regions.length > 0 && <p className="pt-1 text-[11px] text-slate-500">Click any area name or font size to edit it.</p>}
          </div>
          {area && <div className="space-y-3 border-t pt-4">
            <p className="text-sm font-medium">Selected: {area.name}</p>
            <div className="grid grid-cols-2 gap-2">
              <Button variant={tool === "move" ? "default" : "outline"} disabled={!preview || busy} onClick={() => setTool("move")}>Move area</Button>
              <Button variant="outline" disabled={!preview || busy} onClick={() => setTool("source")}>Redraw area</Button>
            </div>
            <Button className="w-full border border-red-300 bg-red-50 text-red-700 hover:bg-red-100" disabled={busy} onClick={() => { change(previous => ({ ...previous, regions: previous.regions.filter((_, i) => i !== selected) })); setSelected(0); setTool("move") }}>Delete selected area</Button>
          </div>}
          <p className="text-xs leading-5 text-slate-500">Every area stays separately listed and numbered on the PDF. Hindi spacing and overlapping selections are handled automatically during conversion. Text in scanned images is read automatically with offline OCR.</p>
        </aside>
        <section className="min-w-0 overflow-auto p-4 sm:p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 text-sm">
            <p className="font-medium">{tool === "add" ? "Drag to add an English text area" : tool === "source" ? "Drag to replace the selected English area" : "Drag the selected area to move it"}</p>
            {preview && <label className="flex items-center gap-2">Zoom<select className="rounded border bg-white p-1" value={zoom} onChange={event => setZoom(Number(event.target.value))}><option value={1}>Fit width</option><option value={1.5}>150%</option><option value={2}>200%</option></select></label>}
            {preview && <div className="flex items-center gap-2"><Button size="sm" variant="outline" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Previous</Button><label>Page <select className="rounded border bg-white p-1" value={page} disabled={loading} onChange={event => setPage(Number(event.target.value))}>{Array.from({ length: preview.page_count }, (_, i) => <option key={i} value={i + 1}>{i + 1}</option>)}</select> / {preview.page_count}</label><Button size="sm" variant="outline" disabled={page >= preview.page_count || loading} onClick={() => setPage(page + 1)}>Next</Button></div>}
          </div>
          {loading ? <p className="p-10 text-center text-slate-500" role="status">Loading PDF page…</p> : preview ? <>
            <div className="relative mx-auto shrink-0 overflow-hidden bg-white shadow" style={{ width: `${zoom * 100}%`, maxWidth: `${1000 * zoom}px`, aspectRatio: `${preview.width}/${preview.height}` }}>
              <img src={preview.image} alt={`Reference PDF page ${page}`} className="absolute inset-0 h-full w-full" draggable={false} />
              <svg ref={svg} viewBox={`0 0 ${draft.page_width} ${draft.page_height}`} className="absolute inset-0 h-full w-full touch-none cursor-crosshair" aria-label="Draw or move PDF areas" onPointerDown={start} onPointerMove={move} onPointerUp={finish} onPointerCancel={() => { drag.current = null; setPending(null) }}>
                {draft.regions.map((region, index) => <g key={index} pointerEvents="none">
                  <rect x={region.rect[0]} y={region.rect[1]} width={region.rect[2] - region.rect[0]} height={region.rect[3] - region.rect[1]} fill={region.mode === "preserve" ? "#dc2626" : "#2563eb"} fillOpacity={0.12} stroke={region.mode === "preserve" ? "#dc2626" : "#2563eb"} strokeWidth={index === selected ? 2 : 1} vectorEffect="non-scaling-stroke" />
                  <text x={region.rect[0] + 2} y={Math.max(10, region.rect[1] - 3)} fontSize={10} fill="#1d4ed8">{index + 1}</text>
                </g>)}
                {pending && <rect pointerEvents="none" x={pending[0]} y={pending[1]} width={pending[2] - pending[0]} height={pending[3] - pending[1]} fill="#f97316" fillOpacity={0.2} stroke="#ea580c" vectorEffect="non-scaling-stroke" />}
              </svg>
            </div>
            <p className="mx-auto mt-3 max-w-[1000px] text-xs text-slate-600">Select an area by its number in the list to rename, move or delete it. Overlapping areas remain separate entries.</p>
          </> : <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center text-sm leading-6 text-slate-500">Upload a PDF on the main screen to draw and move areas.{configuration && " Your saved areas are listed on the left."}</div>}
        </section>
      </div>
    </div>
  )
}
