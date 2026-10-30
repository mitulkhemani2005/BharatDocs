export type HindiFont = "Mukta" | "Noto Sans Devanagari"

type ProcessingCallback = () => void

function getApiBase() {
  if (typeof window !== "undefined" && process.env.NEXT_PUBLIC_DESKTOP_APP === "1") {
    return window.location.origin
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
  return typeof body?.error === "string" ? body.error : fallback
}

export async function uploadAndTranslatePdf(
  file: File,
  fontFamily: HindiFont,
  onProcessing: ProcessingCallback,
): Promise<Blob> {
  const apiBase = getApiBase()
  const form = new FormData()
  form.append("file", file)

  const uploadResponse = await fetch(`${apiBase}/upload`, { method: "POST", body: form })
  if (!uploadResponse.ok) {
    throw new Error(await responseError(uploadResponse, "The PDF could not be uploaded. Please try again."))
  }

  const upload = await uploadResponse.json()
  if (typeof upload?.upload_id !== "string") {
    throw new Error("The server did not create an upload session. Please try again.")
  }

  onProcessing()
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

  return translationResponse.blob()
}
