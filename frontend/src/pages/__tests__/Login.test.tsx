import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Login from '../Login'

describe('Login', () => {
  it('renders login form', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )
    expect(screen.getByPlaceholderText(/username/i)).toBeInTheDocument()
  })
})
