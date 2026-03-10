import { useSearchParams } from "react-router-dom"
import VariantTable from "@/components/variant-table/VariantTable"

export default function VariantExplorer() {
  const [searchParams] = useSearchParams()
  const sampleId = searchParams.get("sample_id")
    ? Number(searchParams.get("sample_id"))
    : null

  return (
    <div className="flex flex-col h-[calc(100vh-40px)]">
      <div className="px-4 py-3 border-b border-border">
        <h1 className="text-xl font-semibold">Variant Explorer</h1>
      </div>
      <VariantTable sampleId={sampleId} />
    </div>
  )
}
