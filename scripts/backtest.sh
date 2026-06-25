#!/usr/bin/env bash
# BORR pre-release back test.
# Usage: scripts/backtest.sh [BASE_URL]   (default http://localhost:3002)
# Exercises every route, search edge cases, 404s, and API validation,
# then prints latency timings. Exits non-zero if any check fails.

BASE="${1:-http://localhost:3002}"
PASS=0
FAIL=0

check() { # name, expected_status, url, [grep_pattern], [absent_pattern]
  local name="$1" expected="$2" url="$3" pattern="${4:-}" absent="${5:-}"
  local body status
  body=$(mktemp)
  status=$(curl -s -o "$body" -w "%{http_code}" "$url")
  local ok=1
  [ "$status" != "$expected" ] && ok=0
  if [ -n "$pattern" ] && ! grep -q "$pattern" "$body"; then ok=0; fi
  if [ -n "$absent" ] && grep -q "$absent" "$body"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    echo "PASS  $name"
    PASS=$((PASS+1))
  else
    echo "FAIL  $name (status=$status expected=$expected pattern='$pattern' absent='$absent')"
    FAIL=$((FAIL+1))
  fi
  rm -f "$body"
}

post_check() { # name, expected_status, url, json_body
  local name="$1" expected="$2" url="$3" data="$4"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$data" "$url")
  if [ "$status" = "$expected" ]; then
    echo "PASS  $name"
    PASS=$((PASS+1))
  else
    echo "FAIL  $name (status=$status expected=$expected)"
    FAIL=$((FAIL+1))
  fi
}

echo "== Pages =="
check "home renders"                 200 "$BASE/" "Research for a Better Bangladesh"
check "home has stats"               200 "$BASE/" "Articles"
check "about renders"                200 "$BASE/about" "About BORR"
check "submit renders"               200 "$BASE/submit" "Digital Object Identifier"
check "unknown route 404"            404 "$BASE/no-such-page"

echo "== Search =="
check "all papers"                   200 "$BASE/search" "All Papers"
check "query search"                 200 "$BASE/search?q=arsenic" "Results for"
check "query highlights"             200 "$BASE/search?q=arsenic" "<mark"
check "relevance default w/ query"   200 "$BASE/search?q=arsenic" "Sort by relevance"
check "cite on results"              200 "$BASE/search?q=arsenic" "Cite"
check "newest sort"                  200 "$BASE/search?q=arsenic&sort=newest" "Results for"
check "cited sort"                   200 "$BASE/search?q=arsenic&sort=cited" "Results for"
check "field filter chip"            200 "$BASE/search?q=health&field=Medicine" "Field: Medicine"
check "year range chip"              200 "$BASE/search?q=health&yearFrom=2015&yearTo=2020" "2015–2020"
check "institution filter"           200 "$BASE/search?institution=Dhaka" "Affiliation: Dhaka"
check "access filter"                200 "$BASE/search?q=health&access=Open+Access" "Open Access"
check "phrase query"                 200 "$BASE/search?q=%22climate%20change%22" "Results for"
check "empty results graceful"       200 "$BASE/search?q=zzzyyyxxx_no_match_qqq" "No papers found"
check "huge page number"             200 "$BASE/search?q=arsenic&page=99999" "No papers found"
check "page zero clamps"             200 "$BASE/search?q=arsenic&page=0" "Results for"
check "non-numeric year ignored"     200 "$BASE/search?q=arsenic&yearFrom=abc" "Results for"
check "sql injection inert"          200 "$BASE/search?q=%27%3B%20DROP%20TABLE%20papers%3B--" "" "Error loading results"
check "xss query escaped"            200 "$BASE/search?q=%3Cscript%3Ealert(1)%3C/script%3E" "" "<script>alert(1)</script>"

echo "== Paper page =="
PAPER_ID=$(curl -s "$BASE/search?q=arsenic" | grep -oE 'paper/[0-9a-f-]{36}' | head -1 | cut -d/ -f2)
if [ -n "$PAPER_ID" ]; then
  check "paper by id"                200 "$BASE/paper/$PAPER_ID" "Abstract"
  check "paper JSON-LD"              200 "$BASE/paper/$PAPER_ID" "ScholarlyArticle"
  check "paper citations shown"      200 "$BASE/paper/$PAPER_ID" "Citations"
  check "paper cite button"          200 "$BASE/paper/$PAPER_ID" "Cite"
  check "back param preserved"       200 "$BASE/paper/$PAPER_ID?back=q%3Darsenic" "/search?q=arsenic"
else
  echo "FAIL  could not extract a paper id from search results"
  FAIL=$((FAIL+1))
fi
check "paper by DOI (encoded /)"     200 "$BASE/paper/10.5281%2Fzenodo.20586240" "ScholarlyArticle"
check "missing paper 404"            404 "$BASE/paper/does-not-exist-123"

echo "== API validation =="
post_check "submit rejects bad DOI"  400 "$BASE/api/submit" '{"doi":"not-a-doi"}'
post_check "submit rejects no body"  400 "$BASE/api/submit" '{}'
ADMIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/admin")
if [ "$ADMIN_STATUS" = "401" ] || [ "$ADMIN_STATUS" = "403" ] || [ "$ADMIN_STATUS" = "429" ]; then
  echo "PASS  admin api requires auth ($ADMIN_STATUS)"
  PASS=$((PASS+1))
else
  echo "FAIL  admin api requires auth (status=$ADMIN_STATUS)"
  FAIL=$((FAIL+1))
fi

echo "== Latency (seconds, 3 runs each) =="
for path in "/" "/search?q=arsenic" "/search?q=climate+change&field=Environmental+Science" "/paper/10.5281%2Fzenodo.20586240"; do
  times=""
  for i in 1 2 3; do
    t=$(curl -s -o /dev/null -w "%{time_total}" "$BASE$path")
    times="$times $t"
  done
  echo "  $path:$times"
done

echo
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
