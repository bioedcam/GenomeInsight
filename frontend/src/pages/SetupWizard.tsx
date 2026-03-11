/** Setup wizard — multi-step first-run configuration.
 *
 * P1-19a: Wizard shell + Step 1 (global disclaimer).
 * P1-19b: Step 2 (import from backup).
 * P1-19c: Step 3 (storage path + disk space).
 * P1-19e: Step 4 (external service credentials).
 */

import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSetupStatus } from '@/api/setup'
import DisclaimerStep from '@/components/setup/DisclaimerStep'
import ImportBackupStep from '@/components/setup/ImportBackupStep'
import CredentialsStep from '@/components/setup/CredentialsStep'
import StorageStep from '@/components/setup/StorageStep'
import WizardStepper, { type WizardStep } from '@/components/setup/WizardStepper'
import { cn } from '@/lib/utils'
import { Dna } from 'lucide-react'

/** All wizard steps — stubs will be replaced as P1-19b–g are implemented. */
const WIZARD_STEPS: WizardStep[] = [
  { id: 'disclaimer', label: 'Welcome' },
  { id: 'backup', label: 'Import' },
  { id: 'storage', label: 'Storage' },
  { id: 'credentials', label: 'Services' },
  { id: 'databases', label: 'Databases' },
  { id: 'upload', label: 'Upload' },
]

export default function SetupWizard() {
  const navigate = useNavigate()
  const { data: status, isLoading } = useSetupStatus()
  const [currentStep, setCurrentStep] = useState(0)

  // If setup is already complete, redirect to dashboard
  useEffect(() => {
    if (status && !status.needs_setup) {
      navigate('/', { replace: true })
    }
  }, [status, navigate])

  // If disclaimer already accepted, advance past step 0
  useEffect(() => {
    if (status?.disclaimer_accepted && currentStep === 0) {
      setCurrentStep(1)
    }
  }, [status?.disclaimer_accepted, currentStep])

  const handleDisclaimerAccepted = useCallback(() => {
    setCurrentStep(1)
  }, [])

  const handleNext = useCallback(() => {
    setCurrentStep((prev) => Math.min(WIZARD_STEPS.length - 1, prev + 1))
  }, [])

  const handleBack = useCallback(() => {
    setCurrentStep((prev) => Math.max(0, prev - 1))
  }, [])

  const handleSkipToEnd = useCallback(() => {
    navigate('/', { replace: true })
  }, [navigate])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Checking setup status...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
              <Dna className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-foreground">GenomeInsight</h1>
              <p className="text-xs text-muted-foreground">Setup Wizard</p>
            </div>
          </div>
        </div>
      </header>

      {/* Stepper */}
      <div className="mx-auto max-w-3xl px-6 py-6">
        <WizardStepper steps={WIZARD_STEPS} currentStep={currentStep} />
      </div>

      {/* Step content */}
      <main className="mx-auto max-w-xl px-6 pb-16">
        {currentStep === 0 && (
          <DisclaimerStep onAccepted={handleDisclaimerAccepted} />
        )}

        {currentStep === 1 && (
          <ImportBackupStep
            onNext={handleNext}
            onBack={handleBack}
            onSkipToEnd={handleSkipToEnd}
          />
        )}

        {currentStep === 2 && (
          <StorageStep onNext={handleNext} onBack={handleBack} />
        )}

        {currentStep === 3 && (
          <CredentialsStep onNext={handleNext} onBack={handleBack} />
        )}

        {currentStep > 3 && currentStep < WIZARD_STEPS.length && (
          <StepPlaceholder
            step={WIZARD_STEPS[currentStep]}
            stepNumber={currentStep}
            onBack={handleBack}
          />
        )}
      </main>
    </div>
  )
}

/** Placeholder for wizard steps not yet implemented. */
function StepPlaceholder({
  step,
  stepNumber,
  onBack,
}: {
  step: WizardStep
  stepNumber: number
  onBack: () => void
}) {
  return (
    <div className="space-y-6 text-center">
      <div className="rounded-lg border border-dashed border-border bg-muted/30 p-12">
        <p className="text-lg font-medium text-foreground">
          Step {stepNumber + 1}: {step.label}
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          This step will be implemented in a future task.
        </p>
      </div>
      <button
        type="button"
        onClick={onBack}
        className={cn(
          'rounded-lg border border-border px-5 py-2.5 text-sm font-medium',
          'text-foreground hover:bg-accent transition-colors',
          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
        )}
      >
        Back
      </button>
    </div>
  )
}
