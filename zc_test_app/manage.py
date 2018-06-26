#!/usr/bin/env python
import os
import sys

from os.path import abspath, dirname

if __name__ == "__main__":
    project_dir = dirname(dirname(abspath(__file__)))
    sys.path.insert(0, project_dir)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zc_test_app.settings")

    from django.core.management import execute_from_command_line
    from django import setup
    setup()

    execute_from_command_line(sys.argv)
