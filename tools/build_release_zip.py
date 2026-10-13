"""Build the distributable plugin ZIP: dist/dvr2vod-<version>.zip.

The ZIP contains the plugin package directory at its root, exactly the layout
Dispatcharr's installer and the plugin registry expect.
"""

import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "dvr2vod")

import json

with open(os.path.join(PKG, "plugin.json"), encoding="utf-8") as fh:
    VERSION = json.load(fh)["version"]

EXCLUDE = {"__pycache__", ".pytest_cache"}
OUT = os.path.join(ROOT, "dist", f"dvr2vod-{VERSION}.zip")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if os.path.exists(OUT):
        os.remove(OUT)
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(PKG):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE]
            for name in filenames:
                if name.endswith(".pyc"):
                    continue
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, ROOT)
                zf.write(full, os.path.join("dvr2vod", rel))
                count += 1
    print(f"wrote {OUT} ({count} files, version {VERSION})")


if __name__ == "__main__":
    main()
