"""Static gate for the "Create a Rib" input validation fix.

The real path is a modal Qt dialog, so this only asserts the guard is
present in source and fails if it is ever removed.

Run: python3 tests/testRibValidation.py  (or freecadcmd)
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    with open(os.path.join(ROOT, name)) as f:
        return f.read()


def main():
    ui = _read("airPlaneDesignProfilUI.py")
    assert re.search(r"class SelectObjectUI.*?def __init__\(self\):\s*\n\s*self\.filePath = None",
                     ui, re.S), "SelectObjectUI.__init__ must initialise filePath = None"

    rib = _read("airPlaneRib.py")
    activated = rib.split("def Activated(self):", 1)[1]
    guard = activated.index("os.path.isfile")
    block = activated[guard:activated.index("return", guard)]
    assert "QMessageBox" in block, "missing user-visible error before the guard's return"
    assert activated.index("return", guard) < activated.index("addObject"), \
        "invalid input must return before any document object is created"
    print("testRibValidation: ok")


if __name__ == "__main__":
    main()
