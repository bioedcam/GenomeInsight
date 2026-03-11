import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from './test-utils'
import SetupWizard from '@/pages/SetupWizard'
import DisclaimerStep from '@/components/setup/DisclaimerStep'
import WizardStepper from '@/components/setup/WizardStepper'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

beforeEach(() => {
  mockFetch.mockReset()
})

// ─── Helper to mock API responses ───────────────────────────────────

function mockSetupStatus(overrides: Record<string, unknown> = {}) {
  return {
    needs_setup: true,
    disclaimer_accepted: false,
    has_databases: false,
    has_samples: false,
    data_dir: '/tmp/test',
    ...overrides,
  }
}

function mockDisclaimer() {
  return {
    title: 'Important Information About GenomeInsight',
    text: 'GenomeInsight is an educational and research tool.\n\nPlease read carefully.\n\n**Not a diagnostic tool.** This is for education only.',
    accept_label: 'I Understand and Accept',
  }
}

// ─── WizardStepper tests ────────────────────────────────────────────

describe('WizardStepper', () => {
  const steps = [
    { id: 'disclaimer', label: 'Welcome' },
    { id: 'storage', label: 'Storage' },
    { id: 'databases', label: 'Databases' },
  ]

  it('renders all step labels', () => {
    render(<WizardStepper steps={steps} currentStep={0} />)
    expect(screen.getByText('Welcome')).toBeInTheDocument()
    expect(screen.getByText('Storage')).toBeInTheDocument()
    expect(screen.getByText('Databases')).toBeInTheDocument()
  })

  it('marks current step with aria-current', () => {
    render(<WizardStepper steps={steps} currentStep={1} />)
    const stepIndicators = screen.getAllByText(/[1-3]|✓/)
    // Step 2 should have aria-current="step"
    const currentStepEl = document.querySelector('[aria-current="step"]')
    expect(currentStepEl).not.toBeNull()
  })

  it('shows check icon for completed steps', () => {
    render(<WizardStepper steps={steps} currentStep={2} />)
    // Steps 1 and 2 should be completed (have check icons)
    // Step 3 should be current
    const currentStepEl = document.querySelector('[aria-current="step"]')
    expect(currentStepEl).not.toBeNull()
    expect(currentStepEl?.textContent).toBe('3')
  })
})

// ─── DisclaimerStep tests ───────────────────────────────────────────

describe('DisclaimerStep', () => {
  it('renders disclaimer text', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockDisclaimer()),
    })

    const onAccepted = vi.fn()
    render(<DisclaimerStep onAccepted={onAccepted} />)

    await waitFor(() => {
      expect(screen.getByText('Important Information About GenomeInsight')).toBeInTheDocument()
    })
  })

  it('shows loading state initially', () => {
    mockFetch.mockReturnValue(new Promise(() => {})) // Never resolves
    render(<DisclaimerStep onAccepted={vi.fn()} />)
    // Should show a spinner (the animated div)
    expect(document.querySelector('.animate-spin')).not.toBeNull()
  })

  it('shows error state on fetch failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
    })

    render(<DisclaimerStep onAccepted={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText(/failed to load disclaimer/i)).toBeInTheDocument()
    })
  })

  it('disables checkbox until user scrolls to bottom', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockDisclaimer()),
    })

    render(<DisclaimerStep onAccepted={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('Important Information About GenomeInsight')).toBeInTheDocument()
    })

    const checkbox = screen.getByRole('checkbox')
    expect(checkbox).toBeDisabled()
  })

  it('accept button is disabled when checkbox is unchecked', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockDisclaimer()),
    })

    render(<DisclaimerStep onAccepted={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('Important Information About GenomeInsight')).toBeInTheDocument()
    })

    const acceptButton = screen.getByRole('button', { name: /i understand and accept/i })
    expect(acceptButton).toBeDisabled()
  })

  it('renders markdown bold text correctly', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockDisclaimer()),
    })

    render(<DisclaimerStep onAccepted={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('Not a diagnostic tool.')).toBeInTheDocument()
    })

    // The bold text should be in a <strong> element
    const strongEl = screen.getByText('Not a diagnostic tool.')
    expect(strongEl.tagName).toBe('STRONG')
  })
})

// ─── SetupWizard integration tests ──────────────────────────────────

describe('SetupWizard', () => {
  it('shows loading state while checking setup status', () => {
    mockFetch.mockReturnValue(new Promise(() => {}))
    render(<SetupWizard />)
    expect(screen.getByText(/checking setup status/i)).toBeInTheDocument()
  })

  it('shows wizard with stepper and disclaimer step', async () => {
    // Mock setup status
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockSetupStatus()),
      })
      // Mock disclaimer
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockDisclaimer()),
      })

    render(<SetupWizard />)

    await waitFor(() => {
      expect(screen.getByText('GenomeInsight')).toBeInTheDocument()
      expect(screen.getByText('Setup Wizard')).toBeInTheDocument()
    })

    // Stepper should show all steps
    expect(screen.getByText('Welcome')).toBeInTheDocument()
    expect(screen.getByText('Import')).toBeInTheDocument()
    expect(screen.getByText('Storage')).toBeInTheDocument()
  })

  it('shows all 6 wizard step labels in stepper', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockSetupStatus()),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockDisclaimer()),
      })

    render(<SetupWizard />)

    await waitFor(() => {
      expect(screen.getByText('Welcome')).toBeInTheDocument()
    })

    expect(screen.getByText('Import')).toBeInTheDocument()
    expect(screen.getByText('Storage')).toBeInTheDocument()
    expect(screen.getByText('Services')).toBeInTheDocument()
    expect(screen.getByText('Databases')).toBeInTheDocument()
    expect(screen.getByText('Upload')).toBeInTheDocument()
  })
})
