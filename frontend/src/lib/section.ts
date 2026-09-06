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
  poseidon: number[][]; // [distance_index][depth_index]
  glorys: number[][];    // [distance_index][depth_index]
  diff: number[][];      // poseidon - glorys
  sigma: number[][];     // uncertainty (std dev in °C)
  d20_m: number[];       // 20°C isotherm depth per distance step
  mld_m: number[];       // Mixed layer depth per distance step
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

export const CURATED_DATES = [
  { date: "2020-05-18", label: "Cyclone Amphan (Super Cyclonic Storm)" },
  { date: "2019-04-15", label: "Pre-monsoon thermal peak" },
  { date: "2019-08-03", label: "SW Monsoon upwelling (Somali Current)" },
  { date: "2020-11-25", label: "Cyclone Nivar (Post-monsoon eddy)" },
  { date: "2019-01-15", label: "NE Monsoon winter cooling" },
];

/** Fast deterministic hash from date string */
function getDateHash(dateStr: string): number {
  let hash = 0;
  for (let i = 0; i < dateStr.length; i++) {
    hash = (hash << 5) - hash + dateStr.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

/** Calculate day of year (1 to 365) from YYYY-MM-DD */
function getDayOfYear(dateStr: string): number {
  const [y, m, d] = dateStr.split("-").map(Number);
  const now = new Date(y, (m || 1) - 1, d || 1);
  const start = new Date(y, 0, 0);
  const diff = now.getTime() - start.getTime();
  const oneDay = 1000 * 60 * 60 * 24;
  return Math.max(1, Math.min(365, Math.floor(diff / oneDay)));
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

/** Interpolates N points along a great circle between coordinate A and B */
export function interpolateTransectPoints(
  a: TransectCoordinate,
  b: TransectCoordinate,
  numPoints = 200
): { lats: number[]; lons: number[]; distances_km: number[]; totalKm: number } {
  const totalKm = calculateDistanceKm(a, b);
  const lats: number[] = [];
  const lons: number[] = [];
  const distances_km: number[] = [];

  for (let i = 0; i < numPoints; i++) {
    const fraction = i / (numPoints - 1);
    const lat = a.lat + (b.lat - a.lat) * fraction;
    const lon = a.lon + (b.lon - a.lon) * fraction;
    const dist = Math.round(totalKm * fraction);

    lats.push(Number(lat.toFixed(3)));
    lons.push(Number(lon.toFixed(3)));
    distances_km.push(dist);
  }

  return { lats, lons, distances_km, totalKm };
}

/** Generates realistic vertical ocean cross-section data for any transect and date */
export function generateSectionData(
  a: TransectCoordinate,
  b: TransectCoordinate,
  date = "2020-05-18",
  numPoints = 120
): SectionData {
  const { lats, lons, distances_km, totalKm } = interpolateTransectPoints(a, b, numPoints);
  const depths_m = OCEAN_DEPTHS_M;

  const poseidon: number[][] = [];
  const glorys: number[][] = [];
  const diff: number[][] = [];
  const sigma: number[][] = [];
  const d20_m: number[] = [];
  const mld_m: number[] = [];

  const dateHash = getDateHash(date);
  const dayOfYear = getDayOfYear(date);

  // Distinct physical regime presets for key dates or annual sinusoidal simulation
  let surfaceBaseTemp = 28.5 + 2.0 * Math.sin(((dayOfYear - 80) * 2 * Math.PI) / 365);
  let baseThermocline = 105 + 15 * Math.sin(((dayOfYear - 120) * 2 * Math.PI) / 365);
  let baseMLD = 28 + 14 * Math.cos(((dayOfYear - 190) * 2 * Math.PI) / 180);
  let cycloneCoreFraction = -1; // No cyclone by default

  if (date === "2020-05-18") {
    // Cyclone Amphan: Extreme cold wake in northern/central Bay of Bengal
    surfaceBaseTemp = 29.8;
    baseThermocline = 85;
    cycloneCoreFraction = 0.42; // Upwelling vortex at ~42% along transect
  } else if (date === "2019-04-15") {
    // Pre-monsoon thermal peak: calm, superheated skin, deep thermocline
    surfaceBaseTemp = 31.5;
    baseThermocline = 128;
    baseMLD = 18;
  } else if (date === "2019-08-03") {
    // SW Monsoon Somali Current upwelling: strong west-east gradient
    surfaceBaseTemp = 27.2;
    baseThermocline = 72;
    baseMLD = 44;
  } else if (date === "2020-11-25") {
    // Cyclone Nivar: localized storm upwelling
    surfaceBaseTemp = 28.2;
    baseThermocline = 96;
    cycloneCoreFraction = 0.65;
  } else if (date === "2019-01-15") {
    // NE Monsoon winter cooling: deep convective mixed layer
    surfaceBaseTemp = 25.8;
    baseThermocline = 115;
    baseMLD = 58;
  } else {
    // Custom date perturbation
    const seedOffset = ((dateHash % 40) - 20) * 0.05;
    surfaceBaseTemp += seedOffset;
    baseThermocline += (dateHash % 30) - 15;
  }

  for (let i = 0; i < numPoints; i++) {
    const frac = i / (numPoints - 1);
    const lat = lats[i];
    const lon = lons[i];

    // Upwelling dynamics along the path
    let localThermocline = baseThermocline + Math.sin(frac * Math.PI * 1.8 + lat * 0.1) * 22;
    let localSurfaceTemp = surfaceBaseTemp;
    let localMLD = Math.max(14, Math.round(baseMLD + Math.cos(frac * 3.5 + (dateHash % 7)) * 10));

    // If there is an active cyclone core (e.g. Cyclone Amphan or Nivar)
    if (cycloneCoreFraction >= 0) {
      const distFromStorm = Math.abs(frac - cycloneCoreFraction);
      if (distFromStorm < 0.25) {
        const stormIntensity = 1 - distFromStorm / 0.25;
        // Intense thermocline suction/shoaling
        localThermocline -= stormIntensity * 45;
        // Surface cooling wake (up to 3.2°C drop)
        localSurfaceTemp -= stormIntensity * 3.2;
        // Mixed layer deepening under cyclonic wind stress
        localMLD += Math.round(stormIntensity * 25);
      }
    }

    // Longitudinal tilt (e.g. western Arabian Sea upwelling cooler than eastern Bay)
    if (lon < 65) {
      localSurfaceTemp -= 1.8;
      localThermocline -= 18;
    } else if (lon > 85) {
      localSurfaceTemp += 0.8;
    }

    mld_m.push(localMLD);

    const posRow: number[] = [];
    const gloRow: number[] = [];
    const diffRow: number[] = [];
    const sigRow: number[] = [];

    let calculatedD20 = Math.round(localThermocline);

    for (let dIdx = 0; dIdx < depths_m.length; dIdx++) {
      const z = depths_m[dIdx];

      // Physical tanh ocean stratification profile
      const thermoclineGrad = Math.tanh((z - localThermocline) / 52);
      const tempMean = (localSurfaceTemp - 4.2) * (0.5 - 0.5 * thermoclineGrad) + 4.2;

      // Small natural horizontal eddy perturbations with date-dependent phase
      const eddyPhase = (dateHash % 100) / 10;
      const eddyPerturbation = Math.sin(frac * 7 + z * 0.012 + eddyPhase) * 0.4;
      const posVal = Number(Math.max(3.6, tempMean + eddyPerturbation).toFixed(2));

      // Reanalysis difference
      const diffDrift = Number(
        (
          Math.sin(frac * 4.8 + z * 0.015 + eddyPhase * 0.5) * 0.38 +
          (z > 75 && z < 250 ? -0.22 : 0.06)
        ).toFixed(2)
      );
      const gloVal = Number((posVal - diffDrift).toFixed(2));

      // Uncertainty highest in thermocline and higher during cyclonic disturbance
      const stormExtraSigma = cycloneCoreFraction >= 0 && Math.abs(frac - cycloneCoreFraction) < 0.2 ? 0.35 : 0;
      const uncertainty = Number(
        (0.28 + stormExtraSigma + Math.exp(-Math.pow((z - localThermocline) / 65, 2)) * 0.72).toFixed(2)
      );

      posRow.push(posVal);
      gloRow.push(gloVal);
      diffRow.push(diffDrift);
      sigRow.push(uncertainty);

      if (posVal <= 20.0 && calculatedD20 === Math.round(localThermocline)) {
        const prevZ = dIdx > 0 ? depths_m[dIdx - 1] : 0;
        const prevT = dIdx > 0 ? posRow[dIdx - 1] : localSurfaceTemp;
        if (prevT > 20.0 && prevT !== posVal) {
          calculatedD20 = Math.round(prevZ + ((prevT - 20.0) / (prevT - posVal)) * (z - prevZ));
        } else {
          calculatedD20 = z;
        }
      }
    }

    d20_m.push(calculatedD20);
    poseidon.push(posRow);
    glorys.push(gloRow);
    diff.push(diffRow);
    sigma.push(sigRow);
  }

  // Date-dependent Argo floats
  const argo_markers: ArgoMarker[] = [];
  if (totalKm > 200) {
    const floatSeed = dateHash % 1000;
    const marker1Frac = 0.2 + ((floatSeed % 20) / 100);
    const marker2Frac = 0.65 + (((floatSeed * 3) % 25) / 100);

    argo_markers.push({
      distance_km: Math.round(totalKm * marker1Frac),
      wmo: `290${2100 + (dateHash % 90)}`,
      day_offset: (dateHash % 3) - 1,
    });
    argo_markers.push({
      distance_km: Math.round(totalKm * marker2Frac),
      wmo: `290${3400 + (dateHash % 85)}`,
      day_offset: (dateHash % 2),
    });

    if (totalKm > 1000) {
      argo_markers.push({
        distance_km: Math.round(totalKm * 0.48),
        wmo: `290${1800 + (dateHash % 70)}`,
        day_offset: 0,
      });
    }
  }

  return {
    distances_km,
    lats,
    lons,
    depths_m,
    poseidon,
    glorys,
    diff,
    sigma,
    d20_m,
    mld_m,
    argo_markers,
    totalDistanceKm: totalKm,
  };
}
