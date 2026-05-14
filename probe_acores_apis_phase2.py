#!/usr/bin/env python3
"""
Phase 2 — Açores APIs Deep Dive
================================
Reads the phase-1 output and drills into what's actually usable:
  1. Enumerate all 74 IDE.A collections with metadata
  2. For each Terceira-relevant collection, fetch sample features to see fields
  3. Find the correct IPMA location IDs for Terceira
  4. Probe SREA's WordPress custom post types properly
  5. Generate a clean catalog (catalog.md) ready for product design

Run after probe_acores_apis.py. Place in same folder.
Requires: requests   |   Optional: cloudscraper
"""
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

PHASE1 = Path("./azores_probe")
OUT = Path("./azores_probe_v2")
OUT.mkdir(exist_ok=True)
(OUT / "collections").mkdir(exist_ok=True)
(OUT / "samples").mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/geo+json, application/json, */*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
}

# Terceira island bounding box (WGS84 lon/lat)
TERCEIRA_BBOX = (-27.43, 38.63, -27.04, 38.84)

session = requests.Session()
session.headers.update(HEADERS)


# ─────────────────────────────────────────────────────────────────────────────
#  1. IDE.A — enumerate 74 collections
# ─────────────────────────────────────────────────────────────────────────────

def load_collections():
    src = PHASE1 / "responses" / "idea-collections.json"
    if not src.exists():
        print(f"  ! Missing {src} — run probe_acores_apis.py first.")
        return []
    data = json.loads(src.read_text(encoding="utf-8"))
    return data.get("collections", [])


def bbox_overlaps_terceira(extent):
    """Check if a collection's spatial extent intersects Terceira."""
    try:
        bbox = extent["spatial"]["bbox"][0]  # [minx, miny, maxx, maxy]
        tminx, tminy, tmaxx, tmaxy = TERCEIRA_BBOX
        return not (
            bbox[2] < tminx or bbox[0] > tmaxx or
            bbox[3] < tminy or bbox[1] > tmaxy
        )
    except (KeyError, IndexError, TypeError):
        return None  # unknown — don't exclude


def summarize_collections(cols):
    """Build a structured summary of all collections."""
    summary = []
    for c in cols:
        s = {
            "id": c.get("id"),
            "title": c.get("title", ""),
            "description": (c.get("description", "") or "")[:200],
            "item_type": c.get("itemType", "?"),
            "keywords": c.get("keywords", []),
            "covers_terceira": bbox_overlaps_terceira(c.get("extent", {})),
            "feature_count": None,  # filled in later
        }
        # Find items URL
        for link in c.get("links", []):
            if link.get("rel") == "items":
                s["items_url"] = link["href"]
                break
        summary.append(s)
    return summary


def sample_collection(coll):
    """Fetch a few items to inspect actual fields. Server-side filter to Terceira."""
    if coll["item_type"] != "feature" or not coll.get("items_url"):
        return None
    base = coll["items_url"]
    params = {
        "f": "json",
        "limit": 3,
        "bbox": ",".join(str(x) for x in TERCEIRA_BBOX),
    }
    url = f"{base}?{urlencode(params)}"
    try:
        r = session.get(url, timeout=20)
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}"}
        data = r.json()
        feats = data.get("features", [])
        # Save sample
        (OUT / "samples" / f"{coll['id']}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Collect property field names across samples
        fields = sorted({
            k for f in feats for k in (f.get("properties") or {}).keys()
        })
        geom_types = sorted({
            (f.get("geometry") or {}).get("type") for f in feats
            if f.get("geometry")
        })
        return {
            "numberMatched": data.get("numberMatched"),
            "numberReturned": data.get("numberReturned"),
            "fields": fields,
            "geometry_types": [g for g in geom_types if g],
            "sample_props": (feats[0].get("properties") if feats else None),
        }
    except Exception as e:
        return {"error": str(e)[:120]}


# ─────────────────────────────────────────────────────────────────────────────
#  2. IPMA — find correct Terceira location IDs
# ─────────────────────────────────────────────────────────────────────────────

def fix_ipma():
    """The locations endpoint lists every city ID. Find Terceira-relevant ones."""
    print("\n=== IPMA: finding correct Terceira location IDs ===")
    out = {}
    locations_url = "https://api.ipma.pt/open-data/distrits-islands.json"
    try:
        r = session.get(locations_url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            locs = data.get("data", [])
            terceira = [
                l for l in locs
                if "terceira" in (l.get("local", "") + l.get("idDistrito", "")).lower()
                or "angra" in l.get("local", "").lower()
                or "praia da vit" in l.get("local", "").lower()
            ]
            print(f"  Found {len(terceira)} Terceira-area locations:")
            for l in terceira:
                print(f"    - globalIdLocal={l.get('globalIdLocal')}  {l.get('local')}")
            out["terceira_locations"] = terceira
        else:
            print(f"  IPMA locations: HTTP {r.status_code}")
    except Exception as e:
        print(f"  IPMA locations: {e}")
    # Test a forecast using the first ID we found
    if out.get("terceira_locations"):
        gid = out["terceira_locations"][0]["globalIdLocal"]
        fc_url = f"https://api.ipma.pt/open-data/forecast/meteorology/cities/daily/{gid}.json"
        try:
            r = session.get(fc_url, timeout=15)
            print(f"  Forecast test (id={gid}): HTTP {r.status_code}")
            if r.status_code == 200:
                (OUT / "ipma_forecast_terceira.json").write_text(r.text, encoding="utf-8")
                out["forecast_url_template"] = fc_url
        except Exception as e:
            print(f"  Forecast test: {e}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  3. SREA WordPress — find Terceira-specific custom post types
# ─────────────────────────────────────────────────────────────────────────────

def explore_srea():
    print("\n=== SREA WordPress: discovering structure ===")
    types_path = PHASE1 / "responses" / "srea-wp-types.json"
    if not types_path.exists():
        print("  No srea-wp-types.json from phase 1")
        return {}
    types = json.loads(types_path.read_text(encoding="utf-8"))
    print(f"  Custom post types found: {list(types.keys())}")
    out = {"types": list(types.keys())}
    # Try a few promising types for content
    for slug in ["relatorio", "area", "ilha", "indicador", "estatistica"]:
        if slug in types:
            url = f"https://srea.azores.gov.pt/wp-json/wp/v2/{slug}?per_page=5"
            try:
                r = session.get(url, timeout=15)
                if r.status_code == 200:
                    items = r.json()
                    print(f"    {slug}: {len(items)} items returned")
                    out[slug] = [
                        {"id": i.get("id"), "title": i.get("title", {}).get("rendered"), "link": i.get("link")}
                        for i in items[:5]
                    ]
            except Exception as e:
                print(f"    {slug}: {e}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  4. Generate the catalog
# ─────────────────────────────────────────────────────────────────────────────

def write_catalog(summary, terceira_ones, ipma_info, srea_info):
    lines = ["# Açores Data Catalog — Terceira Focus\n"]
    lines.append(f"_Generated {time.strftime('%Y-%m-%d %H:%M')}_\n\n")

    lines.append(f"## IDE.A — {len(summary)} collections total\n")
    lines.append(f"**Terceira-relevant: {len(terceira_ones)}** "
                 f"(by spatial extent or unknown — not excluded)\n\n")

    # Group by item_type
    by_type = {}
    for c in summary:
        by_type.setdefault(c["item_type"], []).append(c)
    for t, items in by_type.items():
        lines.append(f"### Item type: `{t}` ({len(items)})\n")
        for c in sorted(items, key=lambda x: x["id"] or ""):
            cov = "✓" if c["covers_terceira"] else ("?" if c["covers_terceira"] is None else "✗")
            fc = c.get("feature_count")
            fc_str = f" — {fc:,} features" if isinstance(fc, int) else ""
            fields = c.get("fields") or []
            fld_str = f" — fields: {', '.join(fields[:8])}" if fields else ""
            lines.append(f"- [{cov}] **`{c['id']}`** — {c['title']}{fc_str}{fld_str}\n")
        lines.append("\n")

    if ipma_info.get("terceira_locations"):
        lines.append("## IPMA — Terceira location IDs\n")
        for l in ipma_info["terceira_locations"]:
            lines.append(f"- `globalIdLocal={l.get('globalIdLocal')}` → {l.get('local')}\n")
        if ipma_info.get("forecast_url_template"):
            lines.append(f"\nForecast URL pattern: `{ipma_info['forecast_url_template']}`\n")
        lines.append("\n")

    if srea_info.get("types"):
        lines.append("## SREA WordPress\n")
        lines.append(f"Custom post types: {', '.join(srea_info['types'])}\n\n")
        for slug in ["relatorio", "area", "ilha"]:
            if slug in srea_info:
                lines.append(f"### `/wp-json/wp/v2/{slug}` — sample\n")
                for i in srea_info[slug]:
                    lines.append(f"- {i['title']} ({i['link']})\n")
                lines.append("\n")

    (OUT / "catalog.md").write_text("".join(lines), encoding="utf-8")
    print(f"\n✓ Catalog written to {OUT/'catalog.md'}")


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 78)
    print("PHASE 2 — Deep Dive")
    print("=" * 78)

    cols = load_collections()
    print(f"\nLoaded {len(cols)} IDE.A collections from phase 1.")
    summary = summarize_collections(cols)

    # Sample features from each collection
    print("\n=== Sampling features from each collection (Terceira bbox) ===")
    for i, c in enumerate(summary, 1):
        if c["item_type"] != "feature":
            continue
        print(f"  [{i:2}/{len(summary)}] {c['id']}", end=" ")
        sample = sample_collection(c)
        if sample is None:
            print("(skipped)")
            continue
        if "error" in sample:
            print(f"✗ {sample['error']}")
        else:
            c["feature_count"] = sample.get("numberMatched")
            c["fields"] = sample.get("fields", [])
            c["geometry_types"] = sample.get("geometry_types", [])
            print(f"✓ {sample.get('numberReturned')} returned of {sample.get('numberMatched')} matched")
        time.sleep(0.5)

    # Filter Terceira-relevant collections (covers_terceira=True or unknown=None, with features in bbox)
    terceira_ones = [
        c for c in summary
        if c["covers_terceira"] is not False
        and (c.get("feature_count") is None or c.get("feature_count", 0) > 0)
    ]

    # IPMA
    ipma_info = fix_ipma()

    # SREA
    srea_info = explore_srea()

    # Write outputs
    (OUT / "collections_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_catalog(summary, terceira_ones, ipma_info, srea_info)

    print("\n" + "=" * 78)
    print(f"Done. Open {OUT/'catalog.md'} for the structured summary.")
    print(f"Full collection metadata at {OUT/'collections_summary.json'}")
    print(f"Per-collection samples at {OUT/'samples'}/")
    print("=" * 78)


if __name__ == "__main__":
    main()
