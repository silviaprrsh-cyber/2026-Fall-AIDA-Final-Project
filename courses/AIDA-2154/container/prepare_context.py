"""Create a strictly allowlisted Windows Docker build context, never copy data."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

COURSE = Path(__file__).resolve().parents[1]
FILES = ("container/Dockerfile", "container/requirements.txt", "container/infer.py",
         "container/install-runtime.ps1", "src/cv_tools/model.py")


def prepare(output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Choose a new staging directory; existing files are preserved")
    for name in FILES:
        if not (COURSE / name).is_file():
            raise FileNotFoundError(name)
    output.mkdir(parents=True)
    hashes = {}
    for name in FILES:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(COURSE / name, destination)
        hashes[name] = hashlib.sha256(destination.read_bytes()).hexdigest()
    ignore = COURSE / "container/Dockerfile.dockerignore"
    shutil.copyfile(ignore, output / ".dockerignore")
    hashes[".dockerignore"] = hashlib.sha256((output / ".dockerignore").read_bytes()).hexdigest()
    actual = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    if actual != set(hashes):
        raise ValueError("Unexpected staging contents")
    return dict(status="prepared_not_built", files=hashes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
