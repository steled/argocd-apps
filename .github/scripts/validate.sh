#!/usr/bin/env bash
# Validation for pull requests (also runnable locally):
#   1. every transcrypt file (filter=crypt in .gitattributes) is committed encrypted - this repository is public
#   2. the argocd-transcrypt-plugin image tag matches the Argo CD version (appVersion) of the argo-cd chart
#   3. the argocd-transcrypt-plugin image tag exists on ghcr.io
#
# Usage: .github/scripts/validate.sh [git-ref] (default: HEAD)

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

ref="${1:-HEAD}"
failed=0

error() {
  echo "::error::$*"
  failed=1
}

echo "== transcrypt files are encrypted (${ref})"
while IFS= read -r file; do
  # "U2FsdGVkX1" = base64 of the openssl header "Salted__" written by transcrypt
  if [ "$(git cat-file -p "${ref}:${file}" | head -c 10)" = "U2FsdGVkX1" ]; then
    echo "ok: ${file}"
  else
    error "${file} is NOT encrypted in ${ref} - it must never be pushed in plaintext (transcrypt not configured?)"
  fi
done < <(git ls-tree -r --name-only "$ref" | git check-attr --stdin filter | awk -F': ' '$3 == "crypt" { print $1 }')

values="$(git cat-file -p "${ref}:apps/values.yaml")"
chart_version="$(yq '.argocd.version' <<< "$values")"
plugin_tag="$(yq '.argocd.transcryptPlugin.version' <<< "$values")"

echo "== argo-cd chart ${chart_version} <-> plugin image ${plugin_tag}"
app_version="$(helm show chart argo-cd --repo https://argoproj.github.io/argo-helm --version "$chart_version" | yq '.appVersion')"
if [ "${plugin_tag%%-transcrypt-*}" = "$app_version" ]; then
  echo "ok: plugin image is built for Argo CD ${app_version}"
else
  error "argo-cd chart ${chart_version} deploys Argo CD ${app_version}, but the repo-server image ${plugin_tag} is built for ${plugin_tag%%-transcrypt-*}: wait for the matching argocd-transcrypt-plugin release (Renovate updates this PR, group \"argocd\")"
fi

echo "== plugin image exists"
token="$(curl -fsS "https://ghcr.io/token?scope=repository:steled/argocd-transcrypt-plugin:pull" | yq -p=json '.token')"
if curl -fsS -o /dev/null -I \
  -H "Authorization: Bearer ${token}" \
  -H "Accept: application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json" \
  "https://ghcr.io/v2/steled/argocd-transcrypt-plugin/manifests/${plugin_tag}"; then
  echo "ok: ghcr.io/steled/argocd-transcrypt-plugin:${plugin_tag}"
else
  error "image ghcr.io/steled/argocd-transcrypt-plugin:${plugin_tag} does not exist"
fi

exit "$failed"
