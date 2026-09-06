"""CP1 self-check: re-list S3 and compare object-by-object with what was actually read (manifest).
(v2: the first version derived the date from path segment 2 = 'r0' instead of 3 and re-listed nothing.)"""
import json
from pathlib import Path
from pyarrow import fs
DE = Path(__file__).resolve().parent.parent
man = {m["key"]: m for m in json.loads((DE / "cp1_manifest.json").read_text())}
s3 = fs.S3FileSystem(region="ap-south-1"); relist = {}
for d in sorted({k.split("/")[3] for k in man}):
    for o in s3.get_file_info(fs.FileSelector(f"tradetri-orderflow-data-383136686940-ap-south-1-an/orderflow/r0/{d}/depth", recursive=False, allow_not_found=True)):
        if o.type == fs.FileType.File and o.path in man: relist[o.path] = o.size
missing = [k for k in man if k not in relist]; mism = [k for k in man if k in relist and relist[k] != man[k]["bytes"]]
print(f"  manifest objects: {len(man)} | re-listed: {len(relist)} | missing on re-list: {len(missing)} | size mismatch: {len(mism)}")
print(f"  raw tape parquet on local disk (must be 0): {len([p for p in (DE).glob('*.parquet')])} ; feature parquet written by this run: {len(list((DE/'features').glob('*.parquet')))}")
