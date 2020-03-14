#!/bin/bash
LANG=en_US.UTF-8
export LANG
script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

/usr/local/python-2.7/bin/python2.7 "$script_dir/po.py" >> "$script_dir/po.log" 2>&1

