#!/usr/bin/env bash
# Builds the website for Netlify: copies app/ to dist/ and writes config.js
# from the Netlify environment variables (keeps the Supabase values out of git).
set -euo pipefail
: "${SUPABASE_URL:?Set SUPABASE_URL in Netlify environment variables}"
: "${SUPABASE_ANON_KEY:?Set SUPABASE_ANON_KEY in Netlify environment variables}"
rm -rf dist && mkdir dist && cp -r app/. dist/
printf 'window.AIRLOGIC_CONFIG = { supabaseUrl: "%s", supabaseAnonKey: "%s" };\n' \
  "$SUPABASE_URL" "$SUPABASE_ANON_KEY" > dist/config.js
