"use client"

import { useEffect, useRef, useState, type PointerEvent } from "react"
import { Button } from "@/components/ui/button"
import { configurationRequest, getPagePreview, uploadPdf, type Configuration, type ConfigurationDraft, type PagePreview, type Rect, type TranslationArea } from "@/lib/api-client"

type Props = { configuration: Configuration | null; canUpload: boolean; onClose: () => void; onSaved: (configuration: Configuration) => void; onDeleted: (id: string) => void }
type Tool = "add" | "source" | "destination" | "move"
const field = "h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm"
const empty: ConfigurationDraft = { name: "", page_width: 0, page_height: 0, font_size: 14, regions: [] }

export default function ConfigurationEditor({ configuration, canUpload, onClose, onSaved, onDeleted }: Props) {
  const [draft, setDraft] = useState<ConfigurationDraft>(() => configuration ? structuredClone(configuration) : empty)
  const [uploadId, setUploadId] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [preview, setPreview] = useState<PagePreview | null>(null)
  const [selected, setSelected] = useState(0)
  const [tool, setTool] = useState<Tool>("add")
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [error, setError] = useState("")
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
    const index = tool === "add" ? draft.regions.length : selected
    if (index >= 32) { setError("You can add up to 32 translation areas."); return }
    if (tool !== "add" && !area) return
    const target = tool === "destination" ? "text_rect" : "rect"
    drag.current = { start: position, index, target, rect: tool === "move" ? [...(area.text_rect || area.rect)] : undefined }
    if (tool === "move") drag.current.target = "text_rect"
    setPending(tool === "move" ? [...(area.text_rect || area.rect)] : [...position, ...position] as Rect)
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
      change(previous => {
        if (tool === "add") {
          let number = previous.regions.length + 1
          while (previous.regions.some(region => region.name === `Area ${number}`)) number++
          return { ...previous, regions: [...previous.regions, { name: `Area ${number}`, rect }] }
        }
        return { ...previous, regions: previous.regions.map((region, index) => index === active.index ? { ...region, [active.target]: rect } : region) }
      })
      setSelected(active.index)
      setTool("move")
    }
    drag.current = null
    setPending(null)
  }

  const save = async (asNew = false) => {
    setBusy(true); setError("")
    try {
      // Send only editable fields; an existing layout's id is never part of its body.
      const body: ConfigurationDraft = { name: draft.name, page_width: draft.page_width, page_height: draft.page_height, font_size: draft.font_size, regions: draft.regions }
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
        <div className="flex gap-2">
          <Button ref={closeButton} variant="outline" onClick={close} disabled={busy}>Close</Button>
          {configuration && <Button variant="outline" onClick={() => void save(true)} disabled={busy || !draft.regions.length || loading}>Save as new</Button>}
          <Button className="bg-[#17365d] text-white" onClick={() => void save()} disabled={busy || !draft.regions.length || !draft.page_width || loading}>{busy ? "Please wait…" : "Save configuration"}</Button>
        </div>
      </header>
      {error && <p role="alert" className="border-b border-red-200 bg-red-50 px-5 py-3 text-sm text-red-800">{error}</p>}
      <div className="grid min-h-0 flex-1 overflow-auto md:grid-cols-[300px_1fr]">
        <aside className="space-y-5 border-r bg-white p-5 md:overflow-auto">
          <label className="grid gap-1.5 text-sm font-medium">Configuration name<input className={field} maxLength={80} value={draft.name} onChange={event => change(previous => ({ ...previous, name: event.target.value }))} placeholder="For example, shop bills" /></label>
          <label className="grid gap-1.5 text-sm font-medium">Hindi font size (points)<input className={field} type="number" min={8} max={18} value={draft.font_size} onChange={event => change(previous => ({ ...previous, font_size: Number(event.target.value) }))} /></label>
          <div className="space-y-2 border-t pt-4">
            <label className="grid gap-2 text-sm font-medium">Reference PDF<input type="file" accept=".pdf,application/pdf" disabled={busy || loading || !canUpload} className="w-full text-xs file:mr-2 file:rounded-lg file:border file:border-slate-300 file:bg-white file:px-2 file:py-2" onChange={async event => {
              const file = event.target.files?.[0]; event.target.value = ""; if (!file) return
              setLoading(true); setError("")
              try { const result = await uploadPdf(file); setPreview(null); setUploadId(result.upload_id); setPage(1) }
              catch (caught) { setError(caught instanceof Error ? caught.message : "Upload failed."); setLoading(false) }
            }} /></label>
            {!canUpload && <p className="text-xs text-amber-800">Accept the document terms on the main screen before uploading a reference PDF.</p>}
            <p className="text-xs leading-5 text-slate-500">Choose the original English PDF. Areas scale proportionally if another page or PDF has a different size.</p>
          </div>
          <div className="space-y-2 border-t pt-4">
            <div className="flex items-center justify-between"><h3 className="text-sm font-semibold">Translation areas ({draft.regions.length})</h3><button className="text-sm font-medium text-blue-800 underline" onClick={() => setTool("add")} disabled={!preview}>+ Add</button></div>
            {draft.regions.length === 0 && <p className="text-xs leading-5 text-slate-500">Load a PDF, then drag a rectangle around English text.</p>}
            {draft.regions.map((region, index) => <button key={index} onClick={() => { setSelected(index); setTool("move") }} className={`w-full rounded-lg border px-3 py-2 text-left text-sm ${selected === index ? "border-blue-600 bg-blue-50" : "border-slate-200"}`}>{index + 1}. {region.name}</button>)}
          </div>
          {area && <div className="space-y-3 border-t pt-4">
            <label className="grid gap-1 text-sm">Area name<input className={field} maxLength={80} value={area.name} onChange={event => change(previous => ({ ...previous, regions: previous.regions.map((region, i) => i === selected ? { ...region, name: event.target.value } : region) }))} /></label>
            <div className="grid gap-2">
              <Button variant="outline" disabled={!preview} onClick={() => setTool("source")}>Redraw English area</Button>
              <Button variant="outline" disabled={!preview} onClick={() => setTool("destination")}>Draw Hindi placement area</Button>
              <Button variant="outline" disabled={!preview} onClick={() => setTool("move")}>Move Hindi placement</Button>
              {area.text_rect && <button className="text-xs text-blue-800 underline" onClick={() => change(previous => ({ ...previous, regions: previous.regions.map((region, i) => i === selected ? { ...region, text_rect: null } : region) }))}>Use English area for Hindi placement</button>}
              <button className="text-sm text-red-700 underline" onClick={() => { change(previous => ({ ...previous, regions: previous.regions.filter((_, i) => i !== selected) })); setSelected(0); setTool("add") }}>Delete this area</button>
            </div>
          </div>}
          {configuration && <button disabled={busy} className="text-sm text-red-700 underline" onClick={() => void remove()}>Delete configuration</button>}
          <p className="text-xs leading-5 text-slate-500">Draw one area per line of selectable PDF text. Scanned images need OCR first. Leave enough height for Hindi matras; areas of the same type cannot overlap.</p>
        </aside>
        <section className="min-w-0 overflow-auto p-4 sm:p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 text-sm">
            <p className="font-medium">{tool === "add" ? "Drag to add an English text area" : tool === "source" ? "Drag to replace the selected English area" : tool === "destination" ? "Drag where Hindi should appear" : "Drag to move the selected Hindi placement"}</p>
            {preview && <label className="flex items-center gap-2">Zoom<select className="rounded border bg-white p-1" value={zoom} onChange={event => setZoom(Number(event.target.value))}><option value={1}>Fit width</option><option value={1.5}>150%</option><option value={2}>200%</option></select></label>}
            {preview && <div className="flex items-center gap-2"><Button size="sm" variant="outline" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>Previous</Button><label>Page <select className="rounded border bg-white p-1" value={page} disabled={loading} onChange={event => setPage(Number(event.target.value))}>{Array.from({ length: preview.page_count }, (_, i) => <option key={i} value={i + 1}>{i + 1}</option>)}</select> / {preview.page_count}</label><Button size="sm" variant="outline" disabled={page >= preview.page_count || loading} onClick={() => setPage(page + 1)}>Next</Button></div>}
          </div>
          {loading ? <p className="p-10 text-center text-slate-500" role="status">Loading PDF page…</p> : preview ? <>
            <div className="relative mx-auto shrink-0 overflow-hidden bg-white shadow" style={{ width: `${zoom * 100}%`, maxWidth: `${1000 * zoom}px`, aspectRatio: `${preview.width}/${preview.height}` }}>
              <img src={preview.image} alt={`Reference PDF page ${page}`} className="absolute inset-0 h-full w-full" draggable={false} />
              <svg ref={svg} viewBox={`0 0 ${draft.page_width} ${draft.page_height}`} className="absolute inset-0 h-full w-full touch-none cursor-crosshair" aria-label="Draw translation areas on the PDF" onPointerDown={start} onPointerMove={move} onPointerUp={finish} onPointerCancel={() => { drag.current = null; setPending(null) }}>
                {draft.regions.map((region, index) => <g key={index} pointerEvents="none">
                  <rect x={region.rect[0]} y={region.rect[1]} width={region.rect[2] - region.rect[0]} height={region.rect[3] - region.rect[1]} fill="#2563eb" fillOpacity={0.12} stroke="#2563eb" strokeWidth={index === selected ? 2 : 1} vectorEffect="non-scaling-stroke" />
                  {region.text_rect && <rect x={region.text_rect[0]} y={region.text_rect[1]} width={region.text_rect[2] - region.text_rect[0]} height={region.text_rect[3] - region.text_rect[1]} fill="#059669" fillOpacity={0.12} stroke="#059669" strokeDasharray="4 2" vectorEffect="non-scaling-stroke" />}
                  <text x={region.rect[0] + 2} y={Math.max(10, region.rect[1] - 3)} fontSize={10} fill="#1d4ed8">{index + 1}</text>
                </g>)}
                {pending && <rect pointerEvents="none" x={pending[0]} y={pending[1]} width={pending[2] - pending[0]} height={pending[3] - pending[1]} fill="#f97316" fillOpacity={0.2} stroke="#ea580c" vectorEffect="non-scaling-stroke" />}
              </svg>
            </div>
            <p className="mx-auto mt-3 max-w-[1000px] text-xs text-slate-600">Blue: English text to convert · Green: separate Hindi placement · Select an area in the list to edit it.</p>
          </> : <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center text-sm leading-6 text-slate-500">Choose a reference PDF to see its pages and draw translation areas.{configuration && " Your saved areas are listed on the left; load a PDF to adjust their placement."}</div>}
        </section>
      </div>
    </div>
  )
}
