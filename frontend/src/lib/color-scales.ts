/**
 * Scientific oceanographic color scales based on cmocean specifications
 * Thermal (2-32 °C): Dark blue -> Cyan -> Green -> Yellow -> Orange -> Red
 * Balance / Diverging (-3 to +3 °C): Blue -> Light Cyan -> Off-white -> Orange -> Red
 * Amp / Uncertainty (0 to 2 °C): Dark purple -> Magenta -> Orange -> Pale Yellow
 */

export interface RGB {
  r: number;
  g: number;
  b: number;
}

function interpolateRgb(c1: RGB, c2: RGB, t: number): RGB {
  return {
    r: Math.round(c1.r + (c2.r - c1.r) * t),
    g: Math.round(c1.g + (c2.g - c1.g) * t),
    b: Math.round(c1.b + (c2.b - c1.b) * t),
  };
}

function sampleStops(stops: { val: number; color: RGB }[], normalized: number): RGB {
  const clamped = Math.max(0, Math.min(1, normalized));
  for (let i = 0; i < stops.length - 1; i++) {
    const s1 = stops[i];
    const s2 = stops[i + 1];
    if (clamped >= s1.val && clamped <= s2.val) {
      const t = (clamped - s1.val) / (s2.val - s1.val);
      return interpolateRgb(s1.color, s2.color, t);
    }
  }
  return stops[stops.length - 1].color;
}

// 1. Thermal Colormap (cmocean.thermal: 2°C to 32°C)
const THERMAL_STOPS: { val: number; color: RGB }[] = [
  { val: 0.0, color: { r: 13, g: 17, b: 38 } },     // 2°C abyss
  { val: 0.15, color: { r: 18, g: 46, b: 96 } },    // ~6°C deep
  { val: 0.35, color: { r: 24, g: 110, b: 140 } },  // ~12°C
  { val: 0.55, color: { r: 42, g: 157, b: 120 } },  // ~18°C thermocline
  { val: 0.72, color: { r: 228, g: 158, b: 54 } },  // ~23°C
  { val: 0.88, color: { r: 232, g: 82, b: 42 } },   // ~28°C surface
  { val: 1.0, color: { r: 245, g: 45, b: 35 } },    // 32°C tropical warm pool
];

// 2. Diverging Colormap (cmocean.balance: -3°C to +3°C)
const BALANCE_STOPS: { val: number; color: RGB }[] = [
  { val: 0.0, color: { r: 27, g: 68, b: 150 } },    // -3°C
  { val: 0.25, color: { r: 76, g: 154, b: 219 } },  // -1.5°C
  { val: 0.5, color: { r: 242, g: 242, b: 242 } },   // 0°C (neutral)
  { val: 0.75, color: { r: 235, g: 133, b: 68 } },  // +1.5°C
  { val: 1.0, color: { r: 184, g: 34, b: 30 } },    // +3°C
];

// 3. Sequential Amp Colormap (Uncertainty: 0 to 2°C)
const AMP_STOPS: { val: number; color: RGB }[] = [
  { val: 0.0, color: { r: 15, g: 23, b: 42 } },     // 0°C
  { val: 0.3, color: { r: 79, g: 40, b: 115 } },    // 0.6°C
  { val: 0.6, color: { r: 180, g: 50, b: 105 } },   // 1.2°C
  { val: 0.85, color: { r: 236, g: 110, b: 64 } },  // 1.7°C
  { val: 1.0, color: { r: 254, g: 215, b: 102 } },  // 2.0°C
];

export function getThermalColor(tempC: number, min = 2, max = 32): string {
  const norm = (tempC - min) / (max - min);
  const { r, g, b } = sampleStops(THERMAL_STOPS, norm);
  return `rgb(${r}, ${g}, ${b})`;
}

export function getBalanceColor(diffC: number, min = -3, max = 3): string {
  const norm = (diffC - min) / (max - min);
  const { r, g, b } = sampleStops(BALANCE_STOPS, norm);
  return `rgb(${r}, ${g}, ${b})`;
}

export function getAmpColor(sigmaC: number, min = 0, max = 2): string {
  const norm = (sigmaC - min) / (max - min);
  const { r, g, b } = sampleStops(AMP_STOPS, norm);
  return `rgb(${r}, ${g}, ${b})`;
}

export function getColorByMode(
  value: number,
  mode: "poseidon" | "glorys" | "diff" | "sigma"
): string {
  switch (mode) {
    case "poseidon":
    case "glorys":
      return getThermalColor(value);
    case "diff":
      return getBalanceColor(value);
    case "sigma":
      return getAmpColor(value);
  }
}
