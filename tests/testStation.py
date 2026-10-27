#!/usr/bin/env freecadcmd
#################################################
#
# Wing station core tests - Aircraft
#
# Copyright (c) RedxHerring - 2026 - V0.1
#
# For FreeCAD Versions = or > 0.17 Revision xxxx
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License (LGPL)
# as published by the Free Software Foundation; either version 2 of
# the License, or (at your option) any later version.
# for detail see the LICENCE text file.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
################################################
"""Gate test for airPlaneStation.  Run from the repo root, NO arguments:

    freecadcmd tests/testStation.py

Plain asserts + printed summary; non-zero exit on failure (freecadcmd 1.1.4
returns 0 on an uncaught exception, so the failure path calls sys.exit(1)
explicitly).

The permanent centre of this test is the placement equivalence:
placement.multVec((u, 0, v)) == Station.to3d(u, v) - the contract
airPlaneCavity schedule consumers lean on instead of a second frame
implementation (measured 1.5e-11 mm at the source project).
"""
__title__ = "FreeCAD airPlaneStation tests"
__author__ = "RedxHerring"
__url__ = "https://fredsfactory.fr"

import math
import os
import sys
import traceback

try:  # stream the gate report even when piped - and do not lose it on exit(1)
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass

# uninstalled checkout: the workbench root is the parent of tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import airPlaneStation

# captured right after importing the module under test, before any other
# workbench import can muddy sys.modules
PURITY_OK = ('PySide' not in sys.modules and 'FreeCADGui' not in sys.modules)

import FreeCAD
import Part

# frames under test: twisted starboard root, mirrored port mid-span station
FRAMES = [airPlaneStation.Station(0.0, 0.0, 0.35, 1.0, 4000.0),
          airPlaneStation.Station(14000.0, 3000.0, -0.06, -1.0, 2800.0)]
SAMPLES = [(12345.6, 2345.6), (-9876.5, -4321.0)]


def gatePurity():
    assert PURITY_OK, "importing airPlaneStation pulled in the GUI"


def gateTo3d():
    # reference math recomputed independently of the module (cos/sin straight
    # from stdlib math): a shared implementation would test nothing
    for f in FRAMES:
        tw = math.atan2(f.sa, f.ca)
        for u, v in SAMPLES:
            ref = FreeCAD.Vector(
                f.sign * f.station,
                f.y_ref + u * math.cos(tw) + v * math.sin(tw),
                -u * math.sin(tw) + v * math.cos(tw))
            err = (f.to3d(u, v) - ref).Length
            assert err < 1e-9, \
                "to3d(%.1f, %.1f) off the reference frame law by %.2e mm" \
                % (u, v, err)


def gatePlacement():
    # the permanent equivalence: placement.multVec((u, 0, v)) == to3d(u, v)
    # over starboard AND port (sign = -1) frames, both sample corners
    err = 0.0
    for f in FRAMES:
        pl = f.placement()
        assert (pl.Base - FreeCAD.Vector(f.sign * f.station, f.y_ref,
                                         0.0)).Length < 1e-9, \
            "placement Base is not the quarter-chord point"
        for u, v in SAMPLES:
            err = max(err, (pl.multVec(FreeCAD.Vector(u, 0.0, v))
                            - f.to3d(u, v)).Length)
    assert err < 1e-6, \
        "placement.multVec((u,0,v)) != to3d(u,v): max err %.2e mm - frame " \
        "convention mismatch, airPlaneCavity must NOT be fed this frame" % err
    print("      max |multVec - to3d| = %.2e mm" % err)


def gateSchedule():
    cr, ct, semi, tw0, sw = 4000.0, 2000.0, 20000.0, 0.10, 0.35
    sched = airPlaneStation.linearSchedule(cr, ct, semi, tw0, sw, 5)
    assert len(sched) == 5, "nStations=5 returned %d frames" % len(sched)
    for i, s in enumerate(sched):
        f = semi * i / 4.0
        assert abs(s.station - f) < 1e-9, "station %d at %.1f" % (i, s.station)
        assert abs(s.chordMm - (cr + (ct - cr) * f / semi)) < 1e-9, \
            "chord law broken at station %d" % i
        assert abs(math.atan2(s.sa, s.ca) - tw0 * (1.0 - f / semi)) < 1e-12, \
            "twist washout law broken at station %d" % i
        assert abs(s.y_ref - math.tan(sw) * f) < 1e-9, \
            "quarter-chord sweep offset broken at station %d" % i
        assert s.sign == 1.0, "schedule half is not starboard"
    ends = airPlaneStation.linearSchedule(cr, ct, semi, tw0, sw)
    assert len(ends) == 2 and ends[0].chordMm == cr and ends[1].chordMm == ct \
        and abs(math.atan2(ends[1].sa, ends[1].ca)) < 1e-15, \
        "the default two-end schedule does not carry root/tip chord and " \
        "zero tip twist"
    try:
        airPlaneStation.linearSchedule(cr, ct, semi, tw0, sw, 1)
        assert False, "nStations=1 did not raise - the guard is dead"
    except ValueError:
        pass


def gateSectionCoords():
    # hand-computed parity: unit-chord TE->upper->LE->lower->TE loop with a
    # duplicated closing point, chord 4000 mm, quarter-chord origin
    loop = [(1.0, 0.0), (0.5, 0.05), (0.0, 0.0), (0.5, -0.05), (1.0, 0.0)]
    want = [(3000.0, 0.0), (1000.0, 200.0), (-1000.0, 0.0), (1000.0, -200.0)]
    got = airPlaneStation.sectionCoordsMm(loop, 4000.0)
    assert len(got) == 4, \
        "TE seam duplicate not dropped: %d points, expected 4" % len(got)
    for (gu, gv), (wu, wv) in zip(got, want):
        assert abs(gu - wu) < 1e-9 and abs(gv - wv) < 1e-9, \
            "sectionCoordsMm %.3f,%.3f != hand-computed %.3f,%.3f" \
            % (gu, gv, wu, wv)
    vecs = [FreeCAD.Vector(x, 0.0, z) for x, z in loop]
    assert airPlaneStation.sectionCoordsMm(vecs, 4000.0) == got, \
        "Vector input and tuple input disagree"
    # a NON-duplicated loop must survive untouched (dedupe is seam-only)
    assert len(airPlaneStation.sectionCoordsMm(loop[:-1], 4000.0)) == 4, \
        "dedupe ate a real point, not the seam duplicate"


def gatePeriodicWire():
    pts = [FreeCAD.Vector(5000.0, 1000.0 * math.cos(2.0 * math.pi * i / 8.0),
                          1000.0 * math.sin(2.0 * math.pi * i / 8.0))
           for i in range(8)]
    w = airPlaneStation.periodicWire(pts)
    assert len(w.Edges) == 1, \
        "periodic wire is %d edges, not the single closed edge" \
        % len(w.Edges)
    assert w.isClosed() and w.isValid(), "periodic wire not closed/valid"
    # Station.wire: same single-edge closed wire, lying in the frame plane
    # X = sign * station (the mirrored port half included)
    for f in FRAMES:
        sec = f.wire([(1000.0, 0.0), (0.0, 1000.0), (-1000.0, 0.0),
                      (0.0, -1000.0)])
        assert len(sec.Edges) == 1 and sec.isClosed(), \
            "Station.wire is not the single closed periodic wire"
        assert sec.BoundBox.XLength < 1e-9, \
            "Station.wire leaves the frame plane X = %.1f" \
            % (f.sign * f.station)


def main():
    gates = [
        ("import purity (no PySide / FreeCADGui)", gatePurity),
        ("to3d vs independent reference math", gateTo3d),
        ("placement.multVec((u,0,v)) == to3d(u,v)", gatePlacement),
        ("linearSchedule chord/twist/sweep laws + guard", gateSchedule),
        ("sectionCoordsMm hand parity + TE seam dedupe", gateSectionCoords),
        ("periodicWire single-edge closed + frame plane", gatePeriodicWire),
    ]
    failed = []
    for name, fn in gates:
        try:
            fn()
            print("PASS  %s" % name)
        except AssertionError as err:
            failed.append(name)
            print("FAIL  %s: %s" % (name, err))
    print("%d/%d gates pass" % (len(gates) - len(failed), len(gates)))
    if failed:
        sys.stdout.flush()
        sys.exit(1)


try:  # same reason as the build guard above: never let freecadcmd eat it
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.stdout.flush()
    sys.exit(1)
