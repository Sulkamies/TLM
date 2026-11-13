"""IFC models (and the 2D plans rendered from them) via IfcOpenShell.

Every function returns {"value"/"result": ..., "evidence": [{"guid": ...}]} so
the viewer can highlight elements in the plan SVG (elements carry data-guid).
Quantities come from the model's own Qto_* sets; if a model has none, fall back
to ifcopenshell.util.shape / geometry (not implemented here).
"""
from __future__ import annotations

import functools
import os
import re

import ifcopenshell
import ifcopenshell.util.element as ue
import ifcopenshell.util.unit as uu


def model_path_for(path: str) -> str:
    """bsc-molio_molio-with-uris_plan-02-klder.pdf -> bsc-molio_molio-with-uris.ifc"""
    if path.lower().endswith(".ifc"):
        return path
    return re.sub(r"_plan-\d+-.*$", "", os.path.splitext(path)[0]) + ".ifc"


@functools.lru_cache(maxsize=8)
def open_model(path: str):
    return IfcModel(model_path_for(path))


class IfcModel:
    def __init__(self, path):
        self.f = ifcopenshell.open(path)
        self.schema = self.f.schema
        try:
            self.len_scale = uu.calculate_unit_scale(self.f)   # model length unit -> metres
        except Exception:
            self.len_scale = 1.0

    # ---------- spatial helpers ----------
    def storey_of(self, el):
        s = ue.get_container(el) or ue.get_aggregate(el)
        for _ in range(6):
            if s is None or s.is_a("IfcBuildingStorey"):
                return s
            s = ue.get_aggregate(s) or ue.get_container(s)
        return None

    def storeys(self):
        return [{"name": s.Name, "elevation_m": (s.Elevation or 0) * self.len_scale, "guid": s.GlobalId}
                for s in sorted(self.f.by_type("IfcBuildingStorey"), key=lambda s: s.Elevation or 0)]

    def _match_storey(self, el, storey):
        if not storey:
            return True
        s = self.storey_of(el)
        return s is not None and (s.Name or "").strip().casefold() == storey.strip().casefold()

    def _qto(self, el, *keys):
        for qset in ue.get_psets(el, qtos_only=True).values():
            for k in keys:
                if k in qset and qset[k] is not None:
                    return qset[k]
        return None

    # ---------- queries ----------
    def spaces(self, storey=None):
        out = []
        for sp in self.f.by_type("IfcSpace"):
            if not self._match_storey(sp, storey):
                continue
            s = self.storey_of(sp)
            out.append({"name": sp.Name, "long_name": getattr(sp, "LongName", None),
                        "storey": s.Name if s else None,
                        "net_area_m2": self._qto(sp, "NetFloorArea", "NetArea"),
                        "gross_area_m2": self._qto(sp, "GrossFloorArea", "GrossArea"),
                        "guid": sp.GlobalId})
        return out

    def space_area(self, label, storey=None):
        """label as written in questions, e.g. 'TUALETTRUUM (55-3)' or 'Gang (Rum nr. 501)'."""
        lab = label.strip().casefold()
        hits = []
        for s in self.spaces(storey):
            forms = {f"{s['long_name']} ({s['name']})", f"{s['name']} ({s['long_name']})",
                     str(s["name"]), str(s["long_name"])}
            if lab in {x.casefold() for x in forms if x}:
                hits.append(s)
        return {"value": sum(h["net_area_m2"] or 0 for h in hits) if hits else None,
                "result": hits, "evidence": [{"guid": h["guid"]} for h in hits]}

    def count(self, ifc_class, storey=None):
        els = [e for e in self.f.by_type(ifc_class) if self._match_storey(e, storey)]
        return {"value": len(els), "evidence": [{"guid": e.GlobalId} for e in els]}

    def quantity_sum(self, ifc_class, quantity, storey=None):
        """e.g. ('IfcSlab','NetVolume'), ('IfcWall','Length'), ('IfcWall','NetSideArea')."""
        total, used, missing = 0.0, [], 0
        for e in self.f.by_type(ifc_class):
            if not self._match_storey(e, storey):
                continue
            v = self._qto(e, quantity)
            if v is None:
                missing += 1
                continue
            total += v
            used.append({"guid": e.GlobalId})
        # Qto lengths are in the model's length unit (often mm); areas/volumes are
        # normally declared in m2/m3. Verify on one model with a known answer.
        if quantity in ("Length", "Width", "Height", "Depth", "Perimeter"):
            total *= self.len_scale
        return {"value": round(total, 3), "elements_with_quantity": len(used),
                "elements_missing_quantity": missing, "evidence": used}

    def elements(self, ifc_class, storey=None, limit=200):
        out = []
        for e in self.f.by_type(ifc_class)[: limit * 3]:
            if not self._match_storey(e, storey):
                continue
            t = ue.get_type(e)
            row = {"name": e.Name, "type": t.Name if t else None, "guid": e.GlobalId,
                   "storey": (self.storey_of(e).Name if self.storey_of(e) else None)}
            for attr in ("OverallWidth", "OverallHeight", "PredefinedType"):
                if hasattr(e, attr):
                    row[attr] = getattr(e, attr)
            psets = ue.get_psets(e)
            row["properties"] = {k: {pk: pv for pk, pv in v.items() if pk != "id"}
                                 for k, v in list(psets.items())[:6]}
            out.append(row)
            if len(out) >= limit:
                break
        return {"result": out, "evidence": [{"guid": r["guid"]} for r in out]}

    def overview(self):
        counts = {}
        for cls in ("IfcSpace", "IfcWall", "IfcDoor", "IfcWindow", "IfcSlab", "IfcColumn", "IfcBeam",
                    "IfcStair", "IfcRoof", "IfcRailing", "IfcFlowTerminal", "IfcDistributionElement"):
            try:
                counts[cls] = len(self.f.by_type(cls))
            except RuntimeError:  # class not in this schema
                pass
        apps = [a.ApplicationFullName for a in self.f.by_type("IfcApplication")]
        b = self.f.by_type("IfcBuilding")
        return {"schema": self.schema, "applications": apps,
                "project": [p.Name for p in self.f.by_type("IfcProject")],
                "building": [{"name": x.Name, "long_name": getattr(x, "LongName", None),
                              "description": x.Description,
                              "properties": ue.get_psets(x)} for x in b][:2],
                "storeys": self.storeys(), "counts": counts, "length_unit_to_m": self.len_scale}
