#!/usr/bin/env bash
# generate_icons.sh - create PWA PNG icons and print manifest entries
# Usage: ./scripts/generate_icons.sh path/to/source.png
set -euo pipefail
src="$1"
outdir="$(dirname "$0")/../static/icons"
mkdir -p "$outdir"
icon192="$outdir/icon-192.png"
icon512="$outdir/icon-512.png"

# Prefer ImageMagick's convert, fallback to rsvg-convert
if command -v convert >/dev/null 2>&1; then
  echo "Using ImageMagick 'convert' to generate icons..."
  convert "$src" -background '#111827' -resize 192x192^ -gravity center -extent 192x192 "$icon192"
  convert "$src" -background '#111827' -resize 512x512^ -gravity center -extent 512x512 "$icon512"
elif command -v rsvg-convert >/dev/null 2>&1; then
  echo "Using rsvg-convert to generate icons..."
  rsvg-convert -w 192 -h 192 "$src" -o "$icon192"
  rsvg-convert -w 512 -h 512 "$src" -o "$icon512"
else
  echo "Error: neither 'convert' (ImageMagick) nor 'rsvg-convert' is available." >&2
  echo "Install ImageMagick (sudo apt install imagemagick) or librsvg2-bin (sudo apt install librsvg2-bin)" >&2
  exit 2
fi

chmod 644 "$icon192" "$icon512"

cat <<EOF
Icons created:
  $icon192
  $icon512

Add these entries to your manifest (static/manifest.json) inside the "icons" array:

{
  "src": "/scanner/static/icons/icon-192.png",
  "sizes": "192x192",
  "type": "image/png"
},
{
  "src": "/scanner/static/icons/icon-512.png",
  "sizes": "512x512",
  "type": "image/png"
}

After updating the manifest, deploy and purge CDN cache for /scanner/* if used (Cloudflare), then test:
  curl -I https://iamcalledned.ai/scanner/manifest.json
  curl -I https://iamcalledned.ai/scanner/static/icons/icon-192.png
  curl -I https://iamcalledned.ai/scanner/static/icons/icon-512.png

If you want, I can automatically update the manifest for you (requires jq). Run:
  ./scripts/generate_icons.sh path/to/your/source.png

EOF
