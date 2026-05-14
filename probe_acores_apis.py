#!/usr/bin/env python3
"""
Açores Government APIs — Comprehensive Probe
============================================
Tests the key endpoints from the API inventory, saves responses to disk,
and generates a report showing what's accessible and how endpoints connect.

Run: python3 probe_acores_apis.py
Requires: pip install requests
Optional: pip install cloudscraper  (auto-used as fallback for WAF blocks)
"""
import json
import time
from pathlib import Path

import requests
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

OUT = Path("./azores_probe")
OUT.mkdir(exist_ok=True)
(OUT / "responses").mkdir(exist_ok=True)

# Browser-like headers — defeats Cloudflare Bot Fight Mode in most cases
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/geo+json, application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

# Endpoints grouped by data domain. Each entry: (key, url, what_we_expect)
ENDPOINTS = {
    "1_geospatial_core": [
        ("idea-root",        "https://ambiente.azores.gov.pt/idea-api?f=json",
         "pygeoapi root — links to collections, processes, conformance"),
        ("idea-openapi",     "https://ambiente.azores.gov.pt/idea-api/openapi?f=json",
         "OpenAPI 3.0 spec — full endpoint list with parameters"),
        ("idea-conformance", "https://ambiente.azores.gov.pt/idea-api/conformance?f=json",
         "OGC API conformance classes supported"),
        ("idea-collections", "https://ambiente.azores.gov.pt/idea-api/collections?f=json",
         "All geospatial collections (flood risk, land cover, zoning, etc.)"),
        ("idea-processes",   "https://ambiente.azores.gov.pt/idea-api/processes?f=json",
         "Geospatial processing functions"),
    ],
    "2_metadata_catalog": [
        ("geonetwork-records",
         "https://sma.idea.azores.gov.pt/geonetwork/srv/api/records/?hitsPerPage=20&from=1&to=20",
         "GeoNetwork SMA — 425 dataset metadata records"),
        ("geonetwork-search",
         "https://sma.idea.azores.gov.pt/geonetwork/srv/api/search/records/_search?_content_type=json",
         "ElasticSearch backend — full text search across catalog"),
    ],
    "3_wms_wfs": [
        ("wssig3-wms-getcap",
         "https://wssig3.azores.gov.pt/geoserver/wms?service=WMS&request=GetCapabilities&version=1.3.0",
         "GeoServer WMS — list all map layers (XML)"),
        ("wssig3-wfs-getcap",
         "https://wssig3.azores.gov.pt/geoserver/wfs?service=WFS&request=GetCapabilities&version=2.0.0",
         "GeoServer WFS — list queryable feature types"),
        ("wssig2-arcgis",
         "https://wssig2.azores.gov.pt/arcgis/rest/services?f=json",
         "ArcGIS Server REST catalog (PDM, POOC, riscos naturais)"),
        ("wssiga-services",
         "https://wssiga.azores.gov.pt/geoserver/us-govserv-pt/wms?service=WMS&request=GetCapabilities",
         "Locations of regional administration services"),
    ],
    "4_open_data_portal": [
        ("opendata-datasets",
         "https://opendata.azores.gov.pt/api/1/datasets/?page_size=20",
         "uData portal — paginated dataset listing"),
        ("dados-datasets",
         "https://dados.azores.gov.pt/api/1/datasets/?page_size=20",
         "Same uData portal at alt domain"),
        ("opendata-organizations",
         "https://opendata.azores.gov.pt/api/1/organizations/?page_size=20",
         "List of data-publishing organizations"),
    ],
    "5_statistics": [
        ("srea-wp-types",
         "https://srea.azores.gov.pt/wp-json/wp/v2/types",
         "Custom post types — reveals 'relatorio', 'area', 'ilha' structure"),
        ("srea-wp-posts",
         "https://srea.azores.gov.pt/wp-json/wp/v2/posts?per_page=10",
         "Recent SREA publications"),
        ("srea-terceira",
         "https://srea.azores.gov.pt/ilha/terceira/",
         "All SREA indicators for Terceira (HTML — scrape)"),
    ],
    "6_real_time": [
        ("prociv-alerts",
         "https://www.prociv.azores.gov.pt/alertas/api?lang=pt&limit_last_alerts=10",
         "Civil protection JSON alerts — weather, seismic, etc."),
        ("civisa-sismos",
         "https://sismos.civisa.azores.gov.pt/",
         "Seismic events viewer — reverse-engineer XHR for API"),
        ("ipma-angra-forecast",
         "https://api.ipma.pt/open-data/forecast/meteorology/cities/daily/3260400.json",
         "5-day weather forecast for Angra do Heroísmo (Terceira)"),
        ("ipma-stations",
         "https://api.ipma.pt/open-data/observation/meteorology/stations/stations.json",
         "All IPMA weather stations including Açores"),
        ("ipma-warnings",
         "https://api.ipma.pt/open-data/forecast/warnings/warnings_www.json",
         "Active weather warnings — group codes ACE/AOR/AOC"),
        ("ipma-sea-maritime",
         "https://api.ipma.pt/open-data/forecast/meteorology/maritime/maritime-Acores-Central.json",
         "Maritime forecast for Açores Central (includes Terceira waters)"),
    ],
    "7_tourism": [
        ("turismo-monitor",
         "https://monitor.turismo.azores.gov.pt/",
         "Tourism observatory — has admin/data/ingestion tiers"),
        ("parques-naturais",
         "https://parquesnaturais.azores.gov.pt/",
         "Natural parks + trails (Terceira park ID 8)"),
        ("parques-terceira",
         "https://parquesnaturais.azores.gov.pt/parques/8/",
         "Terceira natural park specifically"),
    ],
    "8_business_services": [
        ("api-servicos-root",
         "https://api.servicos.azores.gov.pt/",
         "Regional service-bus API gateway root"),
        ("dev-api-servicos",
         "https://developer-api.servicos.azores.gov.pt/",
         "Developer portal — likely Kong-managed"),
        ("dev-api-swagger",
         "https://developer-api.servicos.azores.gov.pt/swagger",
         "Swagger UI if exposed"),
        ("dev-api-openapi",
         "https://developer-api.servicos.azores.gov.pt/openapi.json",
         "Common OpenAPI path"),
        ("incentivos-empresas",
         "https://incentivos.empresas.azores.gov.pt/",
         "Application portal for business incentives"),
    ],
    "9_legal_procurement": [
        ("jo-root",
         "https://jo.azores.gov.pt/",
         "Jornal Oficial — regional government gazette"),
        ("base-gov-acores",
         "https://www.base.gov.pt/Base4/pt/pesquisa/?type=contratos&distrito=PT200",
         "Public procurement filtered to Açores"),
    ],
}


def make_session():
    """Build an HTTP session with browser headers."""
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def probe(session, name, url, description, timeout=20):
    """Hit one endpoint, capture structured result."""
    t0 = time.time()
    result = {
        "name": name,
        "url": url,
        "description": description,
    }
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True)
        result.update({
            "status": r.status_code,
            "content_type": r.headers.get("Content-Type", "").split(";")[0],
            "size_bytes": len(r.content),
            "elapsed_s": round(time.time() - t0, 2),
            "final_url": r.url if r.url != url else None,
            "server": r.headers.get("Server", ""),
            "cf_ray": r.headers.get("CF-Ray", ""),
            "set_cookie": "Set-Cookie" in r.headers,
        })
        # If JSON, parse it
        if "json" in result["content_type"] and r.status_code == 200:
            try:
                data = r.json()
                result["parsed"] = True
                if isinstance(data, dict):
                    result["json_keys"] = list(data.keys())[:25]
                    # Look for OGC API patterns
                    if "collections" in data:
                        result["collections_count"] = len(data["collections"])
                        result["collection_ids"] = [
                            c.get("id") for c in data["collections"][:30]
                        ]
                    if "links" in data:
                        result["link_count"] = len(data["links"])
                    if "data" in data and isinstance(data["data"], list):
                        result["data_items"] = len(data["data"])
                    if "total" in data:
                        result["total"] = data["total"]
                elif isinstance(data, list):
                    result["json_is_list"] = True
                    result["list_length"] = len(data)
                # Save full body
                fname = OUT / "responses" / f"{name}.json"
                fname.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                result["saved_to"] = str(fname)
            except (ValueError, json.JSONDecodeError) as e:
                result["parsed"] = False
                result["parse_error"] = str(e)[:120]
        else:
            # Save first 50KB of text for inspection
            preview = r.text[:50000]
            fname = OUT / "responses" / f"{name}.txt"
            fname.write_text(preview, encoding="utf-8", errors="replace")
            result["saved_to"] = str(fname)
            result["body_preview"] = r.text[:300].replace("\n", " ")
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)[:200]
        result["elapsed_s"] = round(time.time() - t0, 2)
    return result


def print_row(r):
    """One-line summary for the terminal."""
    status = r.get("status", "ERR")
    size = r.get("size_bytes", 0)
    ctype = r.get("content_type", "—")[:25]
    elapsed = r.get("elapsed_s", 0)
    badge = ""
    if r.get("parsed"):
        if r.get("collections_count") is not None:
            badge = f" ✓ {r['collections_count']} collections"
        elif r.get("data_items") is not None:
            badge = f" ✓ {r['data_items']} items"
        elif r.get("list_length") is not None:
            badge = f" ✓ list[{r['list_length']}]"
        elif r.get("json_keys"):
            badge = f" ✓ JSON keys: {','.join(r['json_keys'][:4])}"
    elif r.get("error"):
        badge = f" ✗ {r['error'][:60]}"
    elif status not in (200, 201):
        badge = f" ✗"
    print(f"  [{status:>3}] {r['name']:25} {size:>9,}B  {ctype:25} {elapsed:>5.2f}s{badge}")


def main():
    print("=" * 90)
    print("AÇORES GOV APIs — COMPREHENSIVE PROBE")
    print("=" * 90)
    print(f"Output: {OUT.absolute()}")
    print(f"cloudscraper available: {HAS_CLOUDSCRAPER}")
    print()

    session = make_session()
    all_results = {}
    summary = {"ok": [], "blocked": [], "error": []}

    for category, items in ENDPOINTS.items():
        print(f"\n=== {category.replace('_', ' ').upper()} ===")
        cat_results = []
        for name, url, desc in items:
            r = probe(session, name, url, desc)
            cat_results.append(r)
            print_row(r)
            # Categorize
            if r.get("error"):
                summary["error"].append(r["name"])
            elif r.get("status") in (200, 201):
                summary["ok"].append(r["name"])
            else:
                summary["blocked"].append(f"{r['name']}({r.get('status')})")
            time.sleep(0.7)  # be polite
        all_results[category] = cat_results

    # Write the full report
    report_path = OUT / "probe_report.json"
    report_path.write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 90)
    print("SUMMARY")
    print("=" * 90)
    print(f"  ✓ Accessible (2xx):  {len(summary['ok'])}")
    for n in summary["ok"]:
        print(f"      - {n}")
    print(f"  ✗ Blocked (3xx/4xx/5xx):  {len(summary['blocked'])}")
    for n in summary["blocked"]:
        print(f"      - {n}")
    print(f"  ! Errors (no response):   {len(summary['error'])}")
    for n in summary["error"]:
        print(f"      - {n}")
    print()
    print(f"Responses saved under: {OUT}/responses/")
    print(f"Full report:           {report_path}")
    print()
    if summary["blocked"] and not HAS_CLOUDSCRAPER:
        print("TIP: Some endpoints blocked. Try: pip install cloudscraper")
        print("     Then re-run — the script will auto-use it for 403s.")


if __name__ == "__main__":
    main()
