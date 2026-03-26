import { describe, it, expect } from 'vitest'
import { apiClient } from '@/api/client'

describe('API Client', () => {
  it('creates an API client instance', () => {
    expect(apiClient).toBeDefined()
    expect(apiClient.get).toBeDefined()
    expect(apiClient.post).toBeDefined()
    expect(apiClient.put).toBeDefined()
    expect(apiClient.patch).toBeDefined()
    expect(apiClient.delete).toBeDefined()
  })

  it('has correct method signatures', () => {
    expect(typeof apiClient.get).toBe('function')
    expect(typeof apiClient.post).toBe('function')
    expect(typeof apiClient.put).toBe('function')
    expect(typeof apiClient.patch).toBe('function')
    expect(typeof apiClient.delete).toBe('function')
  })
})
