import { useSearchParams } from "react-router-dom"
import FileUpload from "@/components/upload/FileUpload"
import { useSamples } from "@/api/samples"
import { formatFileFormat, parseSampleId } from "@/lib/format"

export default function Dashboard() {
  const [searchParams] = useSearchParams()
  const activeSampleId = parseSampleId(searchParams.get("sample_id"))

  const { data: samples } = useSamples()
  const activeSample = samples?.find((s) => s.id === activeSampleId)

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {activeSample ? (
        <div className="mt-4">
          <div className="rounded-lg border bg-card p-4">
            <h2 className="text-lg font-semibold">{activeSample.name}</h2>
            <p className="text-sm text-muted-foreground mt-1">
              {formatFileFormat(activeSample.file_format)}
              {activeSample.created_at && (
                <>
                  {" · Uploaded "}
                  {new Date(activeSample.created_at).toLocaleDateString()}
                </>
              )}
            </p>
          </div>
          <p className="text-muted-foreground mt-4 text-sm">
            Sample overview and analysis summary will appear here.
          </p>
        </div>
      ) : (
        <div className="mt-6">
          <p className="text-muted-foreground mb-4">
            Upload a 23andMe raw data file to get started.
          </p>
          <FileUpload />
        </div>
      )}
    </div>
  )
}
