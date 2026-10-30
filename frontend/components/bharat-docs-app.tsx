"use client"

import type React from "react"
import { useEffect, useRef, useState } from "react"
import {
  ArrowRight,
  Check,
  CheckCircle2,
  Download,
  Eye,
  FileCheck2,
  FileText,
  Languages,
  LoaderCircle,
  Printer,
  RotateCcw,
  Trash2,
  Upload,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"

type Status = "idle" | "uploading" | "processing" | "complete"
type HindiFont = "Mukta" | "Noto Sans Devanagari"

const MAX_FILE_SIZE = 20 * 1024 * 1024
function getApiBase() {
  if (typeof window !== "undefined") {
    const localHost = ["127.0.0.1", "localhost"].includes(window.location.hostname)
    const developmentPort = ["3000", "3001"].includes(window.location.port)
    if (localHost && window.location.port && !developmentPort) return window.location.origin
  }
  const configuredApi = process.env.NEXT_PUBLIC_API_URL
  if (configuredApi) return configuredApi.replace(/\/$/, "")
  if (typeof window !== "undefined" && !["3000", "3001"].includes(window.location.port)) {
    return window.location.origin
  }
  return "http://localhost:5000"
}

async function responseError(response: Response, fallback: string) {
  const body = await response.json().catch(() => null)
  return typeof body?.error === "string" ? body.error : fallback
}

export default function BharatDocsApp() {
  const [status, setStatus] = useState<Status>("idle")
  const [fontFamily, setFontFamily] = useState<HindiFont>("Mukta")
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [translatedBlob, setTranslatedBlob] = useState<Blob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    if (!previewUrl) return
    return () => URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  useEffect(() => {
    if (!showPreview) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setShowPreview(false)
        setPreviewUrl(null)
      }
    }
    window.addEventListener("keydown", closeOnEscape)
    return () => window.removeEventListener("keydown", closeOnEscape)
  }, [showPreview])

  const startTranslation = async (file: File) => {
    setSelectedFile(file)
    setError(null)
    setTranslatedBlob(null)
    setStatus("uploading")

    try {
      const form = new FormData()
      form.append("file", file)

      const apiBase = getApiBase()
      const uploadResponse = await fetch(`${apiBase}/upload`, { method: "POST", body: form })
      if (!uploadResponse.ok) {
        throw new Error(await responseError(uploadResponse, "The PDF could not be uploaded. Please try again."))
      }
      const upload = await uploadResponse.json()

      setStatus("processing")
      const translationResponse = await fetch(`${apiBase}/translate-pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ upload_id: upload.upload_id, font_family: fontFamily }),
      })
      if (!translationResponse.ok) {
        throw new Error(await responseError(translationResponse, "The PDF could not be translated. Please try again."))
      }

      const contentType = translationResponse.headers.get("content-type") || ""
      if (!contentType.includes("application/pdf")) {
        throw new Error("The server returned an unreadable file. Please try again.")
      }

      setTranslatedBlob(await translationResponse.blob())
      setStatus("complete")
    } catch (caughtError) {
      setStatus("idle")
      setError(caughtError instanceof Error ? caughtError.message : "Something went wrong. Please try again.")
    }
  }

  const selectFile = (file?: File) => {
    if (!file) return
    setError(null)
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setStatus("idle")
      setSelectedFile(null)
      setTranslatedBlob(null)
      setError("Choose a PDF file to continue.")
      return
    }
    if (file.size > MAX_FILE_SIZE) {
      setStatus("idle")
      setSelectedFile(null)
      setTranslatedBlob(null)
      setError("This file is larger than 20 MB. Choose a smaller PDF.")
      return
    }
    void startTranslation(file)
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    selectFile(event.target.files?.[0])
    event.target.value = ""
  }

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    selectFile(event.dataTransfer.files?.[0])
  }

  const handleDownload = () => {
    if (!translatedBlob || !selectedFile) return
    const url = URL.createObjectURL(translatedBlob)
    const anchor = document.createElement("a")
    const baseName = selectedFile.name.replace(/\.pdf$/i, "")
    anchor.href = url
    anchor.download = `Hindi_${baseName}.pdf`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const handlePreview = () => {
    if (!translatedBlob) return
    setPreviewUrl(URL.createObjectURL(translatedBlob))
    setShowPreview(true)
  }

  const closePreview = () => {
    setShowPreview(false)
    setPreviewUrl(null)
  }

  const handleReset = () => {
    setStatus("idle")
    setSelectedFile(null)
    setTranslatedBlob(null)
    setError(null)
    closePreview()
  }

  const isBusy = status === "uploading" || status === "processing"

  return (
    <main className="min-h-screen overflow-hidden bg-[#f7f6f2] text-slate-900">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[480px] bg-[radial-gradient(ellipse_at_top,_rgba(255,237,213,0.78),_transparent_70%)]" />

      <div className="relative mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 pb-6 pt-5 sm:px-8 sm:pt-7">
        <header className="flex items-center justify-between">
          <a href="#home" className="flex items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500">
            <span className="grid size-10 place-items-center rounded-xl bg-orange-500 text-white shadow-sm shadow-orange-200">
              <FileText className="size-5" aria-hidden="true" />
            </span>
            <span className="text-[17px] font-bold tracking-tight">BharatDocs</span>
          </a>
          <div className="hidden items-center gap-2 rounded-full border border-orange-100 bg-white/75 px-3.5 py-2 text-sm font-medium text-slate-600 sm:flex">
            <Languages className="size-4 text-orange-600" aria-hidden="true" />
            <span lang="en">English</span>
            <ArrowRight className="size-3.5 text-slate-400" aria-hidden="true" />
            <span className="font-hindi text-[15px] text-slate-800" lang="hi">हिंदी</span>
          </div>
        </header>

        <section id="home" className="mx-auto grid w-full flex-1 items-center gap-10 pb-10 pt-12 lg:grid-cols-[1fr_0.88fr] lg:gap-16 lg:pb-16 lg:pt-14">
          <div className="mx-auto w-full max-w-xl lg:mx-0">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-orange-100 bg-white/80 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.15em] text-orange-700">
              <span className="size-1.5 rounded-full bg-orange-500" />
              Simple PDF translation
            </div>
            <h1 className="max-w-xl text-4xl font-semibold leading-[1.12] tracking-[-0.045em] text-slate-950 sm:text-5xl lg:text-[3.5rem]">
              Your documents, in <span className="text-orange-600">clear Hindi.</span>
            </h1>
            <p className="mt-5 max-w-lg text-[16px] leading-7 text-slate-600 sm:text-lg">
              Upload a bill or PDF and get a translated copy with readable Devanagari text, ready to preview and download.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm text-slate-600">
              <span className="inline-flex items-center gap-2"><Check className="size-4 text-emerald-600" aria-hidden="true" /> Layout stays in place</span>
              <span className="inline-flex items-center gap-2"><Check className="size-4 text-emerald-600" aria-hidden="true" /> Numbers are preserved</span>
            </div>

            <div
              onDragEnter={(event) => { event.preventDefault(); setIsDragging(true) }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setIsDragging(false) }}
              onDrop={handleDrop}
              className={`mt-9 rounded-2xl border bg-white p-5 shadow-[0_18px_55px_-35px_rgba(15,23,42,0.25)] transition sm:p-6 ${isDragging ? "border-orange-400 ring-4 ring-orange-100" : "border-slate-200/80"}`}
              aria-live="polite"
            >
              {status === "idle" && (
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">Hindi print font</p>
                    <p className="mt-0.5 text-xs text-slate-500">Choose the style that is easiest to read.</p>
                  </div>
                  <div className="grid grid-cols-2 gap-2" role="group" aria-label="Hindi print font">
                    {(["Mukta", "Noto Sans Devanagari"] as const).map((font) => (
                      <button
                        key={font}
                        type="button"
                        onClick={() => setFontFamily(font)}
                        aria-pressed={fontFamily === font}
                        className={`rounded-lg border px-3 py-2 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 ${fontFamily === font ? "border-orange-300 bg-orange-50 text-orange-950" : "border-slate-200 bg-white text-slate-600 hover:border-orange-200"}`}
                      >
                        <span className={`block text-sm font-semibold ${font === "Mukta" ? "font-mukta" : "font-hindi"}`}>{font === "Mukta" ? "Mukta" : "Noto Sans"}</span>
                        <span className="mt-0.5 block text-[10px] text-slate-500">{font === "Mukta" ? "Recommended" : "Classic"}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {status === "complete" ? (
                <div className="flex flex-col gap-5">
                  <div className="flex items-start gap-3">
                    <span className="grid size-11 shrink-0 place-items-center rounded-full bg-emerald-50 text-emerald-700">
                      <CheckCircle2 className="size-6" aria-hidden="true" />
                    </span>
                    <div className="min-w-0 flex-1 pt-0.5">
                      <h2 className="font-semibold text-slate-900">Your Hindi PDF is ready</h2>
                      <p className="mt-1 truncate text-sm text-slate-500">{selectedFile?.name}</p>
                    </div>
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Button onClick={handleDownload} className="h-11 flex-1 gap-2 bg-orange-600 text-white hover:bg-orange-700">
                      <Download className="size-4" aria-hidden="true" /> Download PDF
                    </Button>
                    <Button onClick={handlePreview} variant="outline" className="h-11 flex-1 gap-2 border-slate-200 bg-white">
                      <Eye className="size-4" aria-hidden="true" /> Preview
                    </Button>
                    <Button onClick={handleReset} variant="outline" className="h-11 gap-2 border-slate-200 bg-white sm:flex-none">
                      <RotateCcw className="size-4" aria-hidden="true" /> New PDF
                    </Button>
                  </div>
                </div>
              ) : isBusy ? (
                <div className="py-2">
                  <div className="flex items-center gap-3">
                    <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-orange-50 text-orange-700">
                      {status === "uploading" ? <Upload className="size-5" aria-hidden="true" /> : <LoaderCircle className="size-5 animate-spin" aria-hidden="true" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <h2 className="font-semibold text-slate-900">{status === "uploading" ? "Uploading your PDF…" : "Translating into Hindi…"}</h2>
                      <p className="mt-1 truncate text-sm text-slate-500">{selectedFile?.name}</p>
                    </div>
                  </div>
                  <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-orange-50">
                    <div className={`h-full rounded-full bg-orange-500 transition-all duration-700 ${status === "uploading" ? "w-1/3" : "w-4/5 animate-pulse"}`} />
                  </div>
                  <p className="mt-3 text-center text-xs text-slate-500">This can take a little longer for multi-page PDFs.</p>
                </div>
              ) : (
                <>
                  <label
                    htmlFor="pdf-upload"
                    className={`flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed px-5 py-8 text-center transition has-[:focus-visible]:border-orange-400 has-[:focus-visible]:ring-4 has-[:focus-visible]:ring-orange-100 sm:py-9 ${isDragging ? "border-orange-400 bg-orange-50/70" : "border-slate-200 bg-slate-50/70 hover:border-orange-300 hover:bg-orange-50/50"}`}
                  >
                    <span className="grid size-12 place-items-center rounded-2xl bg-white text-orange-600 shadow-sm ring-1 ring-slate-200/70">
                      <Upload className="size-5" aria-hidden="true" />
                    </span>
                    <span className="mt-4 text-base font-semibold text-slate-800">Drop your PDF here</span>
                    <span className="mt-1 text-sm text-slate-500">or <span className="font-medium text-orange-700 underline decoration-orange-200 underline-offset-2">browse files</span></span>
                    <span className="mt-4 rounded-full bg-white px-3 py-1 text-xs text-slate-500 ring-1 ring-slate-200/70">PDF only · Up to 20 MB</span>
                    <input
                      ref={fileInputRef}
                      id="pdf-upload"
                      type="file"
                      accept=".pdf,application/pdf"
                      onChange={handleFileChange}
                      className="sr-only"
                    />
                  </label>
                  {error && (
                    <div className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3.5 py-3 text-sm text-red-800" role="alert">
                      <span className="mt-0.5 size-2 shrink-0 rounded-full bg-red-500" />
                      <span className="flex-1">{error}</span>
                      {selectedFile && <button className="shrink-0 font-semibold underline underline-offset-2" onClick={() => void startTranslation(selectedFile)}>Retry</button>}
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="mt-4 flex items-center justify-center gap-2 text-xs text-slate-500 sm:justify-start">
              <Trash2 className="size-3.5" aria-hidden="true" />
              Files stay on this computer · works offline after installation.
            </div>
          </div>

          <aside className="mx-auto w-full max-w-md lg:mx-0 lg:justify-self-end">
            <div className="overflow-hidden rounded-[26px] border border-slate-200/80 bg-white shadow-[0_28px_75px_-46px_rgba(15,23,42,0.28)]">
              <div className="flex items-center justify-between border-b border-slate-100 px-6 py-5">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Three simple steps</p>
                  <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">From PDF to Hindi</h2>
                </div>
                <span className="grid size-10 place-items-center rounded-xl bg-orange-50 text-orange-700"><Languages className="size-5" aria-hidden="true" /></span>
              </div>
              <ol className="divide-y divide-slate-100 px-6">
                <li className="flex gap-4 py-5">
                  <span className="grid size-9 shrink-0 place-items-center rounded-full bg-slate-100 text-sm font-semibold text-slate-700">01</span>
                  <div><h3 className="font-semibold text-slate-800">Choose a PDF</h3><p className="mt-1 text-sm leading-6 text-slate-500">Select a bill or document from your device.</p></div>
                </li>
                <li className="flex gap-4 py-5">
                  <span className="grid size-9 shrink-0 place-items-center rounded-full bg-orange-100 text-sm font-semibold text-orange-800">02</span>
                  <div><h3 className="font-semibold text-slate-800">Let BharatDocs translate</h3><p className="mt-1 text-sm leading-6 text-slate-500">English text in the configured fields is translated to Hindi.</p></div>
                </li>
                <li className="flex gap-4 py-5">
                  <span className="grid size-9 shrink-0 place-items-center rounded-full bg-emerald-100 text-sm font-semibold text-emerald-800">03</span>
                  <div><h3 className="font-semibold text-slate-800">Preview and save</h3><p className="mt-1 text-sm leading-6 text-slate-500">Check your translated PDF, then download a copy.</p></div>
                </li>
              </ol>
              <div className="mx-6 mb-6 rounded-2xl bg-[#f7f6f2] p-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-9 place-items-center rounded-xl bg-white text-emerald-700 shadow-sm"><FileCheck2 className="size-4" aria-hidden="true" /></span>
                  <div><p className="text-sm font-semibold text-slate-800">Made for readable Hindi</p><p className="mt-0.5 font-mukta text-[17px] leading-7 text-slate-600" lang="hi">साफ़ और स्पष्ट देवनागरी</p></div>
                </div>
              </div>
            </div>
            <p className="mt-4 px-2 text-center text-xs leading-5 text-slate-500">Please review translated names and amounts before using the document.</p>
          </aside>
        </section>

        <footer className="flex flex-col gap-2 border-t border-slate-200/80 pt-4 text-center text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:text-left">
          <p>Made for <span className="font-medium text-slate-700">New Durga Agencies, Ujjain</span></p>
          <p>© {new Date().getFullYear()} BharatDocs</p>
        </footer>
      </div>

      {showPreview && previewUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6" role="dialog" aria-modal="true" aria-label="Translated PDF preview">
          <button aria-label="Close preview" className="absolute inset-0 cursor-default bg-slate-950/65 backdrop-blur-sm" onClick={closePreview} />
          <section className="relative flex h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
            <header className="flex min-h-14 items-center justify-between gap-3 border-b border-slate-200 px-4 sm:px-5">
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-orange-50 text-orange-700"><FileText className="size-4" aria-hidden="true" /></span>
                <p className="truncate text-sm font-medium text-slate-800">{selectedFile?.name}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => iframeRef.current?.contentWindow?.print()} className="gap-2 border-slate-200"><Printer className="size-4" aria-hidden="true" /><span className="hidden sm:inline">Print</span></Button>
                <Button onClick={handleDownload} size="sm" className="gap-2 bg-orange-600 text-white hover:bg-orange-700"><Download className="size-4" aria-hidden="true" /><span className="hidden sm:inline">Download</span></Button>
                <Button variant="ghost" size="icon" aria-label="Close preview" onClick={closePreview}><X className="size-4" aria-hidden="true" /></Button>
              </div>
            </header>
            <iframe ref={iframeRef} src={previewUrl} title="Translated Hindi PDF" className="min-h-0 flex-1 bg-slate-100" />
          </section>
        </div>
      )}
    </main>
  )
}
