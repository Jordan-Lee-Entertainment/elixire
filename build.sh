#!/bin/bash

function check_exitcode {
    local status=$?

    if [ $status -ne 0 ]; then
        echo "Command failed with a non-good error code."
        exit $status
    fi
}

echo "[build] building main frontend code for elixire"

# build frontend
cd frontend
echo "[build] installing deps for frontend"
npm i
check_exitcode

echo "[build] building frontend"
npm run build:production
check_exitcode
cd ..

# build the admin panel
cd admin-panel
echo "[build] installing deps for admin panel"
npm i
check_exitcode

echo "[build] building admin panel"
npm run build
check_exitcode
cd ..

echo "[build] build script finished."
