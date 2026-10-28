#################################################
#
# Wing station frames and section wires - Aircraft
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

"""
Station frames, linear schedules and section wires for lofted wings.

A Station is the rigid frame of one wing section: the plane X = +-station
with the chord along +Y (aft) and the thickness along +Z, rotated by the
local twist about the quarter-chord point.  Station.placement() returns the
FreeCAD.Placement that airPlaneCavity's schedule contract expects: APD maps
section (u, v) to (u, 0, v), Rz(90) takes that to (0, u, v), Rx(-twist) to
(0, u*ca + v*sa, -u*sa + v*ca), and the Base IS the quarter-chord point of
the station - so placement.multVec((u, 0, v)) == Station.to3d(u, v) term
for term (verified in tests/testStation.py).

linearSchedule() applies the straight-taper law: linear chord root->tip
over the semi-span, linear twist washout to zero at the tip, quarter-chord
sweep as the Y offset.

sectionCoordsMm() maps a unit-chord section (the generateNacaCoords output
convention: trailing edge first, upper surface to the nose, lower surface
back) to section-plane mm at the quarter-chord origin, dropping the
duplicated trailing-edge seam point at the same threshold convention as
airPlaneCavity.

periodicWire() is the single closed (periodic) B-spline wire.  Its measured
OCC integration artifact is DOCUMENTED at the function and relied upon by
consumers - read it before touching the wire.

No FreeCADGui, no PySide, no side effects at import - the module is usable
from freecadcmd scripts and the workbench alike, with no registration.
"""

__title__ = "FreeCAD airPlaneStation"
__author__ = "RedxHerring"
__url__ = "https://fredsfactory.fr"


import FreeCAD, Part

from math import atan2
from math import cos
from math import degrees
from math import sin
from math import tan


class Station(object):
    """
    Rigid frame of one wing section: the plane X = +-station, chord along
    +Y (aft), thickness along +Z, rotated by twistRad about the quarter-
    chord point.  The port half uses sign = -1, which mirrors the station
    but leaves the in-plane (u, v) axes identical, so an inward offset
    keeps its sign across the centreline.

    chordMm rides along so a schedule list is self-contained (a station's
    chord is an input, not a law - the frame itself never reads it).
    """

    def __init__(self, stationMm, yRefMm, twistRad, sign, chordMm=0.0):
        self.ca, self.sa = cos(twistRad), sin(twistRad)
        self.station, self.y_ref, self.sign = stationMm, yRefMm, sign
        self.chordMm = chordMm

    def to3d(self, u, v):
        """
        Section-plane (u, v) mm -> global point: u aft-positive along the
        twisted chord, v up.  The frame law, verbatim.
        """
        return FreeCAD.Vector(self.sign * self.station,
                              self.y_ref + u * self.ca + v * self.sa,
                              -u * self.sa + v * self.ca)

    def placement(self):
        """
        The airPlaneCavity schedule placement of this frame: Rz(90) then
        Rx(-twist), Base at the quarter-chord point (sign * station,
        y_ref, 0).  Satisfies placement.multVec((u, 0, v)) == to3d(u, v) -
        the equivalence airPlaneCavity consumers may rely on instead of a
        second frame implementation.
        """
        tw = degrees(atan2(self.sa, self.ca))
        return FreeCAD.Placement(
            FreeCAD.Vector(self.sign * self.station, self.y_ref, 0.0),
            FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), -tw).multiply(
                FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90.0)))

    def wire(self, pts2d):
        """Closed periodic section wire through section-plane (u, v) pairs
        (see periodicWire for the measured face-integration artifact)."""
        return periodicWire([self.to3d(u, v) for u, v in pts2d])


def linearSchedule(rootChordMm, tipChordMm, halfSpanMm, twistRootRad,
                   sweepRad, nStations=2):
    """
    Straight-taper schedule as a list of Stations over the starboard half,
    root (s = 0) to tip (s = halfSpanMm), sign = +1:

        chord(s) = rootChordMm + (tipChordMm - rootChordMm) * s / halfSpan
        twist(s) = twistRootRad * (1 - s / halfSpan)      (washout to 0)
        y_ref(s) = tan(sweepRad) * s                      (q-chord sweep)

    nStations >= 2 samples the law inclusively at both ends; the default
    returns the two end frames, which fully define the linear law.  The
    port mirror of a Station is Station(station, y_ref, twist, -1, chord):
    the in-plane axes are identical by construction, so mirrored sections
    keep an inward offset inward across the centreline.
    """
    if nStations < 2:
        raise ValueError("nStations must be >= 2, got %d" % nStations)
    out = []
    for i in range(nStations):
        s = halfSpanMm * i / (nStations - 1)
        out.append(Station(s, tan(sweepRad) * s,
                           twistRootRad * (1.0 - s / halfSpanMm), 1.0,
                           rootChordMm + (tipChordMm - rootChordMm)
                           * (s / halfSpanMm)))
    return out


def sectionCoordsMm(coords, chordMm):
    """
    Unit-chord closed ordered section -> section-plane (u, v) mm pairs,
    origin at the quarter-chord point: u = (x - 0.25) * chord (aft
    positive), v = z * chord (up).

    Accepts FreeCAD.Vector (the generateNacaCoords output) or plain (x, z)
    tuples.  A duplicated closing point at a sharp trailing edge is dropped
    at the same 1e-12 threshold convention as airPlaneCavity's normaliser:
    the seam duplicate would zero one tangent downstream.
    """
    pts = []
    for p in coords:
        x = float(p.x) if hasattr(p, "x") else float(p[0])
        z = float(p.z) if hasattr(p, "x") else float(p[1])
        pts.append(((x - 0.25) * chordMm, z * chordMm))
    if len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) < 1e-12 \
            and abs(pts[0][1] - pts[-1][1]) < 1e-12:
        pts.pop()
    return pts


def periodicWire(pts3d):
    """
    Periodic B-spline wire through 3D points (smooth closed profile): ONE
    closed edge, no seam vertex.

    MEASURED OCC ARTIFACT, recorded deliberately: a Part.Face bounded by
    this single periodic edge under-integrates its Area by -0.176% and a
    normal extrude loses a t/c-dependent factor (x0.871-0.942 measured
    across t/c 0.12-0.22).  A control face bounded by a single CIRCULAR
    edge extrudes at ratio 1.000000, so the artifact belongs to the
    periodic-spline FACE TYPE, not to OCC in general.  Consumers depend on
    the factor - their regression bands are struck WITH it; do not "fix"
    this wire.  A two-edge (upper + lower, shared LE/TE vertices) wire is
    the same closed curve whose face integrates correctly, but it is a
    different sampling contract and belongs to the consumer's measurement
    recipe, not to this module.
    """
    bs = Part.BSplineCurve()
    bs.interpolate(pts3d, PeriodicFlag=True)
    return Part.Wire([bs.toShape()])
