import Link from 'next/link'

export const metadata = {
  title: 'Privacy Policy — Social Studio',
  description: 'How Social Studio collects, uses, and protects your data.',
}

export default function PrivacyPolicy() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12 text-foreground">
      <h1 className="font-display text-3xl font-semibold tracking-tight">Privacy Policy</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated: 7 June 2026</p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-muted-foreground [&_h2]:mt-8 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-foreground [&_strong]:text-foreground">
        <p>
          Social Studio (&ldquo;we&rdquo;, &ldquo;the app&rdquo;) is a social-media assistant that helps
          organizations plan, draft, and publish content to their connected Facebook and Instagram accounts.
          This policy explains what we collect, how we use it, and the choices you have.
        </p>

        <h2>Information we collect</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li><strong>Account information</strong> — your name and email address, used to create and secure your account. If you sign in with Facebook or Google, we receive your basic public profile and email from that provider.</li>
          <li><strong>Connected social accounts</strong> — when you connect a Facebook Page or Instagram account, we store the account&rsquo;s identifiers and an access token (encrypted at rest) so we can publish and read content on your behalf, only as you direct.</li>
          <li><strong>Content you create</strong> — drafts, posts, images you generate, comments, and the messages you exchange with the assistant.</li>
          <li><strong>Content from your connected accounts</strong> — posts and comments we read at your request to power scheduling, insights, and replies.</li>
        </ul>

        <h2>How we use your information</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>To provide the service: drafting and publishing posts, scheduling, and managing comments on accounts you connect.</li>
          <li>To authenticate you and keep your account secure.</li>
          <li>We do <strong>not</strong> sell your data or use your content to train third-party models.</li>
        </ul>

        <h2>How we share information</h2>
        <p>
          We share data with Meta&rsquo;s APIs strictly to perform the actions you request (e.g., publishing a
          post or reading comments on your Page). We do not share your personal data with advertisers or sell it
          to anyone. Service providers that host our infrastructure process data on our behalf under
          confidentiality obligations.
        </p>

        <h2>Storage &amp; security</h2>
        <p>
          Access tokens are encrypted at rest and never exposed to your browser. Each organization&rsquo;s data is
          isolated at the database level. We retain your data for as long as your account is active.
        </p>

        <h2>Your choices &amp; data deletion</h2>
        <p>
          You can disconnect any social account at any time in <strong>Studio → Sources</strong>, which removes its
          stored token and associated sources. To delete your account and all associated data, follow the steps on
          our{' '}
          <Link href="/data-deletion" className="text-primary underline">Data Deletion</Link> page.
        </p>

        <h2>Contact</h2>
        <p>
          Questions about this policy or your data: <strong>privacy@cgrigoriadis.online</strong>.
        </p>
      </div>

      <p className="mt-10 text-xs text-muted-foreground">
        <Link href="/" className="text-primary underline">← Back to Social Studio</Link>
      </p>
    </main>
  )
}
