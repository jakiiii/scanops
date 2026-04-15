#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import sys
from core.env import configure_environment

if __name__ == "__main__":
    configure_environment()

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
