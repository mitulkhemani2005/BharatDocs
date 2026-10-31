import type { ReactNode } from "react"
import Link from "next/link"
import { legalHref } from "@/lib/legal-links"

export default function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="min-h-screen bg-white text-slate-800">
      <div className="mx-auto flex min-h-screen w-full max-w-4xl flex-col px-5 sm:px-8">
        <header className="flex items-center justify-between border-b border-slate-200 py-5">
          <Link href={legalHref("")} className="flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#17365d]">
            <img src={process.env.NEXT_PUBLIC_DESKTOP_APP === "1" ? "./brand-mark.svg" : "/brand-mark.svg"} alt="" className="size-9 rounded-lg" />
            <span className="font-semibold tracking-tight text-slate-950">BharatDocs</span>
          </Link>
          <Link href={legalHref("")} className="text-sm font-medium text-slate-600 hover:text-slate-950">Back to app</Link>
        </header>

        <article className="flex-1 py-10 sm:py-14">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">BharatDocs</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{title}</h1>
          <p className="mt-3 text-sm text-slate-500">Last updated 31 October 2026</p>
          <div className="mt-9 space-y-8 text-[15px] leading-7 text-slate-700 [&_h2]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:tracking-tight [&_h2]:text-slate-950 [&_a]:font-medium [&_a]:text-[#17365d] [&_a]:underline [&_a]:underline-offset-4 [&_li]:ml-5 [&_li]:list-disc [&_ul]:mt-2 [&_ul]:space-y-1">
            {children}
          </div>
        </article>

        <footer className="flex flex-col gap-3 border-t border-slate-200 py-5 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span>© {new Date().getFullYear()} BharatDocs</span>
          <nav aria-label="Legal" className="flex gap-5">
            <Link href={legalHref("terms")} className="hover:text-slate-900">Terms</Link>
            <Link href={legalHref("privacy")} className="hover:text-slate-900">Privacy</Link>
          </nav>
        </footer>
      </div>
    </main>
  )
}
