import type React from "react"
import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "BharatDocs - English to Hindi PDF Translator",
  description: "Translate English PDF bills into readable Hindi and preview or download the translated copy.",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en-IN">
      <body className="font-sans antialiased">{children}</body>
    </html>
  )
}
