#!/bin/bash
LANG=en_US.UTF-8
export LANG
script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

echo "Start RUN:" $(date "+%y-%m-%d-%-H:%-M:%-S") "------" >> "$script_dir/po.log"
/usr/bin/python2.7 "$script_dir/po.py" >> "$script_dir/po.log" 2>&1
echo "END   RUN:" $(date "+%y-%m-%d-%-H:%-M:%-S") "------" >> "$script_dir/po.log"

