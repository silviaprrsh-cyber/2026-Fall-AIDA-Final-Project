-- Isolated CV lineage; no changes to hydrology schemas or permissions.
CREATE SCHEMA IF NOT EXISTS cv_pipeline;
CREATE TABLE IF NOT EXISTS cv_pipeline.runs (
 run_id text PRIMARY KEY, stage text NOT NULL, started_at timestamptz NOT NULL DEFAULT now(),
 finished_at timestamptz, status text NOT NULL CHECK(status IN ('running','complete','failed')), details jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS cv_pipeline.scenes (
 scene_id text PRIMARY KEY, source_path text NOT NULL UNIQUE, sha256 text NOT NULL CHECK(length(sha256)=64),
 acquired_at timestamptz NOT NULL, provenance text NOT NULL, imported_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS cv_pipeline.samples (
 sample_id text PRIMARY KEY, scene_id text NOT NULL REFERENCES cv_pipeline.scenes,
 point_id text NOT NULL, coordinates jsonb NOT NULL, split text CHECK(split IN ('train','validation','test')),
 original_record jsonb NOT NULL, selection_manifest_sha256 text NOT NULL
);
CREATE TABLE IF NOT EXISTS cv_pipeline.masks (
 sample_id text NOT NULL REFERENCES cv_pipeline.samples, method_id text NOT NULL,
 path text NOT NULL, sha256 text NOT NULL CHECK(length(sha256)=64), water_pixels int NOT NULL,
 unknown_pixels int NOT NULL, run_id text NOT NULL REFERENCES cv_pipeline.runs,
 PRIMARY KEY(sample_id,method_id)
);
CREATE TABLE IF NOT EXISTS cv_pipeline.audit (
 event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 actor text NOT NULL DEFAULT current_user, transaction_id bigint NOT NULL DEFAULT txid_current(),
 table_name text NOT NULL, operation text NOT NULL, row_key text, old_row jsonb, new_row jsonb
);
CREATE OR REPLACE FUNCTION cv_pipeline.log_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO cv_pipeline.audit(table_name,operation,row_key,old_row,new_row)
 VALUES(TG_TABLE_NAME,TG_OP,COALESCE(to_jsonb(NEW)->>'sample_id',to_jsonb(OLD)->>'sample_id',to_jsonb(NEW)->>'scene_id',to_jsonb(OLD)->>'scene_id',to_jsonb(NEW)->>'run_id',to_jsonb(OLD)->>'run_id'),
 CASE WHEN TG_OP<>'INSERT' THEN to_jsonb(OLD) END,CASE WHEN TG_OP<>'DELETE' THEN to_jsonb(NEW) END);
 RETURN COALESCE(NEW,OLD);
END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['runs','scenes','samples','masks'] LOOP
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='audit_cv_'||t AND tgrelid=('cv_pipeline.'||t)::regclass) THEN
 EXECUTE format('CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON cv_pipeline.%I FOR EACH ROW EXECUTE FUNCTION cv_pipeline.log_change()', 'audit_cv_'||t,t);
 END IF;
 END LOOP;
END $$;
CREATE OR REPLACE VIEW cv_pipeline.v_raw_images AS
 SELECT s.sample_id,s.point_id,s.coordinates,s.split,s.original_record,s.selection_manifest_sha256,
 i.scene_id,i.source_path,i.sha256 AS source_sha256,i.acquired_at,i.provenance
 FROM cv_pipeline.samples s JOIN cv_pipeline.scenes i USING(scene_id);
CREATE OR REPLACE VIEW cv_pipeline.v_training_pairs AS
 SELECT r.*,m.method_id,m.path AS mask_path,m.sha256 AS mask_sha256,m.run_id AS mask_run_id
 FROM cv_pipeline.v_raw_images r JOIN cv_pipeline.masks m USING(sample_id)
 JOIN cv_pipeline.runs run ON run.run_id=m.run_id
 WHERE r.split IS NOT NULL AND run.status='complete';
