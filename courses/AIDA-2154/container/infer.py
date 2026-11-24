"""Bounded offline inference; the model is not approved for river prediction."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import torch


# Read the canonical source on the host, or its exact Docker COPY target.
def load_model_class():
    import importlib.util
    source = Path(__file__).resolve().parents[1] / "src/cv_tools/model.py"
    if not source.is_file():
        source = Path(__file__).resolve().with_name("cv_model.py")
    if not source.is_file():
        raise FileNotFoundError("Canonical CV model source is missing")
    spec = importlib.util.spec_from_file_location("cv_model", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SmallSegCNN


SmallSegCNN = load_model_class()


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def validate_input(x, valid):
    if x.dtype != np.float32 or x.ndim != 4 or x.shape[1:] != (4, 61, 61):
        raise ValueError("x must be float32 N x 4 x 61 x 61 reflectance")
    if not 1 <= len(x) <= 4096 or not np.isfinite(x).all() or x.min() < 0 or x.max() > 1:
        raise ValueError("Expected 1..4096 samples with finite reflectance in [0,1]")
    if valid.dtype != np.bool_ or valid.shape != (len(x), 61, 61):
        raise ValueError("valid must be bool N x 61 x 61")


def predict(model_path, input_path, output):
    if output.exists():
        raise FileExistsError("Choose a new output directory; existing evidence is preserved")
    started = time.perf_counter()
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    with np.load(input_path, allow_pickle=False) as data:
        x, valid = data["x"], data["valid"]
    validate_input(x, valid)
    checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)
    if checkpoint["config"]["channels"] != ["red", "green", "blue", "nir"] or checkpoint["config"]["threshold"] != 0.5:
        raise ValueError("Unsupported channel order or threshold")
    mean, std = checkpoint["mean"], checkpoint["std"]
    if tuple(mean.shape) != (1, 4, 1, 1) or tuple(std.shape) != (1, 4, 1, 1) or not torch.isfinite(mean).all() or not torch.isfinite(std).all() or not (std > 0).all():
        raise ValueError("Invalid checkpoint normalization")
    model = SmallSegCNN()
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()
    probabilities = []
    with torch.no_grad():
        for start in range(0, len(x), 16):
            values = (torch.from_numpy(x[start:start+16]) - mean) / std
            values *= torch.from_numpy(valid[start:start+16]).unsqueeze(1)
            probabilities.append(model(values).sigmoid().numpy())
    probabilities = np.concatenate(probabilities)
    mask = (probabilities >= 0.5).astype("uint8")
    mask[~valid] = 255
    probabilities[~valid] = np.nan
    output.mkdir(parents=True)
    np.savez_compressed(output / "predictions.npz", probabilities=probabilities, mask=mask, valid=valid)
    report = dict(status="inference_completed", approved_for_downstream_prediction=False,
                  label_meaning={"0":"non-water", "1":"estimated_water", "255":"unknown"},
                  samples=len(x), cpu_threads=4, batch_size=16, threshold=0.5,
                  model_sha256=sha(model_path), input_sha256=sha(input_path),
                  output_sha256=sha(output / "predictions.npz"),
                  selected_epoch=checkpoint["epoch"], torch=str(torch.__version__),
                  seconds=round(time.perf_counter()-started, 3))
    (output / "inference.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(predict(args.model, args.input, args.output), indent=2))
