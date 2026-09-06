/**
 * Canonical discrete depth axis supplied by the Poseidon product contract.
 * These coordinates describe selectable layers only; they are not measurements.
 */
export const OCEAN_DEPTHS_M = [0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000] as const;

export const OCEAN_LAYER_COUNT = OCEAN_DEPTHS_M.length;
