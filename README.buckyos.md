# BuckyOS fork of ffmpeg-feedstock

This is conda-forge's ffmpeg recipe, built with **libzimg**, so `ffmpeg` has the
`zscale` filter. BuckyOS ext-core (`publish/exttool/ext-core` in the BuckyOS repository)
ships conda-forge's ffmpeg. conda-forge builds it without zimg on every platform, and
nfs_server's preview maps HDR (PQ/HLG) video to SDR BT.709 with
`zscale` + `tonemap`. Without zscale, ext-core's ffmpeg leaves HDR unmapped.

Everything else stays conda-forge's: the recipe, the patches, the variant configs
(`.ci_support/`), the build scripts (`.scripts/`), the compilers and the dependency
packages. The packages differ from conda-forge's only by the commits below.

## Branches and patch queue

- `main` mirrors `conda-forge/ffmpeg-feedstock` `main` (remote `upstream`). Nothing is
  committed to it.
- `buckyos` is the default branch: `upstream/main` plus this patch queue, rebased onto
  each upstream update.
  1. **Enable libzimg (zscale filter) on all platforms.** This commit is meant for
     upstream:
     - zimg is added to host and `--enable-libzimg` to configure.
     - On win-64, a temporary `zimg.pc` is written during the build, because
       conda-forge's win-64 zimg is built with MSBuild and installs none.
     - Two tests are added.

     Offer it to conda-forge as a PR. Once it is merged, this fork can be retired and
     ext-core can go back to plain conda-forge.
  2. **Mark the build string** as `<license>_zimg_h<hash>_<n>` (fork only). Adding zimg
     does not change the package hash (a win-64 build got `h3c7b55c`, the same as
     conda-forge's). Without the marker, this fork's package and conda-forge's would
     share a file name in package caches and locks.
  3. **CI, release and channel** (this file, `.github/workflows/buckyos.yml`,
     `.buckyos/`).

Updating to a new upstream version:

```bash
git fetch upstream
git switch main && git merge --ff-only upstream/main
git switch buckyos && git rebase main
```

Upstream's generated files (`.ci_support/`, `.scripts/`, `.gitignore`,
`.github/workflows/conda-build.yml`) are never edited here, so a rebase only
conflicts if upstream touches the same recipe lines. Upstream's `.gitignore` ignores
everything outside `recipe/` and its own files. Add a new fork file with `git add -f`;
once it is tracked, the ignore rule no longer applies to it. If upstream renames the variant
files (`.ci_support/*.yaml`), the workflow's first step fails; update the matrix in
`buckyos.yml`.

## CI

`.github/workflows/buckyos.yml` builds one variant per ext-core platform:
- the variants are `gpl`, without nvcodec;
- the platforms are linux-64, linux-aarch64, osx-64, osx-arm64 and win-64;
- each build calls conda-forge's own `.scripts/run_docker_build.sh`,
  `run_osx_build.sh` or `run_win_build.bat` with that variant's `.ci_support` file.

`UPLOAD_PACKAGES` is `False`, so nothing goes to anaconda.org. Upstream runs osx on
Azure; here osx runs on GitHub's `macos-15-intel` and `macos-15` runners.

The recipe's tests run as part of each build. Among them are the two from commit 1:
`ffmpeg -filters` lists zscale, and `-buildconf` has `--enable-libzimg`.

One-time repository setup:

- Name the repository **`ffmpeg-feedstock`**. conda-forge's scripts check the outputs
  with `validate_recipe_outputs <repository name>` against conda-forge's registry,
  where `ffmpeg` belongs to `ffmpeg-feedstock`. On Windows the name is taken from
  `GITHUB_REPOSITORY` and cannot be overridden.
- Make `buckyos` the default branch.
- Disable upstream's workflow, so it does not build all 30-odd variants:
  `gh workflow disable conda-build.yml`.
- Settings → Pages → Source: **GitHub Actions**.
- Protect tags matching `buckyos-*`.

## Releases and the channel

A tag `buckyos-<version>-<build number>` (for example `buckyos-9.1.0-100`; the gpl
build number is the recipe's `build` + 100) builds the packages and publishes a
**GitHub Release** with:

- `<subdir>__<file>.conda`: the five packages, each with a GitHub artifact attestation
  (`gh attestation verify <file> -R <owner>/ffmpeg-feedstock`);
- `source__*`: the upstream source archives that the rendered recipes name, checked
  against the recipe's sha256 (the GPL corresponding source, together with the next
  item);
- `recipe__<subdir>.tar.gz`: the package's `info/recipe` (rendered recipe, build
  scripts, patches, and the variant config it was built with);
- `SHA256SUMS`.

The **conda channel** at `https://<owner>.github.io/ffmpeg-feedstock/` is rebuilt
from all releases after each release (`.buckyos/build_channel.sh`, conda-index). It
can also be rebuilt by hand (Actions → BuckyOS packages → Run workflow →
`channel_only`).

The releases are the archive. **Do not delete a release while an ext-core
`conda-lock.yml` still points at its packages.**

## Using it in ext-core

1. In `publish/exttool/ext-core/conda-env.yml`, list this channel before conda-forge:

   ```yaml
   channels:
     - https://<owner>.github.io/ffmpeg-feedstock
     - conda-forge
   ```

2. Regenerate `conda-lock.yml` (the command is in that file). Check that every
   platform's ffmpeg entry is a `*_zimg_*` build from this channel. Under strict
   channel priority, a platform this channel has no build for falls back to
   conda-forge's ffmpeg without zimg.
3. Nothing changes in ext-core's compliance collection. `compliance.py conda` reads
   the package's `info/recipe` like any conda-forge package's, and collects the
   upstream FFmpeg archive, zimg's source and this recipe. This was checked on a
   local win-64 build.
4. Afterwards, nfs_server's comment that ext-core's ffmpeg has no zscale
   (`src/frame/nfs_server/src/preview/tools.rs`, `search_dirs`) no longer holds.

CI builds against the conda-forge pinning of upstream's last re-render. Relock ext-core
soon after a release, so the lock and the build agree on the dependency versions.

To rebuild a version *into an existing lock* without relocking, pin the host
dependencies to the lock's versions with an extra variant file. Otherwise the build's
run_exports can require versions newer than the lock holds.
`.buckyos/lockpins.example.yaml` is the one used for ext-core's win-64 lock in
November 2026:
`conda build recipe -m .ci_support/<config>.yaml -m .buckyos/lockpins.example.yaml`.

## Building locally on Windows

Run the same script CI runs from the repository root, in `cmd`:

```bat
set CONFIG=win_64_build_number_increment0ffnvcodec_headersNonelicense_familygpl
set UPLOAD_PACKAGES=False
set CI=github_actions
set GITHUB_REPOSITORY=local/ffmpeg-feedstock
set CONDA_BLD_PATH=D:\bld\
set MINIFORGE_HOME=D:\Miniforge
call .scripts\run_win_build.bat
```

It needs Visual Studio 2022 Build Tools (MSVC 14.4x). Two things break conda-build on
a desktop machine:

- **`NoDefaultCurrentDirectoryInExePath`.** If it is set, `cmd` cannot run
  conda-build's own `conda_build.bat` from the work directory. Unset it.
- **Non-ASCII environment values**, for example a `PSModulePath` under
  `…\OneDrive\文档\`. conda-build copies the whole environment into an LF-only UTF-8
  `build_env_setup.bat`. Under a non-UTF-8 console code page (936), `cmd` then
  misreads the file: the start of each line is dropped, activation silently loses
  `BUILD_PREFIX` and other variables, and the build fails with "The system cannot find
  the path specified". Remove such entries from the build's environment.

## Licenses

- The feedstock's own files keep their BSD-3-Clause license (`LICENSE.txt`), as do the
  additions here.
- The packages are FFmpeg built as **GPL-2.0-or-later** (with x264 and x265), together
  with the licenses of the libraries they link. Every release carries the matching
  source.
