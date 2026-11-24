"""Build a Windows source package with only explicitly selected server files."""
import argparse, hashlib, io, re, zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
PIN="611348b30e5312f3aba087c1c327a58cdf21c853afc89bcaf52aab4052c66479"
FILES=("__init__.py","schema.py","inference.py","v4_chain.py","service.py","store.py","provider.py",
       "provider.py.md","provider.pyCN.md","model_60_20_20.pt","requirements.txt","README.md","READMECN.md","WIRE.md")

def digest(raw):return hashlib.sha256(raw).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("new_zip",type=Path);z=p.parse_args()
    if z.new_zip.suffix.lower()!=".zip":p.error("The new package must end in .zip")
    entries={f"server/{f}":(HERE/f).read_bytes() for f in FILES}
    assert digest(entries["server/model_60_20_20.pt"])==PIN
    manifest="".join(f"{digest(raw)}  {name}\n" for name,raw in sorted(entries.items()))
    entries["server/MANIFEST.sha256"]=manifest.encode("ascii")
    with zipfile.ZipFile(z.new_zip,"x",compression=zipfile.ZIP_DEFLATED) as w:
        for name,raw in sorted(entries.items()):
            item=zipfile.ZipInfo(name,date_time=(2026,11,20,0,0,0))
            item.compress_type=zipfile.ZIP_DEFLATED
            w.writestr(item,raw)
    with zipfile.ZipFile(z.new_zip) as zf:
        assert set(zf.namelist())==set(entries) and zf.testzip() is None
        for n in entries:
            assert digest(zf.read(n))==digest(entries[n])
    print(f"{digest(z.new_zip.read_bytes())}  {z.new_zip.name}  ({len(entries)} entries)")
if __name__=="__main__":
    main()
