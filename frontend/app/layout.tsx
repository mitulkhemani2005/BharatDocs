import type React from "react"
import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "BharatDocs - English to Hindi PDF Translator",
  description: "Translate configured PDF fields into Hindi with BharatDocs.",
  icons: {
    icon: process.env.NEXT_PUBLIC_DESKTOP_APP === "1" ? "./brand-mark.svg" : "/brand-mark.svg",
    apple: process.env.NEXT_PUBLIC_DESKTOP_APP === "1" ? "./apple-icon.png" : "/apple-icon.png",
  },
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
