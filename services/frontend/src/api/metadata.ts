import apiClient from './client'
import type { MovieMetadata, FfprobeData } from './types'

export const metadataApi = {
  // Get movie metadata with versions
  getMovieMetadata(movieId: number): Promise<MovieMetadata> {
    return apiClient.get<MovieMetadata>(`/v1/metadata/movie/${movieId}`)
  },

  // Get ffprobe data for a file
  getFfprobeData(filePath: string): Promise<FfprobeData> {
    return apiClient.post<FfprobeData>('/v1/metadata/ffprobe', { file_path: filePath })
  },

  // Refresh metadata cache for a movie
  refreshMovieMetadata(movieId: number): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>(`/v1/metadata/movie/${movieId}/refresh`)
  },

  // Clear all metadata cache
  clearMetadataCache(): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/v1/metadata/cache/clear')
  },
}
