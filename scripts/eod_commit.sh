#!/usr/bin/env bash
cd ~/future_prep
git add -A
git commit -m "EOD $(date +%Y-%m-%d): ${1:-daily progress}"
git push
