import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import AIAgentDetailPage from '../AIAgentDetailPage'
import '../../i18n'

const { mockGetAIAgent } = vi.hoisted(() => ({
  mockGetAIAgent: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  listAIAgents: vi.fn(),
  getAIAgentsStats: vi.fn(),
  triggerAIAgentScan: vi.fn(),
  getAIAgent: mockGetAIAgent,
  claimAIAgent: vi.fn(),
}))

const unownedAgent = {
  agent_name: 'UnownedAgent',
  framework: 'langchain',
  risk_level: 'low',
  status: 'active',
  last_seen_at: '2026-06-01T00:00:00Z',
  discovered_at: '2026-05-01T00:00:00Z',
}

const ownedAgent = {
  ...unownedAgent,
  agent_name: 'OwnedAgent',
  owner_user: 'alice',
}

function renderAt(id: string) {
  return render(
    <MemoryRouter initialEntries={[`/ai-agents/${id}`]}>
      <Routes>
        <Route path="/ai-agents/:id" element={<AIAgentDetailPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('AIAgentDetailPage', () => {
  it('renders all 5 sections for an unowned agent', async () => {
    mockGetAIAgent.mockResolvedValue({ data: unownedAgent })

    renderAt('1')

    await waitFor(() => {
      expect(screen.getByText('UnownedAgent')).toBeInTheDocument()
    })
    expect(screen.getByText('Basic Information')).toBeInTheDocument()
    expect(screen.getByText('Capabilities')).toBeInTheDocument()
    expect(screen.getByText('Credentials')).toBeInTheDocument()
    expect(screen.getByText('Risk Signals')).toBeInTheDocument()
    expect(screen.getByText('Related')).toBeInTheDocument()
  })

  it('does not show claim button when owner is set', async () => {
    mockGetAIAgent.mockResolvedValue({ data: ownedAgent })

    renderAt('1')

    await waitFor(() => {
      expect(screen.getByText('OwnedAgent')).toBeInTheDocument()
    })
    expect(screen.queryByText('Claim Owner')).not.toBeInTheDocument()
    // The "owned" template interpolates {user}; the user value is what we
    // ultimately want to confirm is on screen.
    expect(screen.getByText('alice')).toBeInTheDocument()
  })
})
