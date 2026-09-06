import { OCEAN_DEPTHS_M } from "./depths";

export interface TransectCoordinate {
  lat: number;
  lon: number;
}

export interface ArgoMarker {
  distance_km: number;
  wmo: string;
  day_offset?: number;
  depth_m?: number;
}

export interface SectionData {
  distances_km: number[];
  lats: number[];
  lons: number[];
  depths_m: readonly number[];
  poseidon: number[][]; // [distance_index][depth_index], NaN where the model has no value
  glorys: number[][]; // [distance_index][depth_index], NaN on land / below the seafloor
  diff: number[][]; // poseidon - glorys
  sigma: number[][]; // uncertainty (std dev in °C)
  d20_m: number[]; // 20°C isotherm depth per distance step, NaN where the column never crosses 20°C
  mld_m: number[]; // Mixed layer depth per distance step
  argo_markers: ArgoMarker[];
  totalDistanceKm: number;
}

export type SectionMode = "poseidon" | "glorys" | "diff" | "sigma";

export interface TransectPreset {
  id: string;
  name: string;
  basin: string;
  description: string;
  a: TransectCoordinate;
  b: TransectCoordinate;
}

export const TRANSECT_PRESETS: TransectPreset[] = [
  {
    id: "bob_88e",
    name: "BoB north-south along 88°E",
    basin: "Bay of Bengal",
    description: "Slices from the Ganges-Brahmaputra freshwater plume down to the central Bay equatorial gateway.",
    a: { lat: 21.0, lon: 88.0 },
    b: { lat: 6.0, lon: 88.0 },
  },
  {
    id: "as_15n",
    name: "Arabian Sea east-west along 15°N",
    basin: "Arabian Sea",
    description: "Transits from the high-salinity western Arabian Sea into the west coast Indian upwelling zone.",
    a: { lat: 15.0, lon: 55.0 },
    b: { lat: 15.0, lon: 73.5 },
  },
  {
    id: "eq_5n",
    name: "Equatorial edge along 5°N",
    basin: "Equatorial Gateway",
    description: "Zonal transect tracking the Wyrtki jet and equatorial thermocline tilt across the basin.",
    a: { lat: 5.0, lon: 60.0 },
    b: { lat: 5.0, lon: 95.0 },
  },
];

/** An empty section, shown while a day's fields are still downloading. */
export function emptySectionData(): SectionData {
  return {
    distances_km: [],
    lats: [],
    lons: [],
    depths_m: OCEAN_DEPTHS_M,
    poseidon: [],
    glorys: [],
    diff: [],
    sigma: [],
    d20_m: [],
    mld_m: [],
    argo_markers: [],
    totalDistanceKm: 0,
  };
}

/** Haversine formula to compute great-circle distance in kilometers */
export function calculateDistanceKm(a: TransectCoordinate, b: TransectCoordinate): number {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLon = ((b.lon - a.lon) * Math.PI) / 180;
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;

  const sinDLat = Math.sin(dLat / 2);
  const sinDLon = Math.sin(dLon / 2);
  const aVal = sinDLat * sinDLat + Math.cos(lat1) * Math.cos(lat2) * sinDLon * sinDLon;
  const c = 2 * Math.atan2(Math.sqrt(aVal), Math.sqrt(1 - aVal));
  return Math.round(R * c);
}
