/** Grid of analysis module cards for the dashboard (P1-20, wired P3-43a).
 *
 * Seven modules: Pharmacogenomics, Nutrigenomics, Cancer, Cardiovascular,
 * APOE (gated), Carrier Status, Ancestry. Cards show real finding counts,
 * top finding text, and evidence stars from the findings summary API.
 */

import {
  Pill,
  Apple,
  ShieldAlert,
  HeartPulse,
  Brain,
  Baby,
  Globe,
} from 'lucide-react'
import ModuleCard from './ModuleCard'
import { useFindingsSummary } from '@/api/findings'
import type { FindingSummaryItem } from '@/types/findings'

const MODULE_CARDS = [
  {
    to: '/pharmacogenomics',
    moduleKey: 'pharmacogenomics',
    label: 'Pharmacogenomics',
    icon: Pill,
    description: 'Drug-gene interactions and metabolizer status based on CPIC guidelines.',
  },
  {
    to: '/nutrigenomics',
    moduleKey: 'nutrigenomics',
    label: 'Nutrigenomics',
    icon: Apple,
    description: 'Nutrient metabolism pathways including folate, vitamin D, and omega-3.',
  },
  {
    to: '/cancer',
    moduleKey: 'cancer',
    label: 'Cancer',
    icon: ShieldAlert,
    description: 'Cancer predisposition genes and polygenic risk scores.',
  },
  {
    to: '/cardiovascular',
    moduleKey: 'cardiovascular',
    label: 'Cardiovascular',
    icon: HeartPulse,
    description: 'Cardiovascular risk variants including familial hypercholesterolemia.',
  },
  {
    to: '/apoe',
    moduleKey: 'apoe',
    label: 'APOE',
    icon: Brain,
    description: 'APOE genotype and associated health considerations.',
    gated: true,
    gateText: 'Tap to learn more',
  },
  {
    to: '/carrier-status',
    moduleKey: 'carrier',
    label: 'Carrier Status',
    icon: Baby,
    description: 'Recessive carrier screening for conditions like CF, sickle cell, and Tay-Sachs.',
  },
  {
    to: '/ancestry',
    moduleKey: 'ancestry',
    label: 'Ancestry',
    icon: Globe,
    description: 'Ancestry composition, haplogroups, and population-matched frequencies.',
  },
] as const

function findSummary(
  modules: FindingSummaryItem[] | undefined,
  key: string,
): FindingSummaryItem | undefined {
  return modules?.find((m) => m.module === key)
}

export default function ModuleCardsGrid({ sampleId }: { sampleId: number | null }) {
  const { data: summary } = useFindingsSummary(sampleId)

  return (
    <section aria-label="Analysis modules">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {MODULE_CARDS.map((card) => {
          const moduleSummary = findSummary(summary?.modules, card.moduleKey)
          return (
            <ModuleCard
              key={card.to}
              to={card.to}
              label={card.label}
              icon={card.icon}
              description={card.description}
              gated={'gated' in card ? card.gated : undefined}
              gateText={'gateText' in card ? card.gateText : undefined}
              findingCount={moduleSummary?.count}
              maxEvidenceLevel={moduleSummary?.max_evidence_level}
              topFindingText={moduleSummary?.top_finding_text}
            />
          )
        })}
      </div>
    </section>
  )
}
