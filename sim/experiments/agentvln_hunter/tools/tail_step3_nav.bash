#!/usr/bin/env bash
set +u
tail -n 120 /tmp/agentvln_step3/base3/nav2.log | grep -E 'Goal|failed|abort|error|feedback|recover|clearing|planner|controller' | tail -n 60
