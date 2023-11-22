#!/usr/bin/env python3
""" please run `python3 -m polyapi generate` before running this script!
"""
import os
from polyapi import poly, vari

# print(poly.polyapi.functions.api.list("develop-k8s", os.environ.get("HACKY_SECRET")))
# print(poly.test.testServerFunction(2, 2, "hi world"))
print(vari.my3.openaikey.update("fake key"))
