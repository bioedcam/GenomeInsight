/** Grid of analysis module cards for the dashboard (P1-20).
 *
 * Seven modules: Pharmacogenomics, Nutrigenomics, Cancer, Cardiovascular,
 * APOE (gated), Carrier Status, Ancestry. All cards are navigation links
 * to their respective module pages.
 *
 * In Phase 1 these show placeholder descriptions. Real finding counts
 * and top findings are wired in P3-43a.
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

const MODULE_CARDS = [
  {
    to: '/pharmacogenomics',
    label: 'Pharmacogenomics',
    icon: Pill,
    description: 'Drug-gene interactions and metabolizer status based on CPIC guidelines.',
  },
  {
    to: '/nutrigenomics',
    label: 'Nutrigenomics',
    icon: Apple,
    description: 'Nutrient metabolism pathways including folate, vitamin D, and omega-3.',
  },
  {
    to: '/cancer',
    label: 'Cancer',
    icon: ShieldAlert,
    description: 'Cancer predisposition genes and polygenic risk scores.',
  },
  {
    to: '/cardiovascular',
    label: 'Cardiovascular',
    icon: HeartPulse,
    description: 'Cardiovascular risk variants including familial hypercholesterolemia.',
  },
  {
    to: '/apoe',
    label: 'APOE',
    icon: Brain,
    description: 'APOE genotype and associated health considerations.',
    gated: true,
    gateText: 'Tap to learn more',
  },
  {
    to: '/carrier-status',
    label: 'Carrier Status',
    icon: Baby,
    description: 'Recessive carrier screening for conditions like CF, sickle cell, and Tay-Sachs.',
  },
  {
    to: '/ancestry',
    label: 'Ancestry',
    icon: Globe,
    description: 'Ancestry composition, haplogroups, and population-matched frequencies.',
  },
] as const

export default function ModuleCardsGrid() {
  return (
    <section aria-label="Analysis modules">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {MODULE_CARDS.map((card) => (
          <ModuleCard key={card.to} {...card} />
        ))}
      </div>
    </section>
  )
}
