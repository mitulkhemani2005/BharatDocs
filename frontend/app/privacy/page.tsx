import type { Metadata } from "next"
import LegalPage from "@/components/legal-page"

export const metadata: Metadata = {
  title: "Privacy Notice | BharatDocs",
  description: "How BharatDocs handles PDFs and related information.",
}

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Notice">
      <section>
        <h2>1. Who handles your data</h2>
        <p>BharatDocs is software that can run on your computer or be hosted as a website and API. For the desktop app, you control the computer and its stored files. For a hosted website, the operator of that deployment controls the API server and its storage. If you self-host BharatDocs, you or your organization are the operator.</p>
      </section>
      <section>
        <h2>2. Information processed</h2>
        <p>When you use the conversion feature, BharatDocs processes the PDF you choose, its file name, and text extracted from configured regions so it can create a translated PDF. The document may contain personal information that you or another person placed in it. The app does not require an account.</p>
      </section>
      <section>
        <h2>3. Why the PDF is processed</h2>
        <p>The PDF and extracted text are used to validate the document, translate configured fields, create the output PDF, and handle errors or support requests. The bundled translation model runs on the computer or API server providing BharatDocs; the application code does not send document text to an external translation API.</p>
      </section>
      <section>
        <h2>4. Where files are stored and for how long</h2>
        <ul>
          <li><strong>Desktop app:</strong> source PDFs are saved under Documents/BharatDocs/Input and translated PDFs under Documents/BharatDocs/Output on your computer. Temporary working files are removed after successful conversion; abandoned work sessions are cleaned up after two hours when a later upload is processed. The saved Input and Output copies remain until you delete them.</li>
          <li><strong>Hosted website:</strong> the browser sends the PDF to the API server for conversion. The server saves retained copies in its Documents/BharatDocs/Input and Output folders. Those copies remain until the server operator deletes them. Temporary work sessions are removed after successful conversion; abandoned sessions are cleaned up after two hours when a later upload is processed.</li>
          <li>A download to your device does not remove a retained server-side copy. The hosting provider may also process routine connection and diagnostic information under its own terms.</li>
        </ul>
      </section>
      <section>
        <h2>5. Sharing and security</h2>
        <p>BharatDocs does not include document sharing or an external translation provider. The PDF is available to the person or organization that controls the computer or API server and to its hosting infrastructure as needed to run the deployment. A hosted operator should use access controls and HTTPS. The software does not provide end-to-end encryption, choose the hosting provider, or control that provider's systems.</p>
      </section>
      <section>
        <h2>6. Your choices and requests</h2>
        <p>For the desktop app, delete source and output copies from the folders above when you no longer need them. For a hosted deployment, contact its operator to ask about access or deletion of server-side copies. If your request concerns a BharatDocs-operated deployment, use the <a href="https://github.com/mitulkhemani2005" target="_blank" rel="noreferrer">project maintainer profile</a>. Do not send PDFs or sensitive details through public issues. Rights and request procedures depend on the laws that apply to the deployment.</p>
      </section>
      <section>
        <h2>7. Children and third-party information</h2>
        <p>Only submit information about another person when you have a valid reason and authority to do so. Do not submit a child's personal information unless you are authorized and the deployment is appropriate for that use.</p>
      </section>
      <section>
        <h2>8. Updates</h2>
        <p>This notice may be updated when the software or its data handling changes. The current version and its update date will be available on this page. A hosted operator may publish a separate notice for its deployment.</p>
      </section>
      <p className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">This notice describes the current application behavior. The project owner or deployment operator should have it reviewed against their actual hosting, contact, retention, and legal requirements before commercial use.</p>
    </LegalPage>
  )
}
