import apiClient from './client'
import type { Movie, MovieListResponse, MovieFilters } from './types'

export const moviesApi = {
  // Get paginated movie list with filters
  getMovies(filters?: MovieFilters): Promise<MovieListResponse> {
    return apiClient.get<MovieListResponse>('/v1/movies', filters)
  },

  // Get single movie by ID
  getMovie(id: number): Promise<Movie> {
    return apiClient.get<Movie>(`/v1/movies/${id}`)
  },

  // Get single movie by rating key
  getMovieByRatingKey(ratingKey: string): Promise<Movie> {
    return apiClient.get<Movie>(`/v1/movies/rating-key/${ratingKey}`)
  },

  // Search movies
  searchMovies(query: string): Promise<Movie[]> {
    return apiClient.get<Movie[]>('/v1/movies/search', { q: query })
  },

  // Get movie statistics
  getStatistics(): Promise<{
    total: number
    dv_total: number
    dv_p5: number
    dv_p7: number
    dv_p8: number
    dv_p10: number
    dv_fel: number
    atmos_total: number
    resolution_4k: number
    resolution_1080p: number
  }> {
    return apiClient.get('/v1/movies/statistics')
  },
}
