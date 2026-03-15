/** Shared constants for cardiovascular module (P3-21). */

export const INHERITANCE_LABELS: Record<string, string> = {
  AD: "Autosomal Dominant",
  AR: "Autosomal Recessive",
  XL: "X-linked",
  XLD: "X-linked Dominant",
  XLR: "X-linked Recessive",
  MT: "Mitochondrial",
}

export const CATEGORY_CONFIG: Record<string, { label: string; badge: string }> = {
  familial_hypercholesterolemia: {
    label: "Familial Hypercholesterolemia",
    badge: "bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-300",
  },
  lipid_metabolism: {
    label: "Lipid Metabolism",
    badge: "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300",
  },
  channelopathy: {
    label: "Channelopathy",
    badge: "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300",
  },
  cardiomyopathy: {
    label: "Cardiomyopathy",
    badge: "bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300",
  },
}

export const DEFAULT_CATEGORY = {
  label: "Cardiovascular",
  badge: "bg-muted text-muted-foreground",
}

export const CATEGORY_LABELS: Record<string, string> = {
  familial_hypercholesterolemia: "Familial Hypercholesterolemia",
  lipid_metabolism: "Lipid Metabolism",
  channelopathy: "Channelopathy",
  cardiomyopathy: "Cardiomyopathy",
}
