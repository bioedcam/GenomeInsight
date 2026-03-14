/** Shared EvidenceStars component for displaying star-based evidence levels. */

export default function EvidenceStars({ level }: { level: number }) {
  const stars = Math.max(0, Math.min(4, level))
  return (
    <span
      className="text-xs text-muted-foreground"
      role="img"
      aria-label={`${stars} of 4 stars evidence`}
    >
      {"★".repeat(stars)}
      {"☆".repeat(4 - stars)}
    </span>
  )
}
