import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import { I18nextProvider } from 'react-i18next'
import i18n from '../../i18n'
import Login from '../Login'

// Mock the API client
vi.mock('../../api/client', () => ({
  default: {
    post: vi.fn(),
  },
}))

describe('Login', () => {
  it('renders login form', () => {
    render(
      <BrowserRouter>
        <I18nextProvider i18n={i18n}>
          <Login />
        </I18nextProvider>
      </BrowserRouter>
    )
    expect(screen.getByPlaceholderText(/username/i)).toBeInTheDocument()
  })
})
