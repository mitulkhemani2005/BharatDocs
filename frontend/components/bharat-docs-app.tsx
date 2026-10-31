"use client"

import type React from "react"
import { useEffect, useRef, useState } from "react"
import {
  ArrowRight,
  CheckCircle2,
  Download,
  Eye,
  FileCheck2,
  FileText,
  Languages,
  LoaderCircle,
  Printer,
  RotateCcw,
  Upload,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { configurationRequest, translateUploadedPdf, uploadPdf, type Configuration, type HindiFont } from "@/lib/api-client"
import ConfigurationEditor from "@/components/configuration-editor"
import { legalHref } from "@/lib/legal-links"

type Status = "idle" | "ready" | "uploading" | "processing" | "complete"

const MAX_FILE_SIZE = 20 * 1024 * 1024

export default function BharatDocsApp() {
  const isDesktopApp = process.env.NEXT_PUBLIC_DESKTOP_APP === "1"
  const [status, setStatus] = useState<Status>("idle")
  const fontFamily: HindiFont = "Noto Sans Devanagari"
  const [uploadId, setUploadId] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [translatedBlob, setTranslatedBlob] = useState<Blob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [hasAcceptedTerms, setHasAcceptedTerms] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [configurations, setConfigurations] = useState<Configuration[]>([])
  const [configurationId, setConfigurationId] = useState("")
  const [editor, setEditor] = useState<{ configuration: Configuration | null } | null>(null)
  const [configurationError, setConfigurationError] = useState("")
  const [configurationsLoading, setConfigurationsLoading] = useState(true)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const loadConfigurations = () => {
    setConfigurationsLoading(true)
    setConfigurationError("")
    configurationRequest<{ configurations: Configuration[] }>("/configurations")
      .then(result => {
        setConfigurations(result.configurations)
        const saved = localStorage.getItem("bharatdocs-selected-configuration")
        setConfigurationId(result.configurations.some(item => item.id === saved) ? saved! : "")
      })
      .catch(caught => setConfigurationError(caught.message))
      .finally(() => setConfigurationsLoading(false))
  }
  useEffect(loadConfigurations, [])
  const chooseConfiguration = (id: string) => {
    setConfigurationId(id)
    localStorage.setItem("bharatdocs-selected-configuration", id)
  }

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
    if (!configurationId) {
      setError("Create or select a saved configuration before translating a PDF.")
      return
    }
    setSelectedFile(file)
    setError(null)
    setTranslatedBlob(null)
    if (!uploadId) return
    setStatus("processing")

    try {
      const blob = await translateUploadedPdf(uploadId, fontFamily, configurationId)
      setTranslatedBlob(blob)
      setStatus("complete")
    } catch (caughtError) {
      setStatus("idle")
      setError(caughtError instanceof Error ? caughtError.message : "Something went wrong. Please try again.")
    }
  }

  const selectFile = async (file?: File) => {
    if (!file || isBusy) return
    setError(null)
    if (!isDesktopApp && !hasAcceptedTerms) {
      setError("Please confirm you have permission to submit this PDF and review the Terms and Privacy Notice.")
      return
    }
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setStatus("idle")
      setSelectedFile(null)
      setUploadId(null)
      setTranslatedBlob(null)
      setError("Choose a PDF file to continue.")
      return
    }
    if (file.size > MAX_FILE_SIZE) {
      setStatus("idle")
      setSelectedFile(null)
      setUploadId(null)
      setTranslatedBlob(null)
      setError("This file is larger than 20 MB. Choose a smaller PDF.")
      return
    }
    setSelectedFile(file)
    setUploadId(null)
    setTranslatedBlob(null)
    setStatus("uploading")
    try {
      const uploaded = await uploadPdf(file)
      setUploadId(uploaded.upload_id)
      setStatus("ready")
    } catch (caught) {
      setStatus("idle")
      setError(caught instanceof Error ? caught.message : "The PDF could not be uploaded.")
    }
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
    setUploadId(null)
    setTranslatedBlob(null)
    setError(null)
    closePreview()
  }

  const isBusy = status === "uploading" || status === "processing"
  const canTranslate = !!uploadId && !!configurationId && !configurationsLoading && !configurationError
  const canUpload = !isBusy && (isDesktopApp || hasAcceptedTerms)
  const resetResult = () => { setTranslatedBlob(null); setStatus(uploadId ? "ready" : "idle"); setError(null); closePreview() }

  return (
    <main className="min-h-screen bg-white text-slate-900">
      <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 pb-6 sm:px-8">
        <header className="flex items-center justify-between border-b border-slate-200 py-4">
          <a href="#home" className="flex items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500">
            <img
              src={process.env.NEXT_PUBLIC_DESKTOP_APP === "1" ? "./brand-mark.svg" : "/brand-mark.svg"}
              alt=""
              className="size-10 rounded-xl"
            />
            <span className="text-[17px] font-semibold tracking-tight text-slate-950">BharatDocs</span>
          </a>
          <div className="hidden items-center gap-2 text-sm font-medium text-slate-500 sm:flex">
            <Languages className="size-4 text-orange-600" aria-hidden="true" />
            <span lang="en">English</span>
            <ArrowRight className="size-3.5 text-slate-400" aria-hidden="true" />
            <span className="font-hindi text-[15px] text-slate-800" lang="hi">हिंदी</span>
          </div>
        </header>

        <section id="home" className="mx-auto grid w-full flex-1 items-center gap-12 py-12 lg:grid-cols-[1fr_0.82fr] lg:gap-20 lg:py-16">
          <div className="mx-auto w-full max-w-xl lg:mx-0">
            <p className="mb-4 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">PDF translation</p>
            <h1 className="max-w-xl text-4xl font-semibold leading-[1.12] tracking-[-0.04em] text-slate-950 sm:text-5xl lg:text-[3.35rem]">
              Your documents, in <span className="text-[#17365d]">clear Hindi.</span>
            </h1>
            <p className="mt-5 max-w-lg text-base leading-7 text-slate-600 sm:text-[17px]">
              Upload a bill or PDF and get a translated copy with readable Devanagari text, ready to preview and download.
            </p>

            <div
              onDragEnter={(event) => { event.preventDefault(); setIsDragging(true) }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setIsDragging(false) }}
              onDrop={handleDrop}
              className={`mt-8 rounded-2xl border bg-white p-5 transition sm:p-6 ${isDragging ? "border-[#17365d] ring-4 ring-slate-100" : "border-slate-200 shadow-sm"}`}
              aria-live="polite"
            >
              {uploadId && <div className="mb-5 space-y-3 border-b border-slate-200 pb-5">
                <label className="grid gap-2 text-sm font-semibold" htmlFor="configuration-select">Translation configuration
                  <select id="configuration-select" value={configurationId} disabled={isBusy || configurationsLoading} onChange={event => { chooseConfiguration(event.target.value); resetResult() }} className="h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-normal">
                    <option value="" disabled>Select a configuration</option>
                    {configurations.map(configuration => <option key={configuration.id} value={configuration.id}>{configuration.name}</option>)}
                  </select>
                </label>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" disabled={isBusy || configurationsLoading || !!configurationError} onClick={() => setEditor({ configuration: null })}>New configuration</Button>
                  {configurationId && <Button variant="outline" size="sm" disabled={isBusy} onClick={() => setEditor({ configuration: configurations.find(item => item.id === configurationId) || null })}>Edit / delete</Button>}
                </div>
                <p className="text-xs leading-5 text-slate-500">{configurations.length === 0 ? "Create a configuration using this PDF to select translation areas." : "Choose a saved configuration for this PDF. Its selected areas apply to every page."}</p>
                {configurationError && <p role="alert" className="text-xs text-red-700">{configurationError} <button onClick={loadConfigurations} className="underline">Retry loading configurations</button></p>}
              </div>}
              {(status === "idle" || status === "ready") && !isDesktopApp && (
                <div className="mb-4 flex items-start gap-3 rounded-xl bg-slate-50 px-3.5 py-3">
                  <input
                    id="accept-terms"
                    type="checkbox"
                    checked={hasAcceptedTerms}
                    onChange={(event) => { setHasAcceptedTerms(event.target.checked); setError(null) }}
                    className="mt-1 size-4 shrink-0 accent-[#17365d]"
                  />
                  <p className="text-xs leading-5 text-slate-600">
                    <label htmlFor="accept-terms" className="cursor-pointer">I confirm I have permission to submit this document and agree to the </label>
                    <a href={legalHref("terms")} className="font-semibold text-[#17365d] underline underline-offset-2">Terms</a>
                    <span> and acknowledge the </span>
                    <a href={legalHref("privacy")} className="font-semibold text-[#17365d] underline underline-offset-2">Privacy Notice</a>.
                  </p>
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
                    <Button onClick={handleDownload} className="h-11 flex-1 gap-2 bg-[#17365d] text-white hover:bg-[#102846]">
                      <Download className="size-4" aria-hidden="true" /> Download PDF
                    </Button>
                    <Button onClick={handlePreview} variant="outline" className="h-11 flex-1 gap-2 border-slate-200 bg-white">
                      <Eye className="size-4" aria-hidden="true" /> Preview
                    </Button>
                    <Button onClick={handleReset} variant="outline" className="h-11 gap-2 border-slate-200 bg-white sm:flex-none">
                      <RotateCcw className="size-4" aria-hidden="true" /> New PDF
                    </Button>
                  </div>
                  <p className="text-xs leading-5 text-slate-500">
                    {isDesktopApp ? (
                      "The source and translated PDFs are saved in Documents/BharatDocs on this computer."
                    ) : (
                      <>The connected API server retains source and translated copies. See the <a href={legalHref("privacy")} className="font-medium text-[#17365d] underline underline-offset-2">Privacy Notice</a>.</>
                    )}
                  </p>
                </div>
              ) : isBusy ? (
                <div className="py-2">
                  <div className="flex items-center gap-3">
                      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-slate-100 text-[#17365d]">
                      {status === "uploading" ? <Upload className="size-5" aria-hidden="true" /> : <LoaderCircle className="size-5 animate-spin" aria-hidden="true" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <h2 className="font-semibold text-slate-900">{status === "uploading" ? "Uploading your PDF…" : "Translating into Hindi…"}</h2>
                      <p className="mt-1 truncate text-sm text-slate-500">{selectedFile?.name}</p>
                    </div>
                  </div>
                  <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div className={`h-full rounded-full bg-[#17365d] transition-all duration-700 ${status === "uploading" ? "w-1/3" : "w-4/5 animate-pulse"}`} />
                  </div>
                  <p className="mt-3 text-center text-xs text-slate-500">This can take a little longer for multi-page PDFs.</p>
                </div>
              ) : (
                <>
                  <label
                    htmlFor="pdf-upload"
                    className={`flex flex-col items-center rounded-xl border border-dashed px-5 py-9 text-center transition has-[:focus-visible]:border-[#17365d] has-[:focus-visible]:ring-4 has-[:focus-visible]:ring-slate-100 sm:py-10 ${canUpload ? "cursor-pointer" : "cursor-not-allowed opacity-65"} ${isDragging ? "border-[#17365d] bg-slate-50" : "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50/70"}`}
                  >
                    <span className="grid size-12 place-items-center rounded-xl bg-slate-100 text-[#17365d]">
                      <Upload className="size-5" aria-hidden="true" />
                    </span>
                    <span className="mt-4 text-base font-semibold text-slate-900">{uploadId ? "Choose a different PDF" : "Choose a PDF to translate"}</span>
                    {uploadId && <span className="mt-2 block max-w-full truncate text-sm font-medium text-[#17365d]" title={selectedFile?.name}>{selectedFile?.name}</span>}
                    <span className="mt-1 text-sm text-slate-500">Drop it here or <span className="font-medium text-[#17365d] underline underline-offset-2">browse files</span></span>
                    <span className="mt-4 text-xs text-slate-500">PDF only · Up to 20 MB</span>
                    <input
                      ref={fileInputRef}
                      id="pdf-upload"
                      type="file"
                      accept=".pdf,application/pdf"
                      disabled={!canUpload}
                      onChange={handleFileChange}
                      className="sr-only"
                    />
                  </label>
                  {uploadId && <Button className="mt-4 h-11 w-full bg-[#17365d] text-white" disabled={!canTranslate} onClick={() => selectedFile && void startTranslation(selectedFile)}>Translate PDF into Hindi</Button>}
                  {error && (
                    <div className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3.5 py-3 text-sm text-red-800" role="alert">
                      <span className="mt-0.5 size-2 shrink-0 rounded-full bg-red-500" />
                      <span className="flex-1">{error}</span>
                      {selectedFile && <button className="shrink-0 font-semibold underline underline-offset-2" onClick={() => uploadId ? void startTranslation(selectedFile) : void selectFile(selectedFile)}>Retry</button>}
                    </div>
                  )}
                </>
              )}
            </div>

          </div>

          <aside className="mx-auto w-full max-w-md lg:mx-0 lg:justify-self-end">
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
              <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Simple workflow</p>
                  <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">From PDF to Hindi</h2>
                </div>
                <span className="grid size-10 place-items-center rounded-xl bg-slate-100 text-[#17365d]"><Languages className="size-5" aria-hidden="true" /></span>
              </div>
              <ol className="divide-y divide-slate-100 px-6">
                <li className="flex gap-4 py-5">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-slate-100 text-xs font-semibold text-slate-700">01</span>
                  <div><h3 className="font-semibold text-slate-800">Choose a PDF</h3><p className="mt-1 text-sm leading-6 text-slate-500">Select a bill or document from your device.</p></div>
                </li>
                <li className="flex gap-4 py-5">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-slate-100 text-xs font-semibold text-slate-700">02</span>
                  <div><h3 className="font-semibold text-slate-800">Choose a configuration</h3><p className="mt-1 text-sm leading-6 text-slate-500">Select or create a layout, then translate its selected areas into Hindi.</p></div>
                </li>
                <li className="flex gap-4 py-5">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-slate-100 text-xs font-semibold text-slate-700">03</span>
                  <div><h3 className="font-semibold text-slate-800">Preview and save</h3><p className="mt-1 text-sm leading-6 text-slate-500">Check your translated PDF, then download a copy.</p></div>
                </li>
              </ol>
              <div className="mx-6 mb-6 rounded-xl border border-slate-200 bg-white p-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-9 place-items-center rounded-lg bg-slate-100 text-[#17365d]"><FileCheck2 className="size-4" aria-hidden="true" /></span>
                  <div><p className="text-sm font-semibold text-slate-800">Readable Devanagari output</p><p className="mt-0.5 font-hindi text-[16px] font-normal leading-6 text-slate-600" lang="hi">साफ़ और स्पष्ट देवनागरी</p></div>
                </div>
              </div>
            </div>
            <p className="mt-4 px-2 text-center text-xs leading-5 text-slate-500">Please review translated names and amounts before using the document.</p>
          </aside>
        </section>

        <footer className="flex flex-col gap-3 border-t border-slate-200 pt-4 text-center text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:text-left">
          <p>© {new Date().getFullYear()} BharatDocs</p>
          <nav aria-label="Legal" className="flex justify-center gap-5">
            <a href={legalHref("terms")} className="hover:text-slate-900">Terms</a>
            <a href={legalHref("privacy")} className="hover:text-slate-900">Privacy</a>
          </nav>
        </footer>
      </div>

      {showPreview && previewUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6" role="dialog" aria-modal="true" aria-label="Translated PDF preview">
          <button aria-label="Close preview" className="absolute inset-0 cursor-default bg-slate-950/65 backdrop-blur-sm" onClick={closePreview} />
          <section className="relative flex h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
            <header className="flex min-h-14 items-center justify-between gap-3 border-b border-slate-200 px-4 sm:px-5">
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-slate-100 text-[#17365d]"><FileText className="size-4" aria-hidden="true" /></span>
                <p className="truncate text-sm font-medium text-slate-800">{selectedFile?.name}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => iframeRef.current?.contentWindow?.print()} className="gap-2 border-slate-200"><Printer className="size-4" aria-hidden="true" /><span className="hidden sm:inline">Print</span></Button>
                <Button onClick={handleDownload} size="sm" className="gap-2 bg-[#17365d] text-white hover:bg-[#102846]"><Download className="size-4" aria-hidden="true" /><span className="hidden sm:inline">Download</span></Button>
                <Button variant="ghost" size="icon" aria-label="Close preview" onClick={closePreview}><X className="size-4" aria-hidden="true" /></Button>
              </div>
            </header>
            <iframe ref={iframeRef} src={previewUrl} title="Translated Hindi PDF" className="min-h-0 flex-1 bg-slate-100" />
          </section>
        </div>
      )}
      {editor && <ConfigurationEditor configuration={editor.configuration} initialUploadId={uploadId} onClose={() => setEditor(null)} onSaved={saved => {
        setConfigurations(previous => [saved, ...previous.filter(item => item.id !== saved.id)])
        chooseConfiguration(saved.id)
        setEditor(null)
        resetResult()
      }} onDeleted={id => {
        setConfigurations(previous => previous.filter(item => item.id !== id))
        if (configurationId === id) chooseConfiguration("")
        setEditor(null)
        resetResult()
      }} />}
    </main>
  )
}
