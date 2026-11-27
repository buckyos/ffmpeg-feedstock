"""Write .buckyos/pins/<subdir>.json: ffmpeg's host dependencies pinned to the
versions in BuckyOS ext-core's conda-lock.yml.

ffmpeg built against conda-forge's newest pinning can need newer libraries than
the rest of ext-core's environment (ImageMagick, graphviz, ...) is built for, and
then ext-core's lock has no solution. Built against the versions ext-core already
locks, the package drops into that environment: relocking moves ffmpeg (and adds
zimg) without forcing anything else.

usage: pins_from_lock.py <conda-lock.yml> [--out .buckyos/pins] [--build-number-increment N]

The lock is ext-core's (publish/exttool/ext-core/conda-lock.yml in the BuckyOS
repository), preferably from a conda-forge-only solve of the environment so it
reflects the conda-forge of the day. A key is pinned only when the locked package
is there; otherwise the recipe's own pin applies and the script says so.
Only the standard library is used (the lock is read line by line).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SUBDIRS = ["linux-64", "linux-aarch64", "osx-64", "osx-arm64", "win-64"]

# Variant key (the recipe's host dependency, '-' as '_') -> the package in the lock
# that carries the same version (the run dependency the host package exports).
HOST = {
    "aom": ["aom"],
    "alsa_lib": ["alsa-lib"],
    "bzip2": ["bzip2"],
    "dav1d_devel": ["libdav1d7", "libdav1d"],
    "expat": ["libexpat"],
    "fontconfig": ["fontconfig"],
    "freetype": ["libfreetype"],
    "gmp": ["gmp"],
    "harfbuzz": ["libharfbuzz"],
    "lame": ["lame"],
    "libass": ["libass"],
    "libiconv": ["libiconv"],
    "libjxl": ["libjxl"],
    "libopenvino_dev": ["libopenvino"],
    "libopus": ["libopus"],
    "libplacebo": ["libplacebo"],
    "librsvg": ["librsvg"],
    "libva": ["libva"],
    "libvorbis": ["libvorbis"],
    "libvpl": ["libvpl"],
    "libvpx": ["libvpx"],
    "libvulkan_loader": ["libvulkan-loader"],
    "libwebp": ["libwebp-base"],
    "libxcb": ["libxcb"],
    "libxml2_devel": ["libxml2-16"],
    "liblzma_devel": ["liblzma"],
    "openh264": ["openh264"],
    "openssl": ["openssl"],
    "pulseaudio_client": ["pulseaudio-client"],
    "sdl2": ["sdl2"],
    "svt_av1": ["svt-av1"],
    "x264": ["x264"],
    "x265": ["x265"],
    "xorg_libx11": ["xorg-libx11"],
    "zlib": ["libzlib"],
}


def locked_versions(lock: Path) -> dict[str, dict[str, str]]:
    """{platform: {name: version}} from a conda-lock.yml, without a YAML parser."""
    out: dict[str, dict[str, str]] = {}
    entry: dict[str, str] = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        if line.startswith("- name: "):
            if {"name", "version", "platform"} <= entry.keys() and entry.get("manager") == "conda":
                out.setdefault(entry["platform"], {})[entry["name"]] = entry["version"]
            entry = {"name": line[len("- name: "):].strip()}
        m = re.match(r"^  (version|platform|manager): (.+)$", line)
        if m:
            entry[m.group(1)] = m.group(2).strip().strip("'\"")
    if {"name", "version", "platform"} <= entry.keys() and entry.get("manager") == "conda":
        out.setdefault(entry["platform"], {})[entry["name"]] = entry["version"]
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("lock", type=Path)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "pins")
    parser.add_argument("--build-number-increment", default=None,
                        help="also set build_number_increment, so the build gets a new build number")
    args = parser.parse_args()
    locked = locked_versions(args.lock)
    args.out.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        packages = locked.get(subdir)
        if not packages:
            raise SystemExit(f"{args.lock}: nothing locked for {subdir}")
        pins, missing = {}, []
        for key, names in HOST.items():
            name = next((n for n in names if n in packages), None)
            if name is None:
                missing.append(key)
            else:
                pins[key] = packages[name]
        if args.build_number_increment is not None:
            pins["build_number_increment"] = str(args.build_number_increment)
        (args.out / f"{subdir}.json").write_text(json.dumps(pins, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{subdir}: {len(pins)} pinned; not in the lock, recipe pin applies: {', '.join(missing) or '-'}")


if __name__ == "__main__":
    main()
