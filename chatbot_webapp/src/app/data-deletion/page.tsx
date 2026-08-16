import Link from 'next/link'

export const metadata = {
  title: 'Data Deletion — Social Studio',
  description: 'How to delete your data from Social Studio.',
}

export default function DataDeletion() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12 text-foreground">
      <h1 className="font-display text-3xl font-semibold tracking-tight">Data Deletion</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated: 7 June 2026</p>

      <div className="mt-8 space-y-6 text-sm leading-relaxed text-muted-foreground [&_h2]:mt-8 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-foreground [&_strong]:text-foreground">
        <p>
          You are in control of your data in Social Studio. This page explains how to remove it.
        </p>

        <h2>Disconnect a social account</h2>
        <p>
          Go to <strong>Studio → Sources</strong>, find the Facebook or Instagram account, and choose
          <strong> Disconnect</strong>. This immediately deletes the stored access token for that account and the
          sources created from it. We retain no further access to that account.
        </p>

        <h2>Delete your account and all data</h2>
        <p>To permanently delete your Social Studio account and everything associated with it:</p>
        <ol className="list-decimal space-y-1 pl-5">
          <li>Disconnect any connected social accounts (above).</li>
          <li>Email <strong>privacy@cgrigoriadis.online</strong> from your account email with the subject
            <strong> &ldquo;Delete my account&rdquo;</strong>, or include your account email and the Facebook
            user ID if you signed in with Facebook.</li>
        </ol>
        <p>
          We will permanently delete your account, conversations, drafts, generated images, connected-account
          tokens, comments, and all related records within <strong>30 days</strong>, and confirm by email. This
          deletion is irreversible.
        </p>

        <h2>What gets deleted</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>Your profile (name, email) and login credentials.</li>
          <li>All access tokens for connected Facebook/Instagram accounts.</li>
          <li>Drafts, scheduled posts, generated images, ledger entries, conversations, and ingested sources.</li>
        </ul>
        <p>
          Content you previously published to your own Facebook Page or Instagram account lives on those
          platforms and must be deleted there directly.
        </p>

        <h2>Contact</h2>
        <p>For any data-deletion request or question: <strong>privacy@cgrigoriadis.online</strong>.</p>
      </div>

      <p className="mt-10 text-xs text-muted-foreground">
        <Link href="/" className="text-primary underline">← Back to Social Studio</Link>
      </p>
    </main>
  )
}
