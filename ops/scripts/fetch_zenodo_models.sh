#!/bin/bash
# Downloads the pretrained Diet Network weights + SNP files from Zenodo
# record 16943452 (DN_MODELS/ and DN_SNPS/) and the 1KGP reference used by
# infer.sh's quality-control step (1KGP/) ONCE, at worker image build time.
# Never call this at request/runtime -- see deployPlan.md point 5.
#
# Usage: PARTITION_FILE=<1KGP fold partition .npz> fetch_zenodo_models.sh <dest_dir>
set -euo pipefail

DEST="${1:?Usage: PARTITION_FILE=<npz> fetch_zenodo_models.sh <dest_dir>}"
ZENODO_RECORD="16943452"
ZENODO_API="https://zenodo.org/api/records/${ZENODO_RECORD}"
# Dietnet_inference.tar.gz has DN_MODELS/ and DN_SNPS/. infer.sh's 1KGP
# quality-control step also needs the 1KGP genotypes, which are only in
# Dietnet_training.tar.gz (as 1KGP_dataset.hdf5, ~540MB unpacked); the rest
# of that archive (training weights, embeddings) is not extracted.
WANTED_FILE="Dietnet_inference.tar.gz"
TRAINING_FILE="Dietnet_training.tar.gz"
PARTITION_NAME="1KGP_2322inds_24pops_230Ksnps_parition.npz"

# Checked first so a missing partition fails the build before ~400MB of downloads.
if [ -z "${PARTITION_FILE:-}" ] || [ ! -f "$PARTITION_FILE" ]; then
    echo "ERROR: 1KGP fold partition not found (PARTITION_FILE='${PARTITION_FILE:-}')." >&2
    echo "infer.sh's quality-control step needs the partition DN_MODELS were trained with." >&2
    echo "Place it at ops/dietnet_1kgp/$PARTITION_NAME (see ops/dietnet_1kgp/README.md)." >&2
    exit 1
fi

mkdir -p "$DEST"
cd "$DEST"

echo "Fetching file list for Zenodo record ${ZENODO_RECORD}..."
curl -fsSL "$ZENODO_API" -o record.json

# Each Zenodo record file has a direct download link at .files[].links.self
python3 - "$DEST" "$WANTED_FILE" "$TRAINING_FILE" <<'PYEOF'
import json
import os
import sys
import urllib.request

dest, wanted_files = sys.argv[1], sys.argv[2:]
with open(os.path.join(dest, "record.json")) as f:
    record = json.load(f)

entries = {entry["key"]: entry for entry in record.get("files", [])}
for wanted in wanted_files:
    if wanted not in entries:
        sys.exit(f"'{wanted}' not found in Zenodo record file list")
    print(f"Downloading {wanted} ...")
    urllib.request.urlretrieve(entries[wanted]["links"]["self"], os.path.join(dest, wanted))
PYEOF

rm -f record.json

# Dietnet_inference.tar.gz unpacks to Dietnet_inference/{DN_MODELS,DN_SNPS}/
# (one level nested, matching this repo's own Dietnet_inference/ layout) --
# not DN_MODELS/DN_SNPS directly at the archive root. Unpack then flatten so
# the final layout is: $DEST/DN_MODELS/*.pt|*.npz and $DEST/DN_SNPS/*.txt
echo "Unpacking $WANTED_FILE ..."
tar -xzf "$WANTED_FILE" -C "$DEST"
rm -f "$WANTED_FILE"

if [ -d "$DEST/Dietnet_inference/DN_MODELS" ] && [ -d "$DEST/Dietnet_inference/DN_SNPS" ]; then
    mv "$DEST/Dietnet_inference/DN_MODELS" "$DEST/DN_MODELS"
    mv "$DEST/Dietnet_inference/DN_SNPS" "$DEST/DN_SNPS"
    rmdir "$DEST/Dietnet_inference" 2>/dev/null || true
fi

if [ ! -d "$DEST/DN_MODELS" ] || [ ! -d "$DEST/DN_SNPS" ]; then
    echo "WARNING: expected $DEST/DN_MODELS and $DEST/DN_SNPS after unpacking." >&2
    echo "Inspect the Zenodo record layout (it may have changed) and adjust this script." >&2
    ls -la "$DEST" >&2
    exit 1
fi

# --- 1KGP reference for infer.sh's quality-control step ---
# Layout infer.sh expects under $DEST/1KGP/:
#   1KGP_2322inds_24pops_230Ksnps.hdf5   (1KGP_dataset.hdf5 from the training archive)
#   1000G.2322samples.labels.txt         (generated below from that hdf5)
#   $PARTITION_NAME                      (from $PARTITION_FILE)
mkdir -p "$DEST/1KGP"
echo "Extracting 1KGP_dataset.hdf5 from $TRAINING_FILE ..."
tar -xzf "$TRAINING_FILE" -C "$DEST" Dietnet_training/1KGP_dataset.hdf5
mv "$DEST/Dietnet_training/1KGP_dataset.hdf5" "$DEST/1KGP/1KGP_2322inds_24pops_230Ksnps.hdf5"
rm -rf "$DEST/Dietnet_training" "$TRAINING_FILE"

python3 - "$DEST/1KGP" <<'PYEOF'
import os
import sys

import h5py

out_dir = sys.argv[1]
with h5py.File(os.path.join(out_dir, "1KGP_2322inds_24pops_230Ksnps.hdf5"), "r") as f:
    names = [n.decode() for n in f["class_label_names"]]
    rows = [(s.decode(), names[int(i)]) for s, i in zip(f["samples"], f["class_labels"])]
with open(os.path.join(out_dir, "1000G.2322samples.labels.txt"), "w") as out:
    out.write("sample\tlabel\n")
    out.writelines(f"{s}\t{label}\n" for s, label in rows)
print(f"Wrote labels for {len(rows)} 1KGP samples")
PYEOF

cp "$PARTITION_FILE" "$DEST/1KGP/$PARTITION_NAME"

# Zenodo tarball entries carry the uploader's original uid/gid/mode, which
# means nothing inside this image and can leave files unreadable to the
# unprivileged `worker` user infer.sh actually runs as. Normalize so the
# runtime user can read (but not modify) its own model files.
chmod -R a+rX,go-w "$DEST"

echo "Diet Network model and 1KGP files ready at $DEST"
