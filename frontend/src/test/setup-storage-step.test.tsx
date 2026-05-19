/** Step 15 — Setup wizard disk-space pre-check (Plan §12.1, ADNA-00d).
 *
 * Covers:
 * - Per-DB size breakdown is rendered
 * - VEP bundle ~600 MB callout names AncestryDNA v2.0 union catalog
 * - Existing "approximately 4 GB" hint remains for the high-level summary
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from './test-utils'
import StorageStep from '@/components/setup/StorageStep'

const mockFetch = vi.fn()

beforeEach(() => {
  mockFetch.mockReset()
  vi.stubGlobal('fetch', mockFetch)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function mockStorageInfo() {
  return {
    data_dir: '/home/test/.genomeinsight',
    free_space_bytes: 50 * 1024 * 1024 * 1024,
    free_space_gb: 50,
    total_space_bytes: 100 * 1024 * 1024 * 1024,
    total_space_gb: 100,
    status: 'ok' as const,
    message: '50.0 GB free — sufficient for GenomeInsight.',
    path_exists: true,
    path_writable: true,
  }
}

describe('StorageStep — Step 15 disk-space pre-check', () => {
  it('keeps the 4 GB headline summary', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockStorageInfo()),
    })

    render(<StorageStep onNext={vi.fn()} onBack={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('Storage Location')).toBeInTheDocument()
    })

    expect(
      screen.getByText(/approximately 4 GB of disk space/i),
    ).toBeInTheDocument()
  })

  it('renders the per-DB size breakdown panel', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockStorageInfo()),
    })

    render(<StorageStep onNext={vi.fn()} onBack={vi.fn()} />)

    const breakdown = await screen.findByTestId('storage-db-breakdown')
    expect(breakdown).toBeInTheDocument()
    expect(breakdown).toHaveTextContent(/reference database size breakdown/i)
    expect(breakdown).toHaveTextContent(/gnomAD/i)
    expect(breakdown).toHaveTextContent(/dbNSFP/i)
    expect(breakdown).toHaveTextContent(/LAI bundle/i)
  })

  it('calls out the ~600 MB VEP bundle for AncestryDNA v2.0', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockStorageInfo()),
    })

    render(<StorageStep onNext={vi.fn()} onBack={vi.fn()} />)

    const breakdown = await screen.findByTestId('storage-db-breakdown')
    expect(breakdown).toHaveTextContent(/VEP bundle/i)
    expect(breakdown).toHaveTextContent(/600 MB/)
    expect(breakdown).toHaveTextContent(/AncestryDNA v2\.0/i)
    expect(breakdown).toHaveTextContent(/0\.2\.0\+/)
  })
})
