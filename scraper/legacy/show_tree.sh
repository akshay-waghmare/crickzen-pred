#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

find "$1" | awk 'BEGIN {
    FS="/"
}
{
    for (i=1; i<NF; i++) {
        printf "  "
    }
    print $NF
}'
