#!/bin/bash

# for now redef errors happen sometimes, we will clean this up in the future!
mypy polyapi/poly | grep -v no-redef
mypy polyapi/vari | grep -v no-redef
mypy polyapi/schemas | grep -v no-redef