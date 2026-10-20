#!/usr/bin/env bash
# Run in Chaldea or CI. Return the executable as an artifact, never install here.
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
: "${DISPLAY_BUILD_SCRATCH:?set an absolute disposable scratch directory}"
[[ $DISPLAY_BUILD_SCRATCH == /* && $DISPLAY_BUILD_SCRATCH != / ]] || exit 2
scratch=$DISPLAY_BUILD_SCRATCH
umask 077
mkdir -p "$scratch/home" "$scratch/tmp" "$scratch/source"
export HOME="$scratch/home" HUYANG_FRICTION=0 GOMAXPROCS=2
[[ $HOME == "$DISPLAY_BUILD_SCRATCH/home" ]] || exit 2
# Unix-socket fixtures need a short pathname; the target stays on scratch disk.
tmp_alias="${RUNNER_TEMP:-$root}/t"
[[ ! -e $tmp_alias && ! -L $tmp_alias ]] || exit 2
ln -s "$scratch/tmp" "$tmp_alias"
trap 'rm -f -- "$tmp_alias"' EXIT
export TMPDIR="$tmp_alias"
[[ $(readlink -f "$TMPDIR") == "$(readlink -f "$scratch/tmp")" ]] || exit 2
umask 022

revision=5d0e64d57fccdc4d8c3ea4ce6c7e1e70c6979e08
curl --fail --location --silent --show-error \
  "https://codeload.github.com/crmne/hyprmoncfg/tar.gz/$revision" \
  --output "$scratch/source.tar.gz"
tar -xzf "$scratch/source.tar.gz" --strip-components=1 -C "$scratch/source"
cd "$scratch/source"
patch --batch --forward -p1 < "$root/hosts/omarchy-pc/patches/hyprmoncfgd-ipc-only.patch"
dependency_hash=$(sha256sum go.mod go.sum)
go mod tidy
[[ $(sha256sum go.mod go.sum) == "$dependency_hash" ]] || exit 1
[[ -z $(gofmt -l cmd internal) ]] || exit 1
go test -p 1 ./... -count=1
go vet -p 1 ./...
go test -p 1 -race ./internal/daemon ./internal/ipc ./cmd/hyprmoncfgd -count=1
mkdir -p "$root/build/display-controller"
CGO_ENABLED=0 go build -p 1 -trimpath -buildvcs=false \
  -o "$root/build/display-controller/hyprmoncfgd" ./cmd/hyprmoncfgd
"$root/build/display-controller/hyprmoncfgd" --help | grep -q -- --ipc-only
sha256sum "$root/build/display-controller/hyprmoncfgd"
