import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import CloudConnectionsPage from '../CloudConnectionsPage'
import '../../i18n'

const mocks = vi.hoisted(() => ({
  listCloudConnections: vi.fn(),
  createCloudConnection: vi.fn(),
  updateCloudConnection: vi.fn(),
  deleteCloudConnection: vi.fn(),
  rotateCloudConnection: vi.fn(),
  syncCloudConnection: vi.fn(),
  getCloudConnectionAudit: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  listCloudConnections: mocks.listCloudConnections,
  createCloudConnection: mocks.createCloudConnection,
  updateCloudConnection: mocks.updateCloudConnection,
  deleteCloudConnection: mocks.deleteCloudConnection,
  rotateCloudConnection: mocks.rotateCloudConnection,
  syncCloudConnection: mocks.syncCloudConnection,
  getCloudConnectionAudit: mocks.getCloudConnectionAudit,
}))

describe('CloudConnectionsPage', () => {
  it('renders an empty state when no connections', async () => {
    mocks.listCloudConnections.mockResolvedValue({ data: { total: 0, connections: [] } })
    render(<MemoryRouter><CloudConnectionsPage /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText(/Cloud Connections/i)).toBeInTheDocument()
    })
  })

  it('renders one row per connection', async () => {
    mocks.listCloudConnections.mockResolvedValue({
      data: {
        total: 2,
        connections: [
          { id: 1, name: 'acme-prod', provider: 'anthropic',
            api_key_fingerprint: 'aaaa', last_sync_at: null, last_sync_status: null,
            last_sync_error: null, created_by_user_id: 1, created_at: '', updated_at: '' },
          { id: 2, name: 'openai-dev', provider: 'openai',
            api_key_fingerprint: 'bbbb', last_sync_at: null, last_sync_status: null,
            last_sync_error: null, created_by_user_id: 1, created_at: '', updated_at: '' },
        ],
      },
    })
    render(<MemoryRouter><CloudConnectionsPage /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('acme-prod')).toBeInTheDocument()
    })
    expect(screen.getByText('openai-dev')).toBeInTheDocument()
  })

  it('opens the add dialog and shows required fields', async () => {
    mocks.listCloudConnections.mockResolvedValue({ data: { total: 0, connections: [] } })
    render(<MemoryRouter><CloudConnectionsPage /></MemoryRouter>)
    await waitFor(() => screen.getByText(/Add Connection/i))
    fireEvent.click(screen.getByText(/Add Connection/i))
    await waitFor(() => {
      expect(screen.getByText(/Add Cloud Connection/i)).toBeInTheDocument()
    })
  })
})
