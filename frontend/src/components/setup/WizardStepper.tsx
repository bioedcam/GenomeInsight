/** Wizard step progress indicator. */

import { cn } from '@/lib/utils'
import { Check } from 'lucide-react'

export interface WizardStep {
  id: string
  label: string
}

interface WizardStepperProps {
  steps: WizardStep[]
  currentStep: number
}

export default function WizardStepper({ steps, currentStep }: WizardStepperProps) {
  return (
    <nav aria-label="Setup progress" className="flex items-center justify-center gap-1">
      {steps.map((step, index) => {
        const isCompleted = index < currentStep
        const isCurrent = index === currentStep
        return (
          <div key={step.id} className="flex items-center">
            {/* Step indicator */}
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'flex h-8 w-8 items-center justify-center rounded-full text-xs font-medium transition-colors',
                  isCompleted && 'bg-primary text-primary-foreground',
                  isCurrent && 'bg-primary text-primary-foreground ring-2 ring-primary/30 ring-offset-2 ring-offset-background',
                  !isCompleted && !isCurrent && 'bg-muted text-muted-foreground',
                )}
                aria-current={isCurrent ? 'step' : undefined}
              >
                {isCompleted ? <Check className="h-4 w-4" /> : index + 1}
              </div>
              <span
                className={cn(
                  'mt-1.5 text-xs whitespace-nowrap',
                  isCurrent ? 'font-medium text-foreground' : 'text-muted-foreground',
                )}
              >
                {step.label}
              </span>
            </div>
            {/* Connector line */}
            {index < steps.length - 1 && (
              <div
                className={cn(
                  'mx-2 mt-[-1rem] h-0.5 w-10 sm:w-16 transition-colors',
                  isCompleted ? 'bg-primary' : 'bg-border',
                )}
              />
            )}
          </div>
        )
      })}
    </nav>
  )
}
