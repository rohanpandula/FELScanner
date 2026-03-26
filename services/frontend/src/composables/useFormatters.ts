export function useFormatters() {
  function formatSize(mb: number): string {
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(2)} GB`
    }
    return `${mb.toFixed(2)} MB`
  }

  function formatSpeed(bytesPerSec: number): string {
    const mbps = bytesPerSec / 1048576
    if (mbps >= 1) {
      return `${mbps.toFixed(2)} MB/s`
    }
    const kbps = bytesPerSec / 1024
    return `${kbps.toFixed(2)} KB/s`
  }

  function formatDate(dateString: string): string {
    const date = new Date(dateString)
    return date.toLocaleString()
  }

  function formatElapsedTime(seconds: number): string {
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60

    if (hours > 0) {
      return `${hours}h ${mins}m ${secs}s`
    } else if (mins > 0) {
      return `${mins}m ${secs}s`
    }
    return `${secs}s`
  }

  function formatETA(seconds: number): string {
    if (seconds === 0 || seconds === 8640000) return '∞'

    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)

    if (hours > 0) {
      return `${hours}h ${minutes}m`
    }
    return `${minutes}m`
  }

  return {
    formatSize,
    formatSpeed,
    formatDate,
    formatElapsedTime,
    formatETA,
  }
}
