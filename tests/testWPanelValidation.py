"""Static gate for the WingPanel bad-selection fix.

Constructing WingPanel headless dies on obj.Base.Visibility (needs a
ViewObject), so this asserts the fix in source: the bad-selection paths
complain instead of building a corrupt panel, and Hullcurves drops None
links (head on HEAD the [None, None] assign raised 'PropertyLinkList:
invalid document object' mid-construction).

Run: python3 tests/testWPanelValidation.py  (or freecadcmd)
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    with open(os.path.join(ROOT, "airPlaneWPanel.py")) as f:
        src = f.read()

    assert "WingPanel(obj,None" not in src, \
        "dead fallback building a WingPanel of Nones is back"

    hull = [l for l in src.splitlines() if '"Hullcurves"' in l]
    assert hull and "if e is not None" in hull[0], \
        "Hullcurves assignment must filter None edge links"

    activated = src.split("class CommandWPanel", 1)[1].split("def Activated(self):", 1)[1]
    assert "QMessageBox" in activated and "PrintError" in activated, \
        "bad selection must surface a user-visible error"
    assert activated.index("QMessageBox") < activated.index("addObject"), \
        "bad selection must return before any document object is created"

    usage = src.split("_WING_PANEL_USAGE = (", 1)[1].split(")", 1)[0]
    assert "Wing -" in usage and "Root rib -" in usage \
        and "Path -" in usage and "Envelope -" in usage, \
        "usage text must name all 4 picks in plain language"
    assert "2 edges" in usage, "usage text must state the envelope needs 2 edges"
    assert activated.count("_WING_PANEL_USAGE") == 4, \
        "both bad-selection paths (empty and wrong count) must use the usage text"
    print("testWPanelValidation: ok")


if __name__ == "__main__":
    main()
