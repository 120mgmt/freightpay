#!/usr/bin/env bash
# Vendors the generated landing-page photography into public/images/landing/
# so the site stops hotlinking the generation CDN. After running, update
# src/components/landing/images.ts to use the local /images/landing/ paths.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p public/images/landing

curl -fL -o public/images/landing/hero-truck.png \
  "https://d8j0ntlcm91z4.cloudfront.net/user_3E7lFi6Ki8EjFd1rNRhEUI0jve9/hf_20260612_142544_baa60a72-4e2e-4248-a6e1-5d92f84907da.png"
curl -fL -o public/images/landing/fleet-owner.png \
  "https://d8j0ntlcm91z4.cloudfront.net/user_3E7lFi6Ki8EjFd1rNRhEUI0jve9/hf_20260612_142552_768320ef-5098-4fcc-8cb7-9fc0733e096c.png"
curl -fL -o public/images/landing/driver-cab.png \
  "https://d8j0ntlcm91z4.cloudfront.net/user_3E7lFi6Ki8EjFd1rNRhEUI0jve9/hf_20260612_142554_c31e8da3-3b48-47bc-bb8f-b7aa8a28fc06.png"

echo "Done. Images saved to public/images/landing/."
