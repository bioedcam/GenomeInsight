/**
 * TypeScript JSX declarations for Nightingale Web Components.
 *
 * Nightingale uses Custom Elements (Web Components) which need
 * explicit type declarations for React JSX usage.
 */

import "react"

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "nightingale-manager": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & { "reflected-attributes"?: string },
        HTMLElement
      >
      "nightingale-navigation": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          length?: string
          height?: string
          "display-start"?: string
          "display-end"?: string
        },
        HTMLElement
      >
      "nightingale-sequence": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          length?: string
          height?: string
          "display-start"?: string
          "display-end"?: string
          highlight?: string
        },
        HTMLElement
      >
      "nightingale-track": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          length?: string
          height?: string
          "display-start"?: string
          "display-end"?: string
          layout?: string
          highlight?: string
        },
        HTMLElement
      >
    }
  }
}
