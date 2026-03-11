import type React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from './test-utils'
import Dashboard from '@/pages/Dashboard'
import StatusBar from '@/components/dashboard/StatusBar'
import ModuleCard from '@/components/dashboard/ModuleCard'
import ModuleCardsGrid from '@/components/dashboard/ModuleCardsGrid'
import FindingsPreview from '@/components/dashboard/FindingsPreview'
import QualityControl from '@/components/dashboard/QualityControl'
import { Pill } from 'lucide-react'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

beforeEach(() => {
  mockFetch.mockReset()
})

// ─── Helpers ────────────────────────────────────────────────

function mockSamplesResponse(samples: unknown[] = []) {
  return {
    ok: true,
    status: 200,
    json: async () => samples,
  }
}

function mockVariantCountResponse(total = 623841) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ total }),
  }
}

function mockDatabaseListResponse(downloaded = 3, total = 4) {
  return {
    ok: true,
    status: 200,
    json: async () => ({
      databases: [],
      total_size_bytes: 0,
      downloaded_count: downloaded,
      total_count: total,
    }),
  }
}

function setupFetchMocks(options: {
  samples?: unknown[]
  variantCount?: number
  dbDownloaded?: number
  dbTotal?: number
} = {}) {
  mockFetch.mockImplementation((url: string) => {
    if (url.includes('/api/samples')) {
      return Promise.resolve(mockSamplesResponse(options.samples ?? []))
    }
    if (url.includes('/api/variants/count')) {
      return Promise.resolve(mockVariantCountResponse(options.variantCount ?? 623841))
    }
    if (url.includes('/api/databases')) {
      return Promise.resolve(mockDatabaseListResponse(
        options.dbDownloaded ?? 3,
        options.dbTotal ?? 4,
      ))
    }
    return Promise.resolve({ ok: true, json: async () => ({}) })
  })
}

const SAMPLE = {
  id: 1,
  name: 'Eduardo',
  db_path: '/tmp/sample_1.db',
  file_format: '23andme_v5',
  file_hash: 'abc123',
  created_at: new Date().toISOString(),
  updated_at: null,
}

// ─── Dashboard page ─────────────────────────────────────────

describe('Dashboard', () => {
  it('shows upload prompt when no sample is active', async () => {
    setupFetchMocks()
    render(<Dashboard />)
    expect(await screen.findByText('Get Started')).toBeInTheDocument()
    expect(screen.getByText(/Upload a 23andMe raw data file/)).toBeInTheDocument()
  })

  it('renders dashboard layout when sample is active', async () => {
    setupFetchMocks({ samples: [SAMPLE], variantCount: 500000 })
    const { QueryClient, QueryClientProvider } = await import('@tanstack/react-query')
    const { MemoryRouter } = await import('react-router-dom')
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
    })
    render(<Dashboard />, {
      wrapper: ({ children }: { children: React.ReactNode }) => (
        <QueryClientProvider client={qc}>
          <MemoryRouter initialEntries={['/?sample_id=1']}>
            {children}
          </MemoryRouter>
        </QueryClientProvider>
      ),
    })
    expect(await screen.findByText('Eduardo')).toBeInTheDocument()
  })
})

// ─── StatusBar ──────────────────────────────────────────────

describe('StatusBar', () => {
  it('displays sample name and variant count', async () => {
    setupFetchMocks()
    render(<StatusBar sample={SAMPLE} variantCount={623841} />)
    expect(screen.getByText('Eduardo')).toBeInTheDocument()
    expect(screen.getByText(/623,841 SNPs/)).toBeInTheDocument()
  })

  it('shows null variant count as no SNP text', () => {
    setupFetchMocks()
    render(<StatusBar sample={SAMPLE} variantCount={null} />)
    expect(screen.getByText('Eduardo')).toBeInTheDocument()
    expect(screen.queryByText(/SNPs/)).not.toBeInTheDocument()
  })

  it('has accessible database status button', async () => {
    setupFetchMocks()
    render(<StatusBar sample={SAMPLE} variantCount={100} />)
    const dbButton = await screen.findByRole('button', { name: /Databases/i })
    expect(dbButton).toBeInTheDocument()
  })

  it('shows database dots based on download status', async () => {
    setupFetchMocks({ dbDownloaded: 2, dbTotal: 4 })
    render(<StatusBar sample={SAMPLE} variantCount={100} />)
    // Wait for database list to load
    const dbButton = await screen.findByRole('button', { name: /2 of 4/i })
    expect(dbButton).toBeInTheDocument()
  })
})

// ─── ModuleCard ─────────────────────────────────────────────

describe('ModuleCard', () => {
  it('renders with label and description', () => {
    render(
      <ModuleCard
        to="/pharmacogenomics"
        label="Pharmacogenomics"
        icon={Pill}
        description="Drug-gene interactions"
      />,
    )
    expect(screen.getByText('Pharmacogenomics')).toBeInTheDocument()
    expect(screen.getByText('Drug-gene interactions')).toBeInTheDocument()
    expect(screen.getByText('View details →')).toBeInTheDocument()
  })

  it('links to the correct route', () => {
    render(
      <ModuleCard
        to="/pharmacogenomics"
        label="Pharmacogenomics"
        icon={Pill}
        description="Test"
      />,
    )
    const link = screen.getByRole('link', { name: /Pharmacogenomics module/i })
    expect(link).toHaveAttribute('href', '/pharmacogenomics')
  })

  it('shows gate text when gated', () => {
    render(
      <ModuleCard
        to="/apoe"
        label="APOE"
        icon={Pill}
        description="Should not show"
        gated
        gateText="Tap to learn more"
      />,
    )
    expect(screen.getByText('Tap to learn more')).toBeInTheDocument()
    expect(screen.queryByText('Should not show')).not.toBeInTheDocument()
  })
})

// ─── ModuleCardsGrid ────────────────────────────────────────

describe('ModuleCardsGrid', () => {
  it('renders all 7 module cards', () => {
    render(<ModuleCardsGrid />)
    expect(screen.getByText('Pharmacogenomics')).toBeInTheDocument()
    expect(screen.getByText('Nutrigenomics')).toBeInTheDocument()
    expect(screen.getByText('Cancer')).toBeInTheDocument()
    expect(screen.getByText('Cardiovascular')).toBeInTheDocument()
    expect(screen.getByText('APOE')).toBeInTheDocument()
    expect(screen.getByText('Carrier Status')).toBeInTheDocument()
    expect(screen.getByText('Ancestry')).toBeInTheDocument()
  })

  it('has an accessible section label', () => {
    render(<ModuleCardsGrid />)
    expect(screen.getByRole('region', { name: /Analysis modules/i })).toBeInTheDocument()
  })

  it('shows APOE as gated', () => {
    render(<ModuleCardsGrid />)
    expect(screen.getByText('Tap to learn more')).toBeInTheDocument()
  })
})

// ─── FindingsPreview ────────────────────────────────────────

describe('FindingsPreview', () => {
  it('shows empty state placeholder', () => {
    render(<FindingsPreview />)
    expect(screen.getByText('High-Confidence Findings')).toBeInTheDocument()
    expect(screen.getByText('No findings yet')).toBeInTheDocument()
    expect(screen.getByText(/Run annotation/)).toBeInTheDocument()
  })

  it('has an accessible section label', () => {
    render(<FindingsPreview />)
    expect(screen.getByRole('region', { name: /High-confidence findings/i })).toBeInTheDocument()
  })
})

// ─── QualityControl ─────────────────────────────────────────

describe('QualityControl', () => {
  it('renders collapsed by default', () => {
    render(<QualityControl variantCount={623841} />)
    expect(screen.getByText('Sample QC')).toBeInTheDocument()
    expect(screen.queryByText('Total Variants')).not.toBeInTheDocument()
  })

  it('expands to show variant count', () => {
    render(<QualityControl variantCount={623841} />)
    fireEvent.click(screen.getByText('Sample QC'))
    expect(screen.getByText('Total Variants')).toBeInTheDocument()
    expect(screen.getByText('623,841')).toBeInTheDocument()
  })

  it('shows dash when variant count is null', () => {
    render(<QualityControl variantCount={null} />)
    fireEvent.click(screen.getByText('Sample QC'))
    // All three metrics show "—" when no data
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBe(3)
  })

  it('shows placeholder for Call Rate and Ti/Tv', () => {
    render(<QualityControl variantCount={100} />)
    fireEvent.click(screen.getByText('Sample QC'))
    expect(screen.getByText('Call Rate')).toBeInTheDocument()
    expect(screen.getByText('Ti/Tv Ratio')).toBeInTheDocument()
  })

  it('has accessible expand/collapse button', () => {
    render(<QualityControl variantCount={100} />)
    const button = screen.getByRole('button', { name: /Sample QC/i })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
  })

  it('collapses when clicked again', () => {
    render(<QualityControl variantCount={100} />)
    const button = screen.getByText('Sample QC')
    fireEvent.click(button)
    expect(screen.getByText('Total Variants')).toBeInTheDocument()
    fireEvent.click(button)
    expect(screen.queryByText('Total Variants')).not.toBeInTheDocument()
  })
})
