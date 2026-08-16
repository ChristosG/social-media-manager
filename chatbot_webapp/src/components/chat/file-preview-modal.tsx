'use client'

import { useEffect, useState, useCallback } from 'react'
import { icons } from '@/components/icons'
import { useAuthBlobUrl, fetchWithAuth } from '@/hooks/use-auth-blob'
import type { Attachment } from '@/lib/chat-api'

interface FilePreviewModalProps {
  attachment: Attachment
  onClose: () => void
}

export function FilePreviewModal({ attachment, onClose }: FilePreviewModalProps) {
  const [textContent, setTextContent] = useState<string | null>(null)
  const downloadUrl = `/api/v1/chat/attachments/${attachment.id}/download`
  const isImage = attachment.mime_type.startsWith('image/')
  const isPdf = attachment.mime_type === 'application/pdf'
  const isText = attachment.mime_type.startsWith('text/')

  // Authenticated blob URL for images and PDFs
  const blobUrl = useAuthBlobUrl(isImage || isPdf ? downloadUrl : null)

  // Fetch text content with auth for text files
  useEffect(() => {
    if (isText) {
      fetchWithAuth(downloadUrl)
        .then(r => {
          if (!r.ok) throw new Error(`${r.status}`)
          return r.text()
        })
        .then(setTextContent)
        .catch(() => setTextContent('[Failed to load file content]'))
    }
  }, [downloadUrl, isText])

  // Close on Escape key
  const handleKey = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
  }, [onClose])

  useEffect(() => {
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [handleKey])

  // Prevent body scroll while modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  // Authenticated download
  const handleDownload = useCallback(async () => {
    try {
      const resp = await fetchWithAuth(downloadUrl)
      if (!resp.ok) return
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = attachment.original_filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {}
  }, [downloadUrl, attachment.original_filename])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative max-w-4xl max-h-[90vh] w-full mx-4 bg-background rounded-xl shadow-2xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b flex-shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            {isImage ? (
              <icons.image className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            ) : isPdf ? (
              <icons.file className="h-4 w-4 text-red-500 flex-shrink-0" />
            ) : (
              <icons.fileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            )}
            <span className="text-sm font-medium truncate">{attachment.original_filename}</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={handleDownload}
              className="p-1.5 rounded hover:bg-accent transition-colors"
              aria-label="Download"
            >
              <icons.download className="h-4 w-4" />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded hover:bg-accent transition-colors"
              aria-label="Close preview"
            >
              <icons.x className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto">
          {isImage && (
            <div className="flex items-center justify-center p-4">
              {blobUrl ? (
                <img
                  src={blobUrl}
                  alt={attachment.original_filename}
                  className="max-w-full max-h-[80vh] object-contain"
                />
              ) : (
                <icons.loader className="h-6 w-6 animate-spin text-muted-foreground" />
              )}
            </div>
          )}

          {isPdf && (
            blobUrl ? (
              <iframe
                src={blobUrl}
                className="w-full h-[80vh]"
                title={attachment.original_filename}
              />
            ) : (
              <div className="flex items-center justify-center py-12">
                <icons.loader className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            )
          )}

          {isText && (
            <div className="p-4">
              {textContent === null ? (
                <div className="flex items-center justify-center py-8">
                  <icons.loader className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <pre className="text-sm whitespace-pre-wrap font-mono bg-muted p-4 rounded-lg overflow-x-auto">
                  {textContent}
                </pre>
              )}
            </div>
          )}

          {!isImage && !isPdf && !isText && (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <icons.file className="h-12 w-12 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Preview not available for this file type</p>
              <button
                onClick={handleDownload}
                className="text-sm text-primary hover:underline"
              >
                Download file
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
