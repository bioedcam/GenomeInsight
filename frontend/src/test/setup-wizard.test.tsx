import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from './test-utils'
import SetupWizard from '@/pages/SetupWizard'
import DisclaimerStep from '@/components/setup/DisclaimerStep'
import ImportBackupStep from '@/components/setup/ImportBackupStep'
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

// ─── ImportBackupStep tests ──────────────────────────────────────

function mockDetectExisting(overrides: Record<string, unknown> = {}) {
  return {
    existing_found: false,
    has_config: false,
    has_samples: false,
    has_databases: false,
    data_dir: '/tmp/test',
    ...overrides,
  }
}

describe('ImportBackupStep', () => {
  it('shows import UI when no existing installation', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockDetectExisting()),
    })

    const onNext = vi.fn()
    const onBack = vi.fn()
    render(<ImportBackupStep onNext={onNext} onBack={onBack} />)

    await waitFor(() => {
      expect(screen.getByText('Import from Backup')).toBeInTheDocument()
    })

    // Should show drop zone
    expect(screen.getByText(/drop a .tar.gz backup file/i)).toBeInTheDocument()
    // Should show skip button
    expect(screen.getByText(/skip — start fresh/i)).toBeInTheDocument()
  })

  it('shows existing installation when detected', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve(
          mockDetectExisting({
            existing_found: true,
            has_config: true,
            has_samples: true,
            has_databases: true,
          }),
        ),
    })

    const onNext = vi.fn()
    const onBack = vi.fn()
    const onSkipToEnd = vi.fn()
    render(
      <ImportBackupStep
        onNext={onNext}
        onBack={onBack}
        onSkipToEnd={onSkipToEnd}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText('Existing Installation Detected')).toBeInTheDocument()
    })

    // Should show detection details
    expect(screen.getByText('Configuration')).toBeInTheDocument()
    expect(screen.getByText('Sample databases')).toBeInTheDocument()
    expect(screen.getByText('Reference databases')).toBeInTheDocument()
  })

  it('shows Go to Dashboard when full installation found', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve(
          mockDetectExisting({
            existing_found: true,
            has_config: true,
            has_samples: true,
            has_databases: true,
          }),
        ),
    })

    const onSkipToEnd = vi.fn()
    render(
      <ImportBackupStep
        onNext={vi.fn()}
        onBack={vi.fn()}
        onSkipToEnd={onSkipToEnd}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText('Go to Dashboard')).toBeInTheDocument()
    })
  })

  it('does not show Go to Dashboard when DBs are missing', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve(
          mockDetectExisting({
            existing_found: true,
            has_config: true,
            has_samples: false,
            has_databases: false,
          }),
        ),
    })

    render(
      <ImportBackupStep
        onNext={vi.fn()}
        onBack={vi.fn()}
        onSkipToEnd={vi.fn()}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText('Existing Installation Detected')).toBeInTheDocument()
    })

    expect(screen.queryByText('Go to Dashboard')).not.toBeInTheDocument()
  })

  it('calls onBack when Back button is clicked', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockDetectExisting()),
    })

    const onBack = vi.fn()
    render(<ImportBackupStep onNext={vi.fn()} onBack={onBack} />)

    await waitFor(() => {
      expect(screen.getByText('Import from Backup')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Back'))
    expect(onBack).toHaveBeenCalledOnce()
  })

  it('calls onNext when Skip is clicked', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockDetectExisting()),
    })

    const onNext = vi.fn()
    render(<ImportBackupStep onNext={onNext} onBack={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('Import from Backup')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText(/skip — start fresh/i))
    expect(onNext).toHaveBeenCalledOnce()
  })

  it('shows loading state while detecting', () => {
    mockFetch.mockReturnValue(new Promise(() => {})) // Never resolves
    render(<ImportBackupStep onNext={vi.fn()} onBack={vi.fn()} />)

    expect(
      screen.getByText(/checking for existing installation/i),
    ).toBeInTheDocument()
  })

  it('has accessible drop zone', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockDetectExisting()),
    })

    render(<ImportBackupStep onNext={vi.fn()} onBack={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('Import from Backup')).toBeInTheDocument()
    })

    const dropZone = screen.getByRole('button', {
      name: /select backup archive/i,
    })
    expect(dropZone).toBeInTheDocument()
    expect(dropZone).toHaveAttribute('tabindex', '0')
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
