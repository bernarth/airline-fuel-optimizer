from __future__ import annotations
from dataclasses import dataclass
from math import radians, sin, cos, asin, sqrt
from pathlib import Path
import csv
import json
from typing import Dict, List, Tuple

NM_EARTH_RADIUS = 3440.065

@dataclass
class FlightPlan:
  flight_id: str
  origin_lat: float
  origin_lon: float
  dest_lat: float
  dest_lon: float
  planned_alt_ft: int

@dataclass
class AircraftPerf:
  base_fuel_burn_kg_per_nm: float
  altitude_efficiency: Dict[str, float]

def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
  lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
  dlat = lat2 - lat1
  dlon = lon2 - lon1
  a = sin(dlat / 2.0) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2.0) ** 2

  return 2.0 * NM_EARTH_RADIUS * asin(sqrt(a))

def _load_flights(data_dir: Path) -> Dict[str, FlightPlan]:
  rows: Dict[str, FlightPlan] = {}
  with open(data_dir / "flights.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
      rows[r["flight_id"]] = FlightPlan(
        flight_id=r["flight_id"],
        origin_lat=float(r["origin_lat"]),
        origin_lon=float(r["origin_lon"]),
        dest_lat=float(r["dest_lat"]),
        dest_lon=float(r["dest_lon"]),
        planned_alt_ft=int(r["planned_alt_ft"]),
      )

  return rows

def _load_aircraft(data_dir: Path) -> AircraftPerf:
  with open(data_dir / "aircraft.json", encoding="utf-8") as f:
    j = json.load(f)
  
  return AircraftPerf(
    base_fuel_burn_kg_per_nm=float(j["base_fuel_burn_kg_per_nm"]),
    altitude_efficiency={str(k): float(v) for k, v in j["altitude_efficiency"].items()},
  )

def _load_winds(data_dir: Path) -> Dict[int, float]:
  winds: Dict[int, float] = {}
  with open(data_dir / "weather.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
      winds[int(r["altitude_ft"])] = float(r["wind_component_knots"])

  return winds

def estimate_fuel_kg(distance_nm: float,
                     altitude_ft: int,
                     perf: AircraftPerf,
                     wind_component_knots: float) -> float:
  """Very simple model: burn_per_nm * distance * wind_penalty_factor.

  wind_penalty_factor = 1 + headwind_knots * 0.005 (tailwind reduces penalty to 1.0).
  """
  eff = perf.altitude_efficiency.get(str(altitude_ft), 1.0)
  burn_per_nm = perf.base_fuel_burn_kg_per_nm * eff
  headwind = max(0.0, -wind_component_knots)
  wind_penalty = 1.0 + headwind * 0.005

  return burn_per_nm * distance_nm * wind_penalty

def optimize_flight(flight_id: str, data_dir: Path) -> Dict:
  flights = _load_flights(data_dir)
  if flight_id not in flights:
    raise ValueError(f"Unknown flight_id: {flight_id}")

  flight = flights[flight_id]
  perf = _load_aircraft(data_dir)
  winds = _load_winds(data_dir)

  distance_nm = _haversine_nm(flight.origin_lat, flight.origin_lon, flight.dest_lat, flight.dest_lon)

  candidate_alts = [30000, 34000, 38000]
  results: List[Tuple[int, float]] = []

  for alt in candidate_alts:
    wind = winds.get(alt, 0.0)
    fuel = estimate_fuel_kg(distance_nm, alt, perf, wind)
    results.append((alt, fuel))

  baseline_alt = flight.planned_alt_ft
  baseline_wind = winds.get(baseline_alt, 0.0)
  baseline_fuel = estimate_fuel_kg(distance_nm, baseline_alt, perf, baseline_wind)

  best_alt, best_fuel = min(results, key=lambda x: x[1])
  savings = max(0.0, baseline_fuel - best_fuel)

  rationale = (
    f"Baseline alt {baseline_alt} ft fuel ≈ {baseline_fuel:.0f} kg. "
    f"Best alt {best_alt} ft fuel ≈ {best_fuel:.0f} kg. "
    f"Estimated savings ≈ {savings:.0f} kg by selecting {best_alt} ft "
    f"(simple headwind penalty model)."
  )

  return {
    "flight_id": flight.flight_id,
    "distance_nm": round(distance_nm, 1),
    "baseline": {
      "altitude_ft": baseline_alt,
      "fuel_kg": round(baseline_fuel, 1),
    },
    "optimized": {
      "altitude_ft": best_alt,
      "fuel_kg": round(best_fuel, 1),
      "projected_savings_kg": round(savings, 1),
    },
    "recommendation": (
      f"Climb to {best_alt} ft" if best_alt > baseline_alt
      else (f"Descend to {best_alt} ft" if best_alt < baseline_alt else "Maintain planned altitude")
    ),
    "rationale": rationale,
  }
