#!/bin/bash

set -e

MY_VAR="${FAAS_FUNCTIONS_BASE_PATH:-${FUNCTIONS_BASE_FOLDER:-/poly/funcs/serverfx}}"
echo "$MY_VAR"

IFS="@"
for arg in "$@"
do
  read -ra entry <<< "$arg"
  read -ra package <<< "${entry[0]}"
  if [ "${#entry[@]}" -eq '1' ];
  then
    read -ra version <<< "latest"
  else
    read -ra version <<< "${entry[1]}"
  fi

  echo "Package: $package"
  echo "Version: $version"
  echo ""

done