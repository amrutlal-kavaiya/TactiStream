#!/usr/bin/env bash
# Runs every `// name:` query in infra/appinsights/queries.kql against Application Insights, prints row counts and
# exits 1 if any query returns no rows (US2 independent test, SC-004). TraceById gets the latest workflow trace id.
#
# Usage: infra/scripts/check-telemetry.sh <resource-group> <appinsights-name>
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <resource-group> <appinsights-name>" >&2
  exit 2
fi
rg=$1
app=$2
queries="$(dirname "$0")/../appinsights/queries.kql"
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

awk -v dir="$workdir" '
  /^\/\/ name: / { name = $3; next }
  name != "" && !/^\/\// { print > (dir "/" name ".kql") }
' "$queries"

run_query() {
  az monitor app-insights query -g "$rg" --app "$app" --offset 7d --analytics-query "$1" -o json
}

latest_trace_id=$(run_query 'union dependencies, requests
| where timestamp > ago(7d)
| order by (itemType == "dependency" and name == "tactistream.explain_moment") desc, timestamp desc
| take 1
| project operation_Id' | jq -r '.tables[0].rows[0][0] // empty')

failed=0
for file in "$workdir"/*.kql; do
  name=$(basename "$file" .kql)
  query=$(cat "$file")
  if [[ "$name" == "TraceById" ]]; then
    if [[ -z "$latest_trace_id" ]]; then
      printf '%-22s %s\n' "$name" "no trace id found"
      failed=1
      continue
    fi
    query=${query//<id>/$latest_trace_id}
  fi
  rows=$(run_query "$query" | jq '[.tables[0].rows[]] | length')
  printf '%-22s %s rows\n' "$name" "$rows"
  if [[ "$rows" == 0 ]]; then
    failed=1
  fi
done
[[ -n "$latest_trace_id" ]] && echo "TraceById used operation_Id $latest_trace_id"
exit "$failed"
