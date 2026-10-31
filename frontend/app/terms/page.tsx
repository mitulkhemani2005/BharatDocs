import type { Metadata } from "next"
import LegalPage from "@/components/legal-page"
import { legalHref } from "@/lib/legal-links"

export const metadata: Metadata = {
  title: "Terms of Use | BharatDocs",
  description: "Terms for using BharatDocs PDF translation software and services.",
}

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Use">
      <section>
        <h2>1. About these terms</h2>
        <p>These terms apply when you use BharatDocs software or a BharatDocs website deployment. By selecting a PDF for conversion, you agree to these terms. If you do not agree, do not submit a document. A third party operating a hosted deployment may also provide deployment-specific terms.</p>
      </section>
      <section>
        <h2>2. What BharatDocs does</h2>
        <p>BharatDocs converts configured text fields in PDF documents into Hindi and produces a translated PDF. It is a document-processing aid. It does not provide certified translations, legal, tax, accounting, financial, or other professional advice.</p>
      </section>
      <section>
        <h2>3. Your documents and permissions</h2>
        <ul>
          <li>You must have the rights, authority, and any permissions needed to submit the PDF and process information in it, including information about other people.</li>
          <li>You are responsible for choosing an appropriate deployment. Do not upload confidential or sensitive documents to a hosted service unless you are authorized to do so and trust its operator.</li>
          <li>You retain your rights in your documents. You give the operator of the deployment permission to process the submitted PDF only to provide the requested conversion and operate that deployment.</li>
          <li>Do not use BharatDocs to violate law, infringe another person's rights, or interfere with the service or its security.</li>
        </ul>
      </section>
      <section>
        <h2>4. Translation review</h2>
        <p>Machine-generated spellings and translations can be incomplete, ambiguous, or incorrect. Review every translated name, address, amount, identifier, and layout before printing, sharing, filing, or relying on the output. You remain responsible for decisions made using a translated document.</p>
      </section>
      <section>
        <h2>5. Storage and availability</h2>
        <p>The desktop app saves the source PDF and translated copy in your local Documents/BharatDocs folders. A hosted web deployment processes files on its API server; its operator controls access, backups, and retention. The app code retains source and output copies until they are deleted by the computer or server operator. See the <a href={legalHref("privacy")}>Privacy Notice</a> for details. Do not assume that a browser download deletes the server-side copy.</p>
      </section>
      <section>
        <h2>6. Service changes and availability</h2>
        <p>The software is provided as available. Features, supported document layouts, and hosted availability may change. The operator may suspend access to protect the service, comply with law, or address misuse. Keep your own backups of documents you need.</p>
      </section>
      <section>
        <h2>7. Disclaimers and liability</h2>
        <p>To the extent permitted by applicable law, BharatDocs is provided without guarantees that a conversion will be accurate, uninterrupted, or suitable for a particular purpose. Nothing in these terms excludes a right or remedy that cannot lawfully be excluded, including rights available to consumers under applicable law.</p>
      </section>
      <section>
        <h2>8. Governing law and contact</h2>
        <p>Applicable laws govern your use of BharatDocs, subject to mandatory consumer protections and the jurisdiction of courts or authorities established by law. For questions or a terms-related request, contact the project maintainer through the <a href="https://github.com/mitulkhemani2005" target="_blank" rel="noreferrer">BharatDocs maintainer profile</a>. Do not post private documents or personal information in a public issue.</p>
      </section>
      <p className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">These are product-use terms and are not a substitute for legal advice. The project owner should have the final terms reviewed for the business entity, contact details, and jurisdictions where BharatDocs is offered.</p>
    </LegalPage>
  )
}
