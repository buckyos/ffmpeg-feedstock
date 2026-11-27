#!/usr/bin/env bash
# Rebuild the conda channel served on GitHub Pages from every GitHub Release of
# this repository: each release asset `<subdir>__<file>.conda` becomes
# <out>/<subdir>/<file>.conda, then conda-index writes the repodata.
#
# The releases are the archive and the channel is derived from them, so a package
# stays installable for as long as its release exists. A release that an ext-core
# lock still points at must not be deleted.
#
# usage: build_channel.sh <out dir>        (needs gh with GH_TOKEN, curl, sha256sum)
set -euo pipefail

out=${1:?usage: build_channel.sh <out dir>}
MICROMAMBA_VERSION=2.10.0-0
MICROMAMBA_SHA256=701f39c06f8e6a670a0e186c8479b9e5c0502a2f0cda6cef65d83bdd2875e8bd  # micromamba-linux-64
CONDA_INDEX_VERSION=0.13.0

rm -rf "$out"
mkdir -p "$out/noarch"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

gh release list --limit 1000 --json tagName --jq '.[].tagName' | grep '^buckyos-' | while read -r tag; do
  gh release download "$tag" --pattern '*__*.conda' --dir "$work/$tag"
  for asset in "$work/$tag"/*__*.conda; do
    name=$(basename "$asset")
    subdir=${name%%__*}
    file=${name#*__}
    mkdir -p "$out/$subdir"
    if [[ -e "$out/$subdir/$file" ]] && ! cmp -s "$asset" "$out/$subdir/$file"; then
      echo "::error::$subdir/$file differs between releases" >&2
      exit 1
    fi
    mv -f "$asset" "$out/$subdir/$file"
  done
done

mm="$work/micromamba"
curl -fsSL --retry 3 -o "$mm" "https://github.com/mamba-org/micromamba-releases/releases/download/${MICROMAMBA_VERSION}/micromamba-linux-64"
echo "${MICROMAMBA_SHA256}  $mm" | sha256sum -c -
chmod +x "$mm"
MAMBA_ROOT_PREFIX="$work/root" "$mm" create -y -q -p "$work/idx" -c conda-forge --override-channels "conda-index=${CONDA_INDEX_VERSION}"
"$work/idx/bin/python" -m conda_index "$out"

cat > "$out/index.html" <<'EOF'
<!doctype html><meta charset="utf-8"><title>BuckyOS ffmpeg channel</title>
<p>Conda channel of the BuckyOS ffmpeg fork (conda-forge recipe with libzimg).
Packages and their upstream sources are attached to the repository's GitHub Releases.</p>
EOF
touch "$out/.nojekyll"
find "$out" -name '*.conda' | sort
