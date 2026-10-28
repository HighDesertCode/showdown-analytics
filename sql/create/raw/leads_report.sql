-- One row per leads text report: the "Total leads" header line (two per battle).
-- lead_count is the overall total even in per-type reports, whose percentages use that type's leads instead.
CREATE TABLE raw.leads_report (
    source_file_id bigint  PRIMARY KEY REFERENCES raw.source_file (source_file_id),
    lead_count     integer NOT NULL CHECK (lead_count >= 0)
);
