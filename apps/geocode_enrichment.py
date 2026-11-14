import json
import time
from typing import Tuple, Any, Optional
import httpx
import pgeocode
import reverse_geocoder as rg
import us

INPUT_FILE = "./shopper-domain/data/us_supermarkets.geojson"
OUTPUT_FILE = "./shopper-domain/data/us_supermarkets_enriched.geojson"

# Set to True to resolve missing street addresses via Photon for all supermarkets,
# or provide a list of substrings (e.g. ["macey", "ralphs", "vons"]) to limit HTTP calls.
ENRICH_ALL_MISSING_STREETS = True
TARGET_BANNERS_FOR_STREET_LOOKUP: list[str] = []


def extract_centroid(geometry: dict[str, Any]) -> Optional[Tuple[float, float]]:
  """Return (lat, lon) centroid for Point, LineString, Polygon, or MultiPolygon."""
  geom_type = geometry.get("type")
  coords = geometry.get("coordinates")
  if not coords:
    return None

  if geom_type == "Point" and len(coords) >= 2:
    return float(coords[1]), float(coords[0])

  if geom_type == "LineString" and len(coords) >= 2:
    ring = (
        coords[:-1] if len(coords) > 2 and coords[0] == coords[-1] else coords
    )
    return (
        sum(p[1] for p in ring) / len(ring),
        sum(p[0] for p in ring) / len(ring),
    )

  if geom_type == "Polygon" and coords[0]:
    ring = (
        coords[0][:-1]
        if len(coords[0]) > 2 and coords[0][0] == coords[0][-1]
        else coords[0]
    )
    return (
        sum(p[1] for p in ring) / len(ring),
        sum(p[0] for p in ring) / len(ring),
    )

  if geom_type == "MultiPolygon" and coords[0] and coords[0][0]:
    ring = coords[0][0]
    ring = ring[:-1] if len(ring) > 2 and ring[0] == ring[-1] else ring
    return (
        sum(p[1] for p in ring) / len(ring),
        sum(p[0] for p in ring) / len(ring),
    )

  return None


def reverse_geocode_photon(
    client: httpx.Client, lat: float, lon: float
) -> dict[str, Any]:
  """Fallback HTTP reverse lookup via Photon (OSM-based) when street address is missing."""
  try:
    resp = client.get(
        "https://photon.komoot.io/reverse",
        params={"lat": lat, "lon": lon},
    )
    if resp.status_code == 200:
      features = resp.json().get("features", [])
      if features:
        return features[0].get("properties", {})
  except Exception:
    pass
  return {}


def should_lookup_street(props: dict[str, Any]) -> bool:
  if ENRICH_ALL_MISSING_STREETS:
    return True
  if not TARGET_BANNERS_FOR_STREET_LOOKUP:
    return False
  searchable = (
      f"{props.get('name', '')} {props.get('brand', '')} {props.get('operator', '')}"
  ).lower()
  return any(banner.lower() in searchable for banner in TARGET_BANNERS_FOR_STREET_LOOKUP)


def main() -> None:
  nomi_zip = pgeocode.Nominatim("us")

  with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

  features = data.get("features", [])

  # 1. Extract centroids for all valid geometries (Point, LineString, Polygon, MultiPolygon)
  coords: list[Tuple[float, float]] = []
  centroid_by_idx: dict[int, Tuple[float, float]] = {}

  for idx, feat in enumerate(features):
    centroid = extract_centroid(feat.get("geometry", {}))
    if centroid is not None:
      coords.append(centroid)
      centroid_by_idx[idx] = centroid

  # 2. Batch offline reverse-geocode in single-threaded mode (Windows-safe)
  offline_geo = rg.search(coords, mode=1) if coords else []
  geo_by_idx = dict(zip(centroid_by_idx.keys(), offline_geo))

  offline_enriched = 0
  street_enriched = 0

  with httpx.Client(
      headers={"User-Agent": "MealShopper-SeedEnricher/1.0"}, timeout=10.0
  ) as client:
    for idx, feat in enumerate(features):
      props = feat.setdefault("properties", {})
      had_city = bool(props.get("addr:city"))
      had_state = bool(props.get("addr:state"))

      # Step A: Deterministic ZIP -> city/state lookup via pgeocode
      postcode = str(props.get("addr:postcode", "")).strip()[:5]
      if postcode and (not props.get("addr:city") or not props.get("addr:state")):
        z_info = nomi_zip.query_postal_code(postcode)
        if isinstance(z_info.place_name, str) and not props.get("addr:city"):
          props["addr:city"] = z_info.place_name
        if isinstance(z_info.state_code, str) and not props.get("addr:state"):
          props["addr:state"] = z_info.state_code

      # Step B: Offline coordinate -> city/state lookup via reverse_geocoder
      if idx in geo_by_idx:
        rg_hit = geo_by_idx[idx]
        if not props.get("addr:city") and rg_hit.get("name"):
          props["addr:city"] = rg_hit["name"]
        if not props.get("addr:state") and rg_hit.get("admin1"):
          state_obj = us.states.lookup(rg_hit["admin1"])
          if state_obj:
            props["addr:state"] = state_obj.abbr

      if (not had_city and props.get("addr:city")) or (
          not had_state and props.get("addr:state")
      ):
        offline_enriched += 1

      # Step C: Optional HTTP Photon lookup when street address is missing
      has_street = bool(
          props.get("addr:street")
          or props.get("addr:full")
          or props.get("street_address")
      )
      if not has_street and idx in centroid_by_idx and should_lookup_street(props):
        lat, lon = centroid_by_idx[idx]
        photon = reverse_geocode_photon(client, lat, lon)
        if photon.get("street"):
          props["addr:street"] = photon["street"]
          if photon.get("housenumber"):
            props["addr:housenumber"] = photon["housenumber"]
          if photon.get("postcode") and not props.get("addr:postcode"):
            props["addr:postcode"] = photon["postcode"]
          street_enriched += 1
          time.sleep(0.25)

  with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f)

  print(
      f"Done. Processed {len(features)} features: backfilled city/state on"
      f" {offline_enriched} features and resolved {street_enriched} missing"
      " street addresses."
  )


if __name__ == "__main__":
  main()