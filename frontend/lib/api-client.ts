export type HindiFont = "Noto Sans Devanagari"

export function getApiBase() {
  if (typeof window !== "undefined" && process.env.NEXT_PUBLIC_DESKTOP_APP === "1") {
    const apiBase = new URLSearchParams(window.location.search).get("apiBase")
    return apiBase?.replace(/\/$/, "") || "http://127.0.0.1:5000"
  }

  const configuredApi = process.env.NEXT_PUBLIC_API_URL
  if (configuredApi) return configuredApi.replace(/\/$/, "")
  if (typeof window !== "undefined" && !["3000", "3001"].includes(window.location.port)) {
    return window.location.origin
  }
  return "http://127.0.0.1:5000"
}

async function responseError(response: Response, fallback: string) {
  const body = await response.json().catch(() => null)
  return typeof body?.error === "string" ? body.error : typeof body?.detail === "string" ? body.detail : fallback
}

export type Rect = [number, number, number, number]
export type TranslationArea = { name: string; rect: Rect; text_rect?: Rect | null; mode?: "translate" | "preserve"; font_size?: number | null }
export type Configuration = { id: string; name: string; page_width: number; page_height: number; font_size: number; regions: TranslationArea[] }
export type ConfigurationDraft = Omit<Configuration, "id">
export type PagePreview = { page: number; page_count: number; width: number; height: number; image: string }

function ownerHeaders(): Record<string, string> {
  const key = "bharatdocs-configuration-owner"
  let owner = localStorage.getItem(key)
  if (!owner) { owner = crypto.randomUUID(); localStorage.setItem(key, owner) }
  return { "X-Configuration-Owner": owner }
}

export async function configurationRequest<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`${getApiBase()}${path}`, {
    method, headers: { ...ownerHeaders(), "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) throw new Error(await responseError(response, "The configuration could not be loaded or saved. Please try again."))
  return response.json()
}

export async function uploadPdf(file: File): Promise<{ upload_id: string; page_count: number }> {
  if (!file.name.toLowerCase().endsWith(".pdf") || file.size > 20 * 1024 * 1024) throw new Error("Choose a PDF under 20 MB.")
  const form = new FormData()
  form.append("file", file)
  const response = await fetch(`${getApiBase()}/upload`, { method: "POST", body: form })
  if (!response.ok) throw new Error(await responseError(response, "The PDF could not be uploaded."))
  const upload = await response.json()
  if (typeof upload?.upload_id !== "string") throw new Error("The server did not create an upload session. Please try again.")
  return upload
}

export async function getPagePreview(uploadId: string, page: number): Promise<PagePreview> {
  const response = await fetch(`${getApiBase()}/pdf-page?upload_id=${encodeURIComponent(uploadId)}&page=${page}`)
  if (!response.ok) throw new Error(await responseError(response, "The page preview could not be loaded."))
  return response.json()
}

export async function translateUploadedPdf(
  uploadId: string,
  fontFamily: HindiFont,
  configurationId: string,
): Promise<Blob> {
  if (!configurationId) throw new Error("Create or select a saved configuration before translating a PDF.")
  const apiBase = getApiBase()
  const translationResponse = await fetch(`${apiBase}/translate-pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...ownerHeaders() },
    body: JSON.stringify({ upload_id: uploadId, font_family: fontFamily, configuration_id: configurationId }),
  })
  if (!translationResponse.ok) {
    throw new Error(await responseError(translationResponse, "The PDF could not be translated. Please try again."))
  }

  const contentType = translationResponse.headers.get("content-type") || ""
  if (!contentType.includes("application/pdf")) {
    throw new Error("The server returned an unreadable file. Please try again.")
  }

  return translationResponse.blob()
}
