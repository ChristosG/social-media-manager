'use client'

import { icons } from '@/components/icons'
import { useAuthBlobUrl } from '@/hooks/use-auth-blob'
import type { Attachment } from '@/lib/chat-api'

interface MessageAttachmentsProps {
  attachments: Attachment[]
  onPreview?: (attachment: Attachment) => void
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + 'KB'
  return (bytes / (1024 * 1024)).toFixed(1) + 'MB'
}

function ImageThumbnail({ att, onPreview }: { att: Attachment; onPreview?: (a: Attachment) => void }) {
  const downloadUrl = `/api/v1/chat/attachments/${att.id}/download`
  const blobUrl = useAuthBlobUrl(downloadUrl)

  return (
    <button
      type="button"
      onClick={() => onPreview?.(att)}
      className="block rounded-lg overflow-hidden border border-border hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer"
    >
      {blobUrl ? (
        <img
          src={blobUrl}
          alt={att.original_filename}
          className="max-w-48 max-h-32 object-cover"
        />
      ) : (
        <div className="flex items-center justify-center w-48 h-32 bg-muted">
          <icons.loader className="h-4 w-4 animate-spin text-muted-foreground" />
        </div>
      )}
    </button>
  )
}

export function MessageAttachments({ attachments, onPreview }: MessageAttachmentsProps) {
  if (!attachments?.length) return null

  return (
    <div className="flex flex-wrap gap-2 mb-2">
      {attachments.map(att => {
        const isImage = att.mime_type.startsWith('image/')
        const isPdf = att.mime_type === 'application/pdf'

        if (isImage) {
          return <ImageThumbnail key={att.id} att={att} onPreview={onPreview} />
        }

        return (
          <button
            key={att.id}
            type="button"
            onClick={() => onPreview?.(att)}
            className="flex items-center gap-2.5 rounded-lg border border-border px-3 py-2.5 text-sm hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer bg-background"
          >
            {isPdf ? (
              <div className="flex items-center justify-center h-8 w-8 rounded bg-red-500/10 flex-shrink-0">
                <icons.file className="h-4 w-4 text-red-500" />
              </div>
            ) : (
              <div className="flex items-center justify-center h-8 w-8 rounded bg-primary/10 flex-shrink-0">
                <icons.fileText className="h-4 w-4 text-primary" />
              </div>
            )}
            <div className="text-left min-w-0">
              <div className="font-medium truncate max-w-40">{att.original_filename}</div>
              <div className="text-xs text-muted-foreground">{formatSize(att.file_size)}</div>
            </div>
          </button>
        )
      })}
    </div>
  )
}
