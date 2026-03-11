/** Setup wizard types. */

export interface SetupStatus {
  needs_setup: boolean
  disclaimer_accepted: boolean
  has_databases: boolean
  has_samples: boolean
  data_dir: string
}

export interface DisclaimerData {
  title: string
  text: string
  accept_label: string
}

export interface AcceptDisclaimerResult {
  accepted: boolean
  accepted_at: string
}
