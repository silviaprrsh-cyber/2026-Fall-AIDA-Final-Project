"""Tests for the isolated inference contract and exact training parity."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from infer import SmallSegCNN, validate_input, predict

class ContractTests(unittest.TestCase):
    def test_minimal_build_context(self):
        from prepare_context import prepare, FILES
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"context"
            result=prepare(output)
            actual={p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
            self.assertEqual(actual,set(FILES)|{".dockerignore"})
            self.assertEqual(actual,set(result["files"]))
            with self.assertRaises(FileExistsError): prepare(output)

    def test_valid_input(self):
        validate_input(np.zeros((1,4,61,61), np.float32), np.ones((1,61,61), bool))
    def test_reject_channel_shape(self):
        with self.assertRaises(ValueError):
            validate_input(np.zeros((1,3,61,61), np.float32), np.ones((1,61,61), bool))
    def test_reject_nonfinite(self):
        x=np.zeros((1,4,61,61),np.float32); x[0,0,0,0]=np.nan
        with self.assertRaises(ValueError): validate_input(x,np.ones((1,61,61),bool))
    def test_reject_range(self):
        with self.assertRaises(ValueError): validate_input(np.full((1,4,61,61),2,np.float32),np.ones((1,61,61),bool))
    def test_reject_invalid_validity(self):
        with self.assertRaises(ValueError): validate_input(np.zeros((1,4,61,61),np.float32),np.ones((1,61,61),np.uint8))
    def test_existing_output_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError): predict(Path('absent'),Path('absent'),Path(directory))
    def test_architecture_parity(self):
        root=HERE.parents[2]
        sys.path.insert(0,str(root))
        import run
        run.bootstrap()
        from cv_tools.train_point_cnn import SmallSegCNN as TrainingCNN
        original=TrainingCNN().eval(); packaged=SmallSegCNN().eval()
        packaged.load_state_dict(original.state_dict())
        x=torch.zeros((2,4,61,61))
        with torch.no_grad():
            self.assertTrue(torch.equal(original(x),packaged(x)))

if __name__=='__main__': unittest.main()
