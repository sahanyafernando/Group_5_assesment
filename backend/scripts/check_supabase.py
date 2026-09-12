"""Verify the Supabase connection from the console.

    cd backend
    python -m scripts.check_supabase

Exit code 0 = connected, 1 = not connected.
"""

import sys

from app.core.startup import print_startup_report


def main() -> int:
    status = print_startup_report()

    if status["connected"]:
        print("Supabase connection OK.")
        return 0

    print("Supabase connection FAILED.")
    print("Checklist:")
    print("  1. backend/.env has SUPABASE_URL and SUPABASE_SECRET_KEY")
    print("  2. the key is the server-side secret key, not the publishable key")
    print("  3. supabase/schema.sql has been run in the Supabase SQL editor")
    return 1


if __name__ == "__main__":
    sys.exit(main())
