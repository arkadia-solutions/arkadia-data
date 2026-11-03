#!/usr/bin/env bash
# Builds the ak-data release archive for this computer — the same script runs
# on any Mac / Linux / Windows (Git Bash) machine and in GitHub Actions
# (.github/workflows/release.yml). `make release` calls it.
#
#   scripts/release.sh                     # this computer's platform
#   scripts/release.sh --target <triple>   # e.g. x86_64-unknown-linux-musl
#   scripts/release.sh --no-sign           # macOS: skip signing / notarization
#
# Output: dist/release/ak-data-<version>-<platform>.tar.gz (.zip on Windows),
# with a .sha256 file next to each archive.
#
# macOS: a universal binary (arm64 + x86_64), signed with the Developer ID
# certificate, notarized by Apple; with an installer certificate also a
# signed, notarized and stapled .pkg. The secrets come from the environment
# or from ./.env (never committed; see .env.example):
#   APPLE_SIGNING_IDENTITY        "Developer ID Application: Name (TEAMID)"
#                                 (default: the first one in the keychain)
#   APPLE_CERTIFICATE_P12         the .p12, base64 — only where the
#   APPLE_CERTIFICATE_PASSWORD    certificate is not in the keychain (CI)
#   APPLE_INSTALLER_IDENTITY      "Developer ID Installer: …" → also a .pkg
#   notarization, one of:
#     APPLE_API_KEY_P8 + APPLE_API_KEY_ID + APPLE_API_ISSUER   (App Store Connect key)
#     APPLE_ID + APPLE_APP_PASSWORD + APPLE_TEAM_ID            (app-specific password)
#     APPLE_NOTARY_PROFILE        (xcrun notarytool store-credentials <name>)
set -euo pipefail
shopt -s inherit_errexit 2> /dev/null || true
cd "$(dirname "$0")/.."
root=$(pwd)

target=""
sign=1
while [[ $# -gt 0 ]]; do
  case $1 in
    --target) target=$2; shift 2 ;;
    --no-sign) sign=0; shift ;;
    -h | --help) sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

# ./.env as KEY=value lines (not run as shell code: values may contain spaces
# and parentheses); variables already set in the environment win.
if [[ -f .env ]]; then
  while IFS= read -r line || [[ -n $line ]]; do
    line=${line%$'\r'}
    [[ $line =~ ^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
    key=${BASH_REMATCH[2]} value=${BASH_REMATCH[3]}
    if [[ $value =~ ^\"(.*)\"$ || $value =~ ^\'(.*)\'$ ]]; then value=${BASH_REMATCH[1]}; fi
    [[ -n $value && -z ${!key:-} ]] && export "$key=$value"
  done < .env
fi

version=$(tr -d ' \n' < VERSION)
bash scripts/version.sh sync > /dev/null
out="$root/dist/release"
mkdir -p "$out"
work=$(mktemp -d)
keychain=""
old_keychains=""
cleanup() {
  if [[ -n $keychain ]]; then
    # shellcheck disable=SC2086
    [[ -n $old_keychains ]] && security list-keychains -d user -s $old_keychains
    security delete-keychain "$keychain" 2> /dev/null || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT

log() { printf '\033[32m==>\033[0m %s\n' "$*"; }
sha() {
  if command -v shasum > /dev/null; then shasum -a 256 "$1"; else sha256sum "$1"; fi | awk '{print $1}'
}
checksum() {
  (cd "$out" && printf '%s  %s\n' "$(sha "$1")" "$1" > "$1.sha256")
  log "$out/$1  sha256 $(cut -d' ' -f1 < "$out/$1.sha256")"
}
build() { # target → path of the binary
  local t=$1
  command -v rustup > /dev/null && rustup target add "$t" > /dev/null 2>&1 || true
  (cd rust && cargo build --release --locked --target "$t") >&2 || return 1
  echo "$root/rust/target/$t/release/ak-data"
}

case "$(uname -s)" in
  Darwin) os=macos ;;
  Linux) os=linux ;;
  MINGW* | MSYS* | CYGWIN*) os=windows ;;
  *) echo "unsupported system: $(uname -s)" >&2; exit 1 ;;
esac

# --- Linux and Windows: one target ------------------------------------------
if [[ $os != macos ]]; then
  if [[ -z $target ]]; then
    case "$os-$(uname -m)" in
      linux-x86_64) target=x86_64-unknown-linux-musl ;;
      linux-aarch64 | linux-arm64) target=aarch64-unknown-linux-musl ;;
      windows-*) target=x86_64-pc-windows-msvc ;;
    esac
  fi
  case $target in
    x86_64-*-linux-*) platform=linux-x86_64 ;;
    aarch64-*-linux-*) platform=linux-arm64 ;;
    x86_64-pc-windows-*) platform=windows-x86_64 ;;
    aarch64-pc-windows-*) platform=windows-arm64 ;;
    *) platform=$target ;;
  esac
  log "Building ak-data $version for $target"
  bin=$(build "$target")
  mkdir -p "$work/pkg"
  cp LICENSE "$work/pkg/" 2> /dev/null || cp rust/LICENSE "$work/pkg/"
  if [[ $os == windows ]]; then
    cp "$bin.exe" "$work/pkg/ak-data.exe"
    name="ak-data-$version-$platform.zip"
    rm -f "$out/$name"
    (cd "$work/pkg" && 7z a -tzip "$out/$name" ak-data.exe LICENSE > /dev/null)
  else
    cp "$bin" "$work/pkg/ak-data"
    name="ak-data-$version-$platform.tar.gz"
    tar -czf "$out/$name" -C "$work/pkg" ak-data LICENSE
  fi
  checksum "$name"
  exit 0
fi

# --- macOS: universal, signed, notarized ------------------------------------
log "Building ak-data $version for macOS (arm64 + x86_64)"
arm=$(build aarch64-apple-darwin)
intel=$(build x86_64-apple-darwin)
mkdir -p "$work/pkg"
lipo -create -output "$work/pkg/ak-data" "$arm" "$intel"
cp LICENSE "$work/pkg/" 2> /dev/null || cp rust/LICENSE "$work/pkg/"
"$work/pkg/ak-data" --version > /dev/null

signing_args=()
if [[ $sign == 1 && -n ${APPLE_CERTIFICATE_P12:-} ]]; then
  # CI: the certificate goes into a temporary keychain, removed afterwards.
  log "Importing the signing certificate into a temporary keychain"
  keychain="$work/release.keychain-db"
  pass=$(openssl rand -hex 16)
  old_keychains=$(security list-keychains -d user | tr -d '"')
  security create-keychain -p "$pass" "$keychain"
  security set-keychain-settings -lut 21600 "$keychain"
  security unlock-keychain -p "$pass" "$keychain"
  printf '%s' "$APPLE_CERTIFICATE_P12" | base64 --decode > "$work/cert.p12"
  security import "$work/cert.p12" -k "$keychain" -P "${APPLE_CERTIFICATE_PASSWORD:-}" \
    -T /usr/bin/codesign -T /usr/bin/productsign -T /usr/bin/pkgbuild > /dev/null
  rm -f "$work/cert.p12"
  security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$pass" "$keychain" > /dev/null
  # shellcheck disable=SC2086
  security list-keychains -d user -s "$keychain" $old_keychains
  signing_args=(--keychain "$keychain")
fi

identity() { # "Developer ID Application" / "Developer ID Installer"
  security find-identity -v ${keychain:+"$keychain"} 2> /dev/null |
    sed -n "s/.*\"\($1: [^\"]*\)\".*/\1/p" | head -1
}

notarize() { # file (zip / pkg)
  local args=()
  if [[ -n ${APPLE_API_KEY_P8:-} ]]; then
    if [[ $APPLE_API_KEY_P8 == -----BEGIN* ]]; then
      printf '%s\n' "$APPLE_API_KEY_P8" > "$work/key.p8"
    else
      printf '%s' "$APPLE_API_KEY_P8" | base64 --decode > "$work/key.p8"
    fi
    args=(--key "$work/key.p8" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER")
  elif [[ -n ${APPLE_ID:-} && -n ${APPLE_APP_PASSWORD:-} ]]; then
    args=(--apple-id "$APPLE_ID" --password "$APPLE_APP_PASSWORD" --team-id "${APPLE_TEAM_ID:?APPLE_TEAM_ID is needed with APPLE_ID}")
  elif [[ -n ${APPLE_NOTARY_PROFILE:-} ]]; then
    args=(--keychain-profile "$APPLE_NOTARY_PROFILE")
  else
    return 1
  fi
  log "Notarizing $(basename "$1") (Apple, a few minutes)"
  xcrun notarytool submit "$1" "${args[@]}" --wait --timeout 30m
}

notarized=0
if [[ $sign == 1 ]]; then
  app_id=${APPLE_SIGNING_IDENTITY:-$(identity "Developer ID Application")}
  if [[ -z $app_id ]]; then
    echo "No Developer ID Application certificate found (APPLE_SIGNING_IDENTITY / APPLE_CERTIFICATE_P12). Use --no-sign for an unsigned build." >&2
    exit 1
  fi
  log "Signing with: $app_id"
  codesign --force --options runtime --timestamp --sign "$app_id" ${signing_args[@]+"${signing_args[@]}"} "$work/pkg/ak-data"
  codesign --verify --strict --verbose=2 "$work/pkg/ak-data"
  # A bare binary cannot be stapled: Apple's servers confirm it on first run.
  ditto -c -k --keepParent "$work/pkg/ak-data" "$work/ak-data.zip"
  if notarize "$work/ak-data.zip"; then
    notarized=1
  else
    echo "No notarization credentials (APPLE_API_KEY_P8… / APPLE_ID… / APPLE_NOTARY_PROFILE): signed, not notarized." >&2
    [[ -n ${CI:-} ]] && exit 1
  fi
fi

name="ak-data-$version-macos-universal.tar.gz"
tar -czf "$out/$name" -C "$work/pkg" ak-data LICENSE
checksum "$name"

# Installer package (/usr/local/bin/ak-data) with the installer certificate.
installer_id=${APPLE_INSTALLER_IDENTITY:-}
[[ $sign == 1 && -z $installer_id ]] && installer_id=$(identity "Developer ID Installer")
if [[ $sign == 1 && -n $installer_id ]]; then
  log "Building the installer package, signed with: $installer_id"
  mkdir -p "$work/root/usr/local/bin"
  cp "$work/pkg/ak-data" "$work/root/usr/local/bin/"
  pkg="ak-data-$version-macos-universal.pkg"
  pkgbuild --root "$work/root" --identifier solutions.arkadia.ak-data --version "$version" \
    --install-location / --sign "$installer_id" ${keychain:+--keychain "$keychain"} "$out/$pkg" > /dev/null
  if [[ $notarized == 1 ]] && notarize "$out/$pkg"; then
    xcrun stapler staple "$out/$pkg" > /dev/null
  fi
  checksum "$pkg"
fi
