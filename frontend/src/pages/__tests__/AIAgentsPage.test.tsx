import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import AIAgentsPage from '../AIAgentsPage'
import '../../i18n'

const { mockListAIAgents, mockGetAIAgentsStats } = vi.hoisted(() => ({
  mockListAIAgents: vi.fn(),
  mockGetAIAgentsStats: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  listAIAgents: mockListAIAgents,
  getAIAgentsStats: mockGetAIAgentsStats,
  triggerAIAgentScan: vi.fn(),
  getAIAgent: vi.fn(),
  claimAIAgent: vi.fn(),
}))

const baseStats = { total: 0, active: 0, critical_risk: 0, no_owner: 0 }

describe('AIAgentsPage', () => {
  it('renders stat cards with stats from API', async () => {
    mockListAIAgents.mockResolvedValue({ data: { agents: [] } })
    mockGetAIAgentsStats.mockResolvedValue({
      data: { total: 5, active: 3, critical_risk: 1, no_owner: 2 },
    })

    render(
      <MemoryRouter>
        <AIAgentsPage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Total AI Agents')).toBeInTheDocument()
    })
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('renders agent name in the list tab after switching to it', async () => {
    mockListAIAgents.mockResolvedValue({
      data: {
        agents: [
          {
            id: 1,
            agent_name: 'TestAgent',
            framework: 'langchain',
            model: 'claude-3',
            risk_level: 'low',
            status: 'active',
          },
        ],
      },
    })
    mockGetAIAgentsStats.mockResolvedValue({ data: { ...baseStats, total: 1, active: 1 } })

    render(
      <MemoryRouter>
        <AIAgentsPage />
      </MemoryRouter>
    )

    // Wait for the page to finish initial load before switching tabs.
    await waitFor(() => {
      expect(screen.getByText('Total AI Agents')).toBeInTheDocument()
    })

    // Switch to the List tab (default is Overview).
    fireEvent.click(screen.getByRole('tab', { name: 'List' }))

    await waitFor(() => {
      expect(screen.getByText('TestAgent')).toBeInTheDocument()
    })
  })
})
