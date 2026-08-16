'use client'
import { useState, useCallback, useRef } from 'react'

export interface PendingFile {
  file: File
  id: string
  preview?: string
  uploading: boolean
  progress: number
  serverId?: string
  error?: string
}

export function useFileAttachments() {
  const [files, setFiles] = useState<PendingFile[]>([])
  const filesRef = useRef(files)
  filesRef.current = files

  // Track in-flight upload promises so we can await them on send
  const uploadPromises = useRef<Map<string, Promise<void>>>(new Map())

  /**
   * Add files and optionally start uploading them immediately.
   * When uploadFn is provided, each file is uploaded right away so backend
   * processing begins while the user is still typing their message.
   */
  const addFiles = useCallback((
    newFiles: File[],
    uploadFn?: (file: File) => Promise<{ id: string }>
  ) => {
    const pending: PendingFile[] = newFiles.map(file => ({
      file,
      id: crypto.randomUUID(),
      preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
      uploading: !!uploadFn,
      progress: 0,
    }))
    setFiles(prev => [...prev, ...pending])

    // Fire uploads immediately if uploadFn provided
    if (uploadFn) {
      for (const p of pending) {
        const promise = uploadFn(p.file)
          .then(result => {
            setFiles(prev => prev.map(f =>
              f.id === p.id ? { ...f, uploading: false, progress: 100, serverId: result.id } : f
            ))
          })
          .catch(() => {
            setFiles(prev => prev.map(f =>
              f.id === p.id ? { ...f, uploading: false, error: 'Upload failed' } : f
            ))
          })
          .finally(() => {
            uploadPromises.current.delete(p.id)
          })
        uploadPromises.current.set(p.id, promise)
      }
    }
  }, [])

  const removeFile = useCallback((id: string) => {
    setFiles(prev => {
      const file = prev.find(f => f.id === id)
      if (file?.preview) URL.revokeObjectURL(file.preview)
      return prev.filter(f => f.id !== id)
    })
    // Stop tracking this upload — if it completes on the backend, the
    // attachment is never linked to a message (harmless orphan).
    uploadPromises.current.delete(id)
  }, [])

  const clearAll = useCallback(() => {
    setFiles(prev => {
      prev.forEach(f => { if (f.preview) URL.revokeObjectURL(f.preview) })
      return []
    })
    uploadPromises.current.clear()
  }, [])

  /**
   * Wait for any in-flight uploads to finish, then return server IDs of
   * files that are still in state (i.e. not removed by the user).
   */
  const waitForUploads = useCallback(async (): Promise<string[]> => {
    await Promise.allSettled(Array.from(uploadPromises.current.values()))
    return filesRef.current
      .filter(f => f.serverId && !f.error)
      .map(f => f.serverId!)
  }, [])

  return {
    files,
    addFiles,
    removeFile,
    clearAll,
    waitForUploads,
    hasFiles: files.length > 0,
    hasUploading: files.some(f => f.uploading),
  }
}
