"""Test runner for Vitrina test suite with clean process termination."""

from __future__ import annotations

import os
import sys
import unittest


def main() -> None:
    os.environ.setdefault("VITRINA_HEADLESS_TEST", "1")
    os.environ.setdefault("FOTODOWN_HEADLESS_TEST", "1")
    loader = unittest.TestLoader()
    suite = loader.discover("tests")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        from PySide6.QtCore import QCoreApplication
        app = QCoreApplication.instance()
        if app is not None:
            app.quit()
            app.processEvents()
    except Exception:
        pass
    if result.wasSuccessful():
        os._exit(0)
    else:
        os._exit(1)


if __name__ == "__main__":
    main()
