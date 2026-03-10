"""Per-sample database schema.

Each sample gets its own SQLite file (sample_{id}.db). Tables are created
via create_sample_tables() when a new sample is imported — not via Alembic,
since each sample DB is a separate file created at runtime.
"""

import sqlalchemy as sa

SAMPLE_TABLES_SQL = """
-- ── Raw Variants (as parsed from 23andMe file) ─────────────────
CREATE TABLE IF NOT EXISTS raw_variants (
    rsid          TEXT NOT NULL,
    chrom         TEXT NOT NULL,
    pos           INTEGER NOT NULL,
    genotype      TEXT NOT NULL,
    PRIMARY KEY (rsid)
);
CREATE INDEX IF NOT EXISTS idx_raw_chrom_pos ON raw_variants(chrom, pos);

-- ── Annotated Variants (single wide table, 30+ columns) ────────
CREATE TABLE IF NOT EXISTS annotated_variants (
    rsid          TEXT NOT NULL PRIMARY KEY,
    chrom         TEXT NOT NULL,
    pos           INTEGER NOT NULL,
    ref           TEXT,
    alt           TEXT,
    genotype      TEXT,
    zygosity      TEXT,         -- 'hom_ref', 'het', 'hom_alt'

    -- VEP annotation (bitmask bit 0)
    gene_symbol       TEXT,
    transcript_id     TEXT,
    consequence       TEXT,     -- SO term
    hgvs_coding       TEXT,
    hgvs_protein      TEXT,
    strand            TEXT,
    exon_number       INTEGER,
    intron_number     INTEGER,
    mane_select       BOOLEAN DEFAULT 0,

    -- ClinVar (bitmask bit 1)
    clinvar_significance  TEXT,
    clinvar_review_stars  INTEGER,
    clinvar_accession     TEXT,
    clinvar_conditions    TEXT,

    -- gnomAD allele frequency (bitmask bit 2)
    gnomad_af_global      REAL,
    gnomad_af_afr         REAL,
    gnomad_af_amr         REAL,
    gnomad_af_eas         REAL,
    gnomad_af_eur         REAL,
    gnomad_af_fin         REAL,
    gnomad_af_sas         REAL,
    gnomad_homozygous_count INTEGER,
    rare_flag             BOOLEAN DEFAULT 0,
    ultra_rare_flag       BOOLEAN DEFAULT 0,

    -- dbNSFP in-silico scores (bitmask bit 3)
    cadd_phred            REAL,
    sift_score            REAL,
    sift_pred             TEXT,
    polyphen2_hsvar_score REAL,
    polyphen2_hsvar_pred  TEXT,
    revel                 REAL,
    mutpred2              REAL,
    vest4                 REAL,
    metasvm               REAL,
    metalr                REAL,
    gerp_rs               REAL,
    phylop                REAL,
    mpc                   REAL,
    primateai             REAL,

    -- Evidence & conflict
    evidence_conflict     BOOLEAN DEFAULT 0,
    ensemble_pathogenic   BOOLEAN DEFAULT 0,

    -- Annotation coverage bitmask (6-bit: VEP|ClinVar|gnomAD|dbNSFP|CPIC|GWAS)
    annotation_coverage   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_annot_chrom_pos
    ON annotated_variants(chrom, pos);
CREATE INDEX IF NOT EXISTS idx_annot_gene
    ON annotated_variants(gene_symbol);
CREATE INDEX IF NOT EXISTS idx_annot_clinvar_sig
    ON annotated_variants(clinvar_significance);
CREATE INDEX IF NOT EXISTS idx_annot_coverage
    ON annotated_variants(annotation_coverage);

-- ── Findings (unified output from all analysis modules) ────────
CREATE TABLE IF NOT EXISTS findings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    module        TEXT NOT NULL,      -- pharmacogenomics, nutrigenomics, cancer, etc.
    category      TEXT,               -- sub-category within module
    evidence_level INTEGER,           -- 1-4 stars
    gene_symbol   TEXT,
    rsid          TEXT,
    finding_text  TEXT NOT NULL,
    phenotype     TEXT,
    conditions    TEXT,
    zygosity      TEXT,
    clinvar_significance TEXT,
    diplotype     TEXT,               -- pharmacogenomics star-allele calling
    metabolizer_status TEXT,          -- e.g. "Poor Metabolizer"
    drug          TEXT,               -- pharmacogenomics drug name
    haplogroup    TEXT,               -- ancestry haplogroup assignment
    prs_score     REAL,               -- polygenic risk score
    prs_percentile REAL,
    pathway       TEXT,               -- nutrigenomics pathway
    pathway_level TEXT,               -- Elevated / Moderate / Standard
    svg_path      TEXT,               -- pre-rendered SVG chart path
    pmid_citations TEXT,              -- JSON array of PubMed IDs
    detail_json   TEXT,               -- arbitrary module-specific data (JSON)
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_findings_module ON findings(module);
CREATE INDEX IF NOT EXISTS idx_findings_evidence ON findings(evidence_level);

-- ── QC Metrics ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS qc_metrics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    call_rate     REAL,
    heterozygosity_rate REAL,
    ti_tv_ratio   REAL,
    total_variants INTEGER,
    called_variants INTEGER,
    nocall_variants INTEGER,
    computed_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── Sample Metadata ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sample_metadata (
    id            INTEGER PRIMARY KEY CHECK (id = 1),  -- single-row table
    name          TEXT NOT NULL,
    notes         TEXT DEFAULT '',
    date_collected DATE,
    source        TEXT DEFAULT '',
    file_format   TEXT,
    file_hash     TEXT,
    extra         TEXT DEFAULT '{}',   -- JSON for custom key-value pairs
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── APOE Gate State ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS apoe_gate (
    id            INTEGER PRIMARY KEY CHECK (id = 1),  -- single-row table
    acknowledged  BOOLEAN DEFAULT 0,
    acknowledged_at DATETIME
);

-- ── Tags ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tags (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    color         TEXT DEFAULT '#6B7280',
    is_predefined BOOLEAN DEFAULT 0,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Seed predefined tags
INSERT OR IGNORE INTO tags (name, is_predefined) VALUES
    ('Review later', 1),
    ('Discuss with clinician', 1),
    ('False positive', 1),
    ('Actionable', 1),
    ('Benign override', 1);

-- ── Variant Tags (many-to-many) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS variant_tags (
    rsid          TEXT NOT NULL,
    tag_id        INTEGER NOT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rsid, tag_id),
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- ── Haplogroup Assignments ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS haplogroup_assignments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    type          TEXT NOT NULL,      -- 'mt' or 'Y'
    haplogroup    TEXT NOT NULL,
    confidence    REAL,
    defining_snps_present INTEGER,
    defining_snps_total   INTEGER,
    assigned_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── Watched Variants (VUS tracking) ─────────────────────────────
CREATE TABLE IF NOT EXISTS watched_variants (
    rsid          TEXT PRIMARY KEY,
    watched_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    clinvar_significance_at_watch TEXT,
    notes         TEXT DEFAULT ''
);
"""


def create_sample_tables(engine: sa.Engine) -> None:
    """Create all per-sample tables in the given SQLite database.

    Args:
        engine: SQLAlchemy engine connected to a sample database file.
    """
    with engine.connect() as conn:
        conn.execute(sa.text("PRAGMA journal_mode=WAL"))
        for statement in SAMPLE_TABLES_SQL.split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(sa.text(stmt))
        conn.commit()
