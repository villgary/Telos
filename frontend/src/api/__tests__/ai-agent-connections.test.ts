import { describe, it, expect, vi } from 'vitest'

const { postMock, getMock, patchMock, delMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  getMock: vi.fn(),
  patchMock: vi.fn(),
  delMock: vi.fn(),
}))

vi.mock('axios', () => ({
  default: {
    post: (...args: any[]) => postMock(...args),
    get: (...args: any[]) => getMock(...args),
    patch: (...args: any[]) => patchMock(...args),
    delete: (...args: any[]) => delMock(...args),
    create: () => ({
      post: postMock, get: getMock, patch: patchMock, delete: delMock,
      interceptors: { request: { use: () => {} }, response: { use: () => {} } },
    }),
  },
}))

import {
  listCloudConnections, createCloudConnection, rotateCloudConnection,
  syncCloudConnection, deleteCloudConnection, updateCloudConnection,
  getCloudConnectionAudit,
} from '../client'

describe('cloud connection API client', () => {
  beforeEach(() => {
    postMock.mockReset()
    getMock.mockReset()
    patchMock.mockReset()
    delMock.mockReset()
  })

  it('listCloudConnections hits /ai-agents/connections', async () => {
    getMock.mockResolvedValue({ data: { total: 0, connections: [] } })
    await listCloudConnections()
    expect(getMock).toHaveBeenCalledWith('/ai-agents/connections')
  })

  it('createCloudConnection sends api_key only in POST body', async () => {
    postMock.mockResolvedValue({ data: {} })
    await createCloudConnection({ name: 'c1', provider: 'anthropic', api_key: 'sk-test' })
    expect(postMock).toHaveBeenCalledWith('/ai-agents/connections',
      { name: 'c1', provider: 'anthropic', api_key: 'sk-test' })
  })

  it('rotateCloudConnection hits /rotate', async () => {
    postMock.mockResolvedValue({ data: {} })
    await rotateCloudConnection(7, 'new-key')
    expect(postMock).toHaveBeenCalledWith('/ai-agents/connections/7/rotate',
      { api_key: 'new-key' })
  })

  it('syncCloudConnection POSTs to /sync', async () => {
    postMock.mockResolvedValue({ data: {} })
    await syncCloudConnection(3)
    expect(postMock).toHaveBeenCalledWith('/ai-agents/connections/3/sync')
  })

  it('deleteCloudConnection calls DELETE', async () => {
    delMock.mockResolvedValue({ data: {} })
    await deleteCloudConnection(5)
    expect(delMock).toHaveBeenCalledWith('/ai-agents/connections/5')
  })

  it('updateCloudConnection uses PATCH and never sends api_key', async () => {
    patchMock.mockResolvedValue({ data: {} })
    await updateCloudConnection(2, { name: 'renamed' })
    expect(patchMock).toHaveBeenCalledWith('/ai-agents/connections/2',
      { name: 'renamed' })
  })

  it('getCloudConnectionAudit passes limit/offset', async () => {
    getMock.mockResolvedValue({ data: { total: 0, entries: [] } })
    await getCloudConnectionAudit(2, 25, 50)
    expect(getMock).toHaveBeenCalledWith('/ai-agents/connections/2/audit',
      { params: { limit: 25, offset: 50 } })
  })
})
