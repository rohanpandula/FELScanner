import apiClient from './client'
import type { Collection, CollectionMovies } from './types'

export const collectionsApi = {
  // Get all Plex collections
  getCollections(): Promise<Collection[]> {
    return apiClient.get<Collection[]>('/v1/collections')
  },

  // Get movies in a collection
  getCollectionMovies(collectionName: string): Promise<CollectionMovies> {
    return apiClient.get<CollectionMovies>(`/v1/collections/${encodeURIComponent(collectionName)}/movies`)
  },

  // Add movie to collection
  addToCollection(collectionName: string, ratingKey: string): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>(`/v1/collections/${encodeURIComponent(collectionName)}/add`, {
      rating_key: ratingKey,
    })
  },

  // Remove movie from collection
  removeFromCollection(collectionName: string, ratingKey: string): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>(`/v1/collections/${encodeURIComponent(collectionName)}/remove`, {
      rating_key: ratingKey,
    })
  },

  // Verify collection integrity
  verifyCollection(collectionName: string): Promise<{ message: string; issues: string[] }> {
    return apiClient.post<{ message: string; issues: string[] }>(`/v1/collections/${encodeURIComponent(collectionName)}/verify`)
  },

  // Update all collections
  updateAllCollections(): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>('/v1/collections/update-all')
  },
}
