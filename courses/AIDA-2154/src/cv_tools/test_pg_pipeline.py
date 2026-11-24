"""Unit and real-PostgreSQL transactional tests for the isolated CV workflow."""
import unittest
import uuid
from pathlib import Path
import psycopg
from cv_tools import pg_pipeline as p

class Paths(unittest.TestCase):
    def test_root_escape(self):
        with self.assertRaises(ValueError):p.local('../outside')
    def test_artifact_escape(self):
        with self.assertRaises(ValueError):p.contained(p.OUTPUT,'../outside.tif')
    def test_artifact_inside(self):
        self.assertTrue(p.contained(p.OUTPUT,'sample.tif').is_relative_to(p.OUTPUT))

class Database(unittest.TestCase):
    def test_shared_eda_connection(self):
        from project_tools import database
        from rdr_eda import postgres
        self.assertIs(postgres.connect,database.connect)
        self.assertIs(postgres.connection_options,database.connection_options)
    def test_cv_application_name(self):
        with p.connect() as db:
            self.assertEqual(db.execute("SELECT current_setting('application_name') AS name").fetchone()['name'],'cv_pipeline')
    def test_insert_audit_and_rollback(self):
        key='test_'+uuid.uuid4().hex
        with p.connect() as db:
            db.execute("INSERT INTO cv_pipeline.runs(run_id,stage,status) VALUES(%s,'test','running')",(key,))
            self.assertEqual(db.execute('SELECT count(*) AS n FROM cv_pipeline.audit WHERE row_key=%s',(key,)).fetchone()['n'],1)
            db.rollback()
        with p.connect() as db:self.assertIsNone(db.execute('SELECT 1 FROM cv_pipeline.runs WHERE run_id=%s',(key,)).fetchone())
    def test_constraints(self):
        with self.assertRaises(psycopg.errors.CheckViolation):
            with p.connect() as db:db.execute("INSERT INTO cv_pipeline.runs(run_id,stage,status) VALUES(%s,'test','invented')",('test_'+uuid.uuid4().hex,))
    def test_views(self):
        with p.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM cv_pipeline.v_raw_images').fetchone()['n'],2322)
            self.assertEqual(db.execute('SELECT count(*) AS n FROM cv_pipeline.samples WHERE split IS NOT NULL').fetchone()['n'],1009)
            bad=db.execute("SELECT acquired_at::date FROM cv_pipeline.v_raw_images WHERE split IS NOT NULL GROUP BY acquired_at::date HAVING count(DISTINCT split)>1").fetchall()
            self.assertFalse(bad)
    def test_failed_promotion_keeps_previous(self):
        with p.connect() as db:
            old=db.execute('SELECT * FROM cv_pipeline.masks ORDER BY sample_id LIMIT 1').fetchone()
        if old is None:self.skipTest('Mask generation not yet complete')
        row=tuple(old[k] for k in ['sample_id','method_id','path','sha256','water_pixels','unknown_pixels','run_id'])
        changed=list(row);changed[2]='not-promoted.tif'
        bad=list(row);bad[0]='missing_'+uuid.uuid4().hex
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):p.promote_masks([tuple(changed),tuple(bad)],old['run_id'],{})
        with p.connect() as db:
            actual=db.execute('SELECT * FROM cv_pipeline.masks WHERE sample_id=%s AND method_id=%s',(old['sample_id'],old['method_id'])).fetchone()
        self.assertEqual(old,actual)

if __name__=='__main__':unittest.main()
