/** Column definitions for the variant table (P1-15a). */

import { createColumnHelper } from "@tanstack/react-table"
import type { VariantRow } from "@/types/variants"

const col = createColumnHelper<VariantRow>()

/** Pinned conflict flag column — non-hideable per PRD. */
export const conflictColumn = col.accessor("evidence_conflict", {
  id: "evidence_conflict",
  header: "",
  size: 36,
  minSize: 36,
  maxSize: 36,
  enableHiding: false,
  cell: (info) => {
    const val = info.getValue()
    if (val === true) return "\u26A0" // ⚠ amber flag
    return ""
  },
})

export const allColumns = [
  conflictColumn,
  col.accessor("rsid", {
    header: "rsID",
    size: 120,
    cell: (info) => info.getValue(),
  }),
  col.accessor("chrom", {
    header: "Chr",
    size: 60,
    cell: (info) => info.getValue(),
  }),
  col.accessor("pos", {
    header: "Position",
    size: 110,
    cell: (info) => info.getValue()?.toLocaleString() ?? "",
  }),
  col.accessor("genotype", {
    header: "Genotype",
    size: 90,
    cell: (info) => info.getValue(),
  }),
  col.accessor("ref", {
    header: "Ref",
    size: 60,
    cell: (info) => info.getValue() ?? "",
  }),
  col.accessor("alt", {
    header: "Alt",
    size: 60,
    cell: (info) => info.getValue() ?? "",
  }),
  col.accessor("zygosity", {
    header: "Zygosity",
    size: 90,
    cell: (info) => info.getValue() ?? "",
  }),
  col.accessor("gene_symbol", {
    header: "Gene",
    size: 100,
    cell: (info) => info.getValue() ?? "",
  }),
  col.accessor("consequence", {
    header: "Consequence",
    size: 150,
    cell: (info) => info.getValue() ?? "",
  }),
  col.accessor("clinvar_significance", {
    header: "ClinVar",
    size: 140,
    cell: (info) => info.getValue() ?? "",
  }),
  col.accessor("clinvar_review_stars", {
    header: "Review",
    size: 70,
    cell: (info) => {
      const stars = info.getValue()
      if (stars == null) return ""
      const clamped = Math.max(0, Math.min(4, stars))
      return "\u2605".repeat(clamped) + "\u2606".repeat(4 - clamped)
    },
  }),
  col.accessor("gnomad_af_global", {
    header: "gnomAD AF",
    size: 100,
    cell: (info) => {
      const val = info.getValue()
      if (val == null) return ""
      return val < 0.0001 ? val.toExponential(2) : val.toFixed(4)
    },
  }),
  col.accessor("rare_flag", {
    header: "Rare",
    size: 60,
    cell: (info) => (info.getValue() === true ? "Yes" : ""),
  }),
  col.accessor("cadd_phred", {
    header: "CADD",
    size: 70,
    cell: (info) => info.getValue()?.toFixed(1) ?? "",
  }),
  col.accessor("sift_score", {
    header: "SIFT",
    size: 70,
    cell: (info) => info.getValue()?.toFixed(3) ?? "",
  }),
  col.accessor("sift_pred", {
    header: "SIFT Pred",
    size: 90,
    cell: (info) => info.getValue() ?? "",
  }),
  col.accessor("polyphen2_hsvar_score", {
    header: "PolyPhen2",
    size: 90,
    cell: (info) => info.getValue()?.toFixed(3) ?? "",
  }),
  col.accessor("polyphen2_hsvar_pred", {
    header: "PP2 Pred",
    size: 90,
    cell: (info) => info.getValue() ?? "",
  }),
  col.accessor("revel", {
    header: "REVEL",
    size: 70,
    cell: (info) => info.getValue()?.toFixed(3) ?? "",
  }),
  col.accessor("annotation_coverage", {
    header: "Coverage",
    size: 80,
    cell: (info) => {
      const val = info.getValue()
      if (val == null) return ""
      // 6-bit bitmask — show as binary for now
      return val.toString(2).padStart(6, "0")
    },
  }),
  col.accessor("ensemble_pathogenic", {
    header: "Ensemble",
    size: 80,
    cell: (info) => (info.getValue() === true ? "Path" : ""),
  }),
]
