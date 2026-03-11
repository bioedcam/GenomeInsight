"""Hardcoded disclaimer text for GenomeInsight.

All disclaimer, gate, and carrier status text lives here.
Referenced by the setup wizard (global disclaimer) and analysis modules
(APOE gate, carrier status).
"""

# ── Global first-launch disclaimer ────────────────────────────────────

GLOBAL_DISCLAIMER_TITLE = "Important Information About GenomeInsight"

GLOBAL_DISCLAIMER_TEXT = """\
GenomeInsight is an educational and research tool designed to help you \
explore your personal genomic data. It is NOT a medical device and has \
NOT been reviewed or approved by the FDA or any regulatory authority.

Please read and understand the following before proceeding:

1. **Not a diagnostic tool.** The information provided by GenomeInsight \
is for educational and research purposes only. It should not be used to \
diagnose, treat, cure, or prevent any disease or medical condition.

2. **Not a substitute for professional medical advice.** Always consult \
a qualified healthcare provider or certified genetic counselor before \
making any medical decisions based on genetic information. Do not \
disregard professional medical advice or delay seeking it because of \
something you have read in this application.

3. **Variant interpretation has limitations.** Genetic variant \
classifications change over time as scientific understanding evolves. \
A variant classified as "benign" today may be reclassified in the \
future, and vice versa. GenomeInsight uses publicly available databases \
that may not reflect the most current scientific consensus.

4. **Genotyping chip limitations.** Consumer genotyping chips (such as \
23andMe) test only a subset of genetic variants. A negative result does \
not mean you do not carry a particular variant — it may simply not have \
been tested. Clinical-grade genetic testing is required for definitive \
diagnostic results.

5. **Population-specific considerations.** Risk scores and frequency \
data may not be equally accurate across all ancestral populations. Many \
genetic studies have been conducted primarily in populations of European \
descent, which may limit the applicability of results to other groups.

6. **Privacy responsibility.** You are responsible for the security of \
your own genetic data. GenomeInsight runs locally on your computer and \
does not transmit your genetic data to external servers (except for \
optional PubMed literature lookups which send gene names only, never \
variant data).

7. **Emotional preparedness.** Genetic information may reveal unexpected \
findings about health risks, carrier status, or ancestry. Consider \
whether you are prepared to receive potentially sensitive information \
before proceeding.

By clicking "I Understand and Accept," you acknowledge that you have \
read and understood these limitations and agree to use GenomeInsight \
solely for educational and research purposes.\
"""

GLOBAL_DISCLAIMER_ACCEPT_LABEL = "I Understand and Accept"

# ── APOE opt-in disclosure gate ────────────────────────────────────────

APOE_GATE_TITLE = "APOE Genetic Information Disclosure"

APOE_GATE_TEXT = """\
You are about to view information about your APOE genotype. The APOE \
gene has variants (particularly the e4 allele) that have been associated \
with increased risk of late-onset Alzheimer's disease and cardiovascular \
conditions.

**Important considerations before viewing:**

- Having an APOE e4 allele does NOT mean you will develop Alzheimer's \
disease. Many people with e4 never develop the condition, and many \
people without e4 do.

- APOE genotype is only one of many factors that influence disease risk. \
Lifestyle, environment, and other genetic factors also play significant \
roles.

- This information may cause significant emotional distress. You may \
wish to have a support person available or to consult with a genetic \
counselor before viewing.

- This result is based on a consumer genotyping chip and is NOT a \
clinical diagnostic test.

**Resources:**
- National Institute on Aging: https://www.nia.nih.gov/health/alzheimers-causes-and-risk-factors/alzheimers-disease-genetics-fact-sheet
- Alzheimer's Association: https://www.alz.org/alzheimers-dementia/what-is-alzheimers/causes-and-risk-factors/genetics
- National Society of Genetic Counselors: https://findageneticcounselor.nsgc.org/

This gate cannot be dismissed. You must actively choose to view or skip \
APOE information each time you access this section.\
"""

APOE_GATE_ACCEPT_LABEL = "I Understand — Show My APOE Results"
APOE_GATE_DECLINE_LABEL = "Not Now — Skip APOE Results"

# ── Carrier status disclaimer ──────────────────────────────────────────

CARRIER_STATUS_DISCLAIMER_TITLE = "About Carrier Status Results"

CARRIER_STATUS_DISCLAIMER_TEXT = """\
Carrier status results indicate whether you carry one copy of a variant \
associated with a genetic condition. Carriers typically do not show \
symptoms of the condition themselves.

**This information is most relevant in a reproductive context.** If both \
partners carry a variant in the same gene, there may be an increased \
chance of having a child affected by the condition.

- These results are based on a consumer genotyping chip and may not \
detect all known variants in these genes.
- A negative carrier result does NOT guarantee that you are not a carrier.
- Clinical-grade carrier screening is recommended for comprehensive \
reproductive planning.
- Consult a genetic counselor for personalized interpretation of these \
results.\
"""
