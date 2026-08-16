'use client'

import { icons } from '@/components/icons'
import type { PendingFile } from '@/hooks/use-file-attachments'

interface AttachmentChipsProps {
  files: PendingFile[]
  onRemove: (id: string) => void
}

export function AttachmentChips({ files, onRemove }: AttachmentChipsProps) {
  if (files.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2 px-3 pt-3">
      {files.map(f => (
        <div
          key={f.id}
          className="flex items-center gap-1.5 rounded-lg bg-muted px-2.5 py-1 text-xs"
        >
          {f.preview ? (
            <img
              src={f.preview}
              alt={f.file.name}
              className="h-6 w-6 rounded object-cover"
            />
          ) : f.file.type.startsWith('image/') ? (
            <icons.image className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <icons.fileText className="h-3.5 w-3.5 text-muted-foreground" />
          )}
          <span className="max-w-32 truncate">{f.file.name}</span>
          <span className="text-muted-foreground">
            ({formatSize(f.file.size)})
          </span>
          {f.uploading && (
            <icons.loader className="h-3 w-3 animate-spin text-primary" />
          )}
          {f.error && (
            <span className="text-destructive">{f.error}</span>
          )}
          <button
            onClick={() => onRemove(f.id)}
            className="ml-0.5 text-muted-foreground hover:text-foreground"
            aria-label="Remove file"
          >
            <icons.x className="h-3 w-3" />
          </button>
        </div>
      ))}
    </div>
  )
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + 'KB'
  return (bytes / (1024 * 1024)).toFixed(1) + 'MB'
}
