"""Lay out the assets of a BuckyOS release of this feedstock.

usage: release_assets.py <dist dir> <assets dir>

<dist dir> holds pkg-<subdir>/<file>.conda as the build jobs stored them. Writes to
<assets dir>:

- <subdir>__<file>.conda   the packages; the prefix keeps the same file name from
                           two platforms apart (build_channel.sh strips it again)
- recipe__<subdir>.tar.gz  the package's info/recipe: rendered recipe, build
                           scripts, patches and the variant config it was built with
- source__<file>           every upstream source archive the rendered recipes name,
                           downloaded and checked against the recipe's sha256
- SHA256SUMS

and the release notes beside it, <assets dir>-notes.md.

Needs zstandard and PyYAML.
"""
from __future__ import annotations

import hashlib
import io
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

import yaml
import zstandard


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def recipe_files(package: Path) -> dict[str, bytes]:
    """info/recipe/* of a .conda package, by path."""
    with zipfile.ZipFile(package) as archive:
        info = next(n for n in archive.namelist() if n.startswith("info-") and n.endswith(".tar.zst"))
        raw = archive.read(info)
    files = {}
    with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw)) as stream, tarfile.open(fileobj=stream, mode="r|") as tar:
        for member in tar:
            if member.isfile() and member.name.startswith("info/recipe/"):
                files[member.name] = tar.extractfile(member).read()
    if "info/recipe/meta.yaml" not in files:
        raise SystemExit(f"{package}: no rendered info/recipe/meta.yaml")
    return files


def sources(meta: dict) -> list[dict]:
    entries = meta.get("source") or []
    return entries if isinstance(entries, list) else [entries]


def fetch(entry: dict, dest_dir: Path) -> Path:
    urls = entry["url"] if isinstance(entry["url"], list) else [entry["url"]]
    expected = entry["sha256"]
    name = entry.get("fn") or PurePosixPath(urls[0].split("?")[0]).name
    dest = dest_dir / f"source__{name}"
    if dest.exists() and sha256(dest) == expected:
        return dest
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=120) as response, dest.open("wb") as out:
                shutil.copyfileobj(response, out)
        except OSError as error:
            print(f"{url}: {error}", file=sys.stderr)
            continue
        if sha256(dest) == expected:
            return dest
        print(f"{url}: sha256 differs from the recipe", file=sys.stderr)
    dest.unlink(missing_ok=True)
    raise SystemExit(f"no address of {name} gave sha256 {expected}")


def main() -> None:
    dist, assets = Path(sys.argv[1]), Path(sys.argv[2])
    assets.mkdir(parents=True, exist_ok=True)
    packages = sorted(dist.glob("pkg-*/*.conda"))
    if not packages:
        raise SystemExit(f"no packages under {dist}/pkg-*/")
    rows, fetched = [], {}
    for package in packages:
        subdir = package.parent.name.removeprefix("pkg-")
        target = assets / f"{subdir}__{package.name}"
        shutil.copy2(package, target)
        files = recipe_files(package)
        with tarfile.open(assets / f"recipe__{subdir}.tar.gz", "w:gz") as tar:
            for name, data in sorted(files.items()):
                item = tarfile.TarInfo(name)
                item.size, item.mtime, item.mode = len(data), 0, 0o644
                tar.addfile(item, io.BytesIO(data))
        meta = yaml.safe_load(files["info/recipe/meta.yaml"])
        for entry in sources(meta):
            if "url" in entry and entry["sha256"] not in fetched:
                fetched[entry["sha256"]] = fetch(entry, assets)
        rows.append((subdir, package.name, sha256(target)))
    sums = sorted((sha256(p), p.name) for p in assets.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    (assets / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for digest, name in sums))
    notes = ["BuckyOS build of conda-forge's ffmpeg recipe with libzimg (zscale). See README.buckyos.md.", "",
             "| platform | package | sha256 |", "|---|---|---|"]
    notes += [f"| {s} | `{n}` | `{d}` |" for s, n, d in rows]
    notes += ["", "Corresponding source: the `source__*` archives (checked against the recipe's sha256) "
              "with the `recipe__*` build scripts and patches. Provenance: GitHub artifact attestation of each package."]
    Path(f"{assets}-notes.md").write_text("\n".join(notes) + "\n")
    for line in sums:
        print(*line)


if __name__ == "__main__":
    main()
