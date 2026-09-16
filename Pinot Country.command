#!/bin/bash
# Double-click to run the Pinot Country pipeline from a numbered menu.
P="$HOME/Developer/claude code projects/pinot-noir"
cd "$P" || { echo "Project folder not found: $P"; read -p "Press return to close."; exit 1; }
PY=python3

while true; do
  echo
  echo "PINOT COUNTRY   —   https://nanobotco.github.io/pinot-noir/"
  echo "  1  Validate every record"
  echo "  2  Build (validate + API + search tables)"
  echo "  3  Make the website (build/site)"
  echo "  4  Everything: 1-3, then open it"
  echo "  5  Serve the site (http://127.0.0.1:8803)"
  echo "  6  Run the tests"
  echo "  7  Draw the share cards that are missing"
  echo "  8  PUBLISH to docs/ (what GitHub Pages serves)"
  echo "  9  Push to GitHub"
  echo " 10  Refresh cellars from OpenStreetMap (slow; runs in chunks)"
  echo " 11  Refresh the American appellation list from the eCFR"
  echo " 12  Fetch free pictures from Commons for records that name them"
  echo "  0  Quit"
  read -p "Number: " n
  case "$n" in
    1) $PY tools/validate.py ;;
    2) $PY tools/build.py ;;
    3) $PY tools/site.py ;;
    4) $PY tools/build.py && $PY tools/site.py && open "build/site/index.html" ;;
    5) $PY tools/serve.py 8803 ;;
    6) $PY -m unittest discover -s tests -v 2>&1 | tail -25 ;;
    7) $PY tools/cards.py ;;
    8) ./publish.sh ;;
    9) git add -A && git commit && git push origin main ;;
    10) $PY tools/harvest_osm.py ;;
    11) $PY tools/harvest_ecfr.py ;;
    12) $PY tools/harvest_commons.py --harvest --apply ;;
    0) exit 0 ;;
    *) echo "Pick a number." ;;
  esac
done
