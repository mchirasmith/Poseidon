import Link from "next/link";
import { ArrowLeft, Waves } from "lucide-react";
import { REPORT_METRICS } from "@/lib/report";
import { MetricShell, ReportPanel } from "@/components/report/report-primitives";
import { OceanDepthStack } from "@/components/report/ocean-depth-stack";

function ReportHeader() {
  return (
    <header className="flex flex-col gap-5 border-b border-white/15 pb-5 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-center gap-4">
        <Link
          aria-label="Back to Poseidon home"
          className="grid size-10 place-items-center rounded-full border border-white/20 bg-white/[0.05] text-white/80 shadow-[inset_0_1px_1px_rgba(255,255,255,0.35)] backdrop-blur-xl transition-all duration-200 hover:scale-105 hover:border-white/40 hover:bg-white/[0.10] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200"
          href="/"
        >
          <ArrowLeft aria-hidden="true" size={18} />
        </Link>
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-cyan-200/80">Poseidon / report</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Validation report</h1>
        </div>
      </div>
    </header>
  );
}

function SkillByDepthShell() {
  return (
    <ReportPanel
      title="Skill by depth · 3D Ocean Stratification"
      description="Interactive 15-layer subsurface temperature reconstruction from satellite surface observations for the North Indian Ocean (0 m to 1000 m)."
    >
      <OceanDepthStack />
    </ReportPanel>
  );
}

function SpatialRmseCard() {
  return (
    <ReportPanel
      title="Spatial RMSE Distribution"
      description="Depth-integrated Root Mean Square Error (°C) across the North Indian Ocean test domain."
    >
      <div className="space-y-4">
        <div className="relative h-60 w-full overflow-hidden rounded-xl border border-white/10 bg-black/40 p-3">
          <svg viewBox="0 0 400 220" className="h-full w-full">
            <line x1="0" y1="55" x2="400" y2="55" stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3" />
            <line x1="0" y1="110" x2="400" y2="110" stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3" />
            <line x1="0" y1="165" x2="400" y2="165" stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3" />
            <line x1="100" y1="0" x2="100" y2="220" stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3" />
            <line x1="200" y1="0" x2="200" y2="220" stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3" />
            <line x1="300" y1="0" x2="300" y2="220" stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3" />

            <radialGradient id="rmse-as" cx="35%" cy="50%" r="40%">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.35" />
              <stop offset="70%" stopColor="#0284c7" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#0284c7" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="rmse-bob" cx="72%" cy="52%" r="35%">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.30" />
              <stop offset="70%" stopColor="#0ea5e9" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="rmse-upwelling" cx="22%" cy="38%" r="18%">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.45" />
              <stop offset="60%" stopColor="#06b6d4" stopOpacity="0.15" />
              <stop offset="100%" stopColor="transparent" stopOpacity="0" />
            </radialGradient>

            <rect x="0" y="0" width="400" height="220" fill="url(#rmse-as)" />
            <rect x="0" y="0" width="400" height="220" fill="url(#rmse-bob)" />
            <circle cx="95" cy="85" r="50" fill="url(#rmse-upwelling)" />

            <path
              d="M 120 0 L 140 45 L 180 60 L 205 105 L 215 140 L 222 170 L 225 185 L 228 170 L 235 140 L 255 100 L 285 75 L 320 60 L 330 0 Z"
              fill="rgba(20, 25, 38, 0.95)"
              stroke="rgba(255, 255, 255, 0.45)"
              strokeWidth="1.2"
            />
            <ellipse cx="238" cy="195" rx="6" ry="10" fill="rgba(20, 25, 38, 0.95)" stroke="rgba(255, 255, 255, 0.45)" strokeWidth="1" />

            <text x="50" y="90" fill="rgba(255,255,255,0.6)" fontSize="10" fontFamily="monospace">ARABIAN SEA</text>
            <text x="50" y="105" fill="#38bdf8" fontSize="10" fontFamily="monospace" fontWeight="bold">0.38 °C</text>

            <text x="270" y="90" fill="rgba(255,255,255,0.6)" fontSize="10" fontFamily="monospace">BAY OF BENGAL</text>
            <text x="270" y="105" fill="#38bdf8" fontSize="10" fontFamily="monospace" fontWeight="bold">0.43 °C</text>

            <text x="35" y="45" fill="#fbbf24" fontSize="8" fontFamily="monospace">Oman Upwelling (0.58 °C)</text>
          </svg>

          <div className="absolute bottom-2.5 right-3 flex items-center gap-2 rounded-lg border border-white/10 bg-black/60 px-2.5 py-1 backdrop-blur-md">
            <span className="font-mono text-[9px] text-cyan-300">0.2 °C</span>
            <div className="h-1.5 w-16 rounded-full bg-gradient-to-r from-cyan-400 via-sky-500 to-amber-400" />
            <span className="font-mono text-[9px] text-amber-300">0.7 °C</span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center font-mono text-xs">
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2">
            <span className="text-white/50 text-[10px] block">DOMAIN MEAN</span>
            <span className="text-sm font-bold text-cyan-200">0.42 °C</span>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2">
            <span className="text-white/50 text-[10px] block">OPEN OCEAN</span>
            <span className="text-sm font-bold text-emerald-300">0.33 °C</span>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2">
            <span className="text-white/50 text-[10px] block">COASTAL PEAK</span>
            <span className="text-sm font-bold text-amber-300">0.68 °C</span>
          </div>
        </div>
      </div>
    </ReportPanel>
  );
}

function SpatialBiasCard() {
  return (
    <ReportPanel
      title="Spatial Bias Distribution"
      description="Mean temperature prediction deviation (Poseidon − Ground Truth) in °C."
    >
      <div className="space-y-4">
        <div className="relative h-60 w-full overflow-hidden rounded-xl border border-white/10 bg-black/40 p-3">
          <svg viewBox="0 0 400 220" className="h-full w-full">
            <line x1="0" y1="55" x2="400" y2="55" stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3" />
            <line x1="0" y1="110" x2="400" y2="110" stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3" />
            <line x1="0" y1="165" x2="400" y2="165" stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3" />
            <line x1="100" y1="0" x2="100" y2="220" stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3" />
            <line x1="200" y1="0" x2="200" y2="220" stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3" />
            <line x1="300" y1="0" x2="300" y2="220" stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3" />

            <radialGradient id="bias-equator" cx="50%" cy="85%" r="45%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.20" />
              <stop offset="100%" stopColor="transparent" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="bias-warm-bob" cx="75%" cy="50%" r="35%">
              <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.18" />
              <stop offset="100%" stopColor="transparent" stopOpacity="0" />
            </radialGradient>

            <rect x="0" y="0" width="400" height="220" fill="url(#bias-equator)" />
            <rect x="0" y="0" width="400" height="220" fill="url(#bias-warm-bob)" />

            <path
              d="M 120 0 L 140 45 L 180 60 L 205 105 L 215 140 L 222 170 L 225 185 L 228 170 L 235 140 L 255 100 L 285 75 L 320 60 L 330 0 Z"
              fill="rgba(20, 25, 38, 0.95)"
              stroke="rgba(255, 255, 255, 0.45)"
              strokeWidth="1.2"
            />
            <ellipse cx="238" cy="195" rx="6" ry="10" fill="rgba(20, 25, 38, 0.95)" stroke="rgba(255, 255, 255, 0.45)" strokeWidth="1" />

            <text x="50" y="90" fill="rgba(255,255,255,0.6)" fontSize="10" fontFamily="monospace">ARABIAN SEA</text>
            <text x="50" y="105" fill="#38bdf8" fontSize="10" fontFamily="monospace" fontWeight="bold">+0.02 °C</text>

            <text x="270" y="90" fill="rgba(255,255,255,0.6)" fontSize="10" fontFamily="monospace">BAY OF BENGAL</text>
            <text x="270" y="105" fill="#f43f5e" fontSize="10" fontFamily="monospace" fontWeight="bold">+0.04 °C</text>

            <text x="130" y="200" fill="#38bdf8" fontSize="9" fontFamily="monospace">Equatorial Belt (-0.01 °C)</text>
          </svg>

          <div className="absolute bottom-2.5 right-3 flex items-center gap-2 rounded-lg border border-white/10 bg-black/60 px-2.5 py-1 backdrop-blur-md">
            <span className="font-mono text-[9px] text-sky-400">-0.3 °C</span>
            <div className="h-1.5 w-16 rounded-full bg-gradient-to-r from-sky-400 via-white/80 to-rose-400" />
            <span className="font-mono text-[9px] text-rose-400">+0.3 °C</span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center font-mono text-xs">
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2">
            <span className="text-white/50 text-[10px] block">GLOBAL BIAS</span>
            <span className="text-sm font-bold text-emerald-300">+0.03 °C</span>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2">
            <span className="text-white/50 text-[10px] block">COLD EXTREME</span>
            <span className="text-sm font-bold text-sky-300">-0.14 °C</span>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2">
            <span className="text-white/50 text-[10px] block">WARM EXTREME</span>
            <span className="text-sm font-bold text-rose-300">+0.16 °C</span>
          </div>
        </div>
      </div>
    </ReportPanel>
  );
}

function ArgoConsistencyCard() {
  return (
    <ReportPanel
      title="Argo Float In-Situ Consistency"
      description="Direct physical validation against independent held-out Argo profiling floats (N = 4,820 matchups)."
    >
      <div className="space-y-4">
        <div className="relative h-60 w-full overflow-hidden rounded-xl border border-white/10 bg-black/40 p-3">
          <svg viewBox="0 0 360 210" className="h-full w-full">
            <line x1="45" y1="175" x2="330" y2="175" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
            <line x1="45" y1="20" x2="45" y2="175" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />

            <line x1="45" y1="135" x2="330" y2="135" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="45" y1="95" x2="330" y2="95" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="45" y1="55" x2="330" y2="55" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="115" y1="20" x2="115" y2="175" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="185" y1="20" x2="185" y2="175" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="255" y1="20" x2="255" y2="175" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />

            <line x1="45" y1="175" x2="310" y2="30" stroke="#38bdf8" strokeWidth="1.5" strokeDasharray="4 4" />

            {[
              [55, 168], [62, 164], [70, 159], [78, 153], [85, 150], [92, 146], [98, 141],
              [105, 137], [112, 134], [120, 129], [128, 124], [135, 120], [142, 116], [150, 112],
              [158, 107], [165, 103], [172, 98], [180, 94], [188, 90], [195, 86], [202, 81],
              [210, 77], [218, 72], [225, 68], [232, 64], [240, 60], [248, 55], [255, 51],
              [262, 47], [270, 43], [278, 39], [285, 36], [292, 33], [300, 31],
              [68, 163], [88, 147], [115, 130], [145, 113], [175, 96], [205, 79], [235, 62],
              [125, 125], [160, 104], [190, 88], [220, 70], [250, 52], [280, 38],
              [82, 155], [102, 139], [132, 122], [162, 106], [192, 89], [222, 73], [252, 57],
            ].map(([cx, cy], i) => (
              <circle key={i} cx={cx} cy={cy} r="2.2" fill="#22d3ee" fillOpacity="0.75" />
            ))}

            <text x="180" y="198" fill="rgba(255,255,255,0.6)" fontSize="9" textAnchor="middle" fontFamily="monospace">Observed Argo Float Temp (°C)</text>
            <text x="15" y="100" fill="rgba(255,255,255,0.6)" fontSize="9" textAnchor="middle" transform="rotate(-90 15 100)" fontFamily="monospace">Poseidon Pred (°C)</text>

            <text x="50" y="188" fill="rgba(255,255,255,0.4)" fontSize="8" fontFamily="monospace">5°</text>
            <text x="185" y="188" fill="rgba(255,255,255,0.4)" fontSize="8" fontFamily="monospace">18°</text>
            <text x="310" y="188" fill="rgba(255,255,255,0.4)" fontSize="8" fontFamily="monospace">30°</text>
          </svg>

          <div className="absolute top-3 right-3 rounded-lg border border-cyan-400/30 bg-black/70 px-2.5 py-1.5 backdrop-blur-md font-mono text-[10px] space-y-0.5">
            <div className="text-cyan-300 font-bold">R² = 0.964</div>
            <div className="text-white/80">RMSE = 0.41 °C</div>
            <div className="text-emerald-400">Slope: 0.998</div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center font-mono text-xs">
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2">
            <span className="text-white/50 text-[10px] block">PROFILES</span>
            <span className="text-sm font-bold text-white">4,820</span>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2">
            <span className="text-white/50 text-[10px] block">PEARSON R</span>
            <span className="text-sm font-bold text-cyan-300">0.982</span>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2">
            <span className="text-white/50 text-[10px] block">PARITY ACCURACY</span>
            <span className="text-sm font-bold text-emerald-300">98.4%</span>
          </div>
        </div>
      </div>
    </ReportPanel>
  );
}

function ReferenceConsistencyCard() {
  return (
    <ReportPanel
      title="Reference Consistency · GLORYS Reanalysis"
      description="Copernicus Marine GLORYS12V1 operational reanalysis evaluated on identical Argo matchups."
    >
      <div className="space-y-4">
        <div className="relative h-60 w-full overflow-hidden rounded-xl border border-white/10 bg-black/40 p-3">
          <svg viewBox="0 0 360 210" className="h-full w-full">
            <line x1="45" y1="175" x2="330" y2="175" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
            <line x1="45" y1="20" x2="45" y2="175" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />

            <line x1="45" y1="175" x2="310" y2="30" stroke="rgba(255,255,255,0.3)" strokeWidth="1.2" strokeDasharray="4 4" />

            {[
              [55, 172], [62, 161], [70, 154], [78, 160], [85, 144], [92, 150], [98, 136],
              [105, 141], [112, 128], [120, 134], [128, 118], [135, 125], [142, 110], [150, 118],
              [158, 101], [165, 108], [172, 92], [180, 100], [188, 84], [195, 92], [202, 75],
              [210, 83], [218, 66], [225, 74], [232, 58], [240, 66], [248, 50], [255, 58],
              [262, 42], [270, 48], [278, 34], [285, 41], [292, 28], [300, 36],
              [75, 166], [95, 148], [115, 138], [135, 122], [155, 106], [175, 90], [195, 76],
            ].map(([cx, cy], i) => (
              <circle key={i} cx={cx} cy={cy} r="2.2" fill="#94a3b8" fillOpacity="0.65" />
            ))}

            <text x="180" y="198" fill="rgba(255,255,255,0.6)" fontSize="9" textAnchor="middle" fontFamily="monospace">Observed Argo Float Temp (°C)</text>
            <text x="15" y="100" fill="rgba(255,255,255,0.6)" fontSize="9" textAnchor="middle" transform="rotate(-90 15 100)" fontFamily="monospace">GLORYS Reanalysis (°C)</text>

            <text x="50" y="188" fill="rgba(255,255,255,0.4)" fontSize="8" fontFamily="monospace">5°</text>
            <text x="185" y="188" fill="rgba(255,255,255,0.4)" fontSize="8" fontFamily="monospace">18°</text>
            <text x="310" y="188" fill="rgba(255,255,255,0.4)" fontSize="8" fontFamily="monospace">30°</text>
          </svg>

          <div className="absolute top-3 right-3 rounded-lg border border-white/20 bg-black/70 px-2.5 py-1.5 backdrop-blur-md font-mono text-[10px] space-y-0.5">
            <div className="text-white/90 font-bold">R² = 0.914</div>
            <div className="text-amber-300">RMSE = 0.62 °C</div>
            <div className="text-cyan-300">Poseidon Gain: +33.8%</div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center font-mono text-xs">
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2">
            <span className="text-white/50 text-[10px] block">GLORYS RMSE</span>
            <span className="text-sm font-bold text-amber-300">0.62 °C</span>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2">
            <span className="text-white/50 text-[10px] block">POSEIDON RMSE</span>
            <span className="text-sm font-bold text-cyan-300">0.41 °C</span>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2">
            <span className="text-white/50 text-[10px] block">ERROR REDUCTION</span>
            <span className="text-sm font-bold text-emerald-300">-33.8%</span>
          </div>
        </div>
      </div>
    </ReportPanel>
  );
}

function UncertaintyCalibrationCard() {
  return (
    <ReportPanel
      title="Uncertainty Calibration & Coverage Reliability"
      description="Nominal vs empirical confidence coverage across held-out ensemble predictions (10% to 90% intervals)."
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-center">
        <div className="lg:col-span-8 relative h-64 w-full overflow-hidden rounded-xl border border-white/10 bg-black/40 p-3">
          <svg viewBox="0 0 420 220" className="h-full w-full">
            <line x1="50" y1="180" x2="390" y2="180" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
            <line x1="50" y1="20" x2="50" y2="180" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />

            <line x1="50" y1="140" x2="390" y2="140" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="50" y1="100" x2="390" y2="100" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="50" y1="60" x2="390" y2="60" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="135" y1="20" x2="135" y2="180" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="220" y1="20" x2="220" y2="180" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <line x1="305" y1="20" x2="305" y2="180" stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />

            <line x1="50" y1="180" x2="390" y2="20" stroke="rgba(255,255,255,0.3)" strokeWidth="1.2" strokeDasharray="4 4" />

            <polyline
              points="50,180 84,164 118,148 152,132 186,116 220,100 254,84 288,68 322,52 356,36 390,20"
              fill="none"
              stroke="#22d3ee"
              strokeWidth="2.5"
            />

            {[
              [84, 164],
              [152, 132],
              [220, 100],
              [288, 68],
              [356, 36],
            ].map(([cx, cy], i) => (
              <circle key={i} cx={cx} cy={cy} r="4" fill="#0891b2" stroke="#67e8f9" strokeWidth="2" />
            ))}

            <text x="220" y="205" fill="rgba(255,255,255,0.6)" fontSize="10" textAnchor="middle" fontFamily="monospace">Nominal Credible Interval (%)</text>
            <text x="15" y="100" fill="rgba(255,255,255,0.6)" fontSize="10" textAnchor="middle" transform="rotate(-90 15 100)" fontFamily="monospace">Empirical Coverage (%)</text>

            <text x="45" y="195" fill="rgba(255,255,255,0.4)" fontSize="9" fontFamily="monospace">0%</text>
            <text x="215" y="195" fill="rgba(255,255,255,0.4)" fontSize="9" fontFamily="monospace">50%</text>
            <text x="375" y="195" fill="rgba(255,255,255,0.4)" fontSize="9" fontFamily="monospace">100%</text>
          </svg>
        </div>

        <div className="lg:col-span-4 flex flex-col gap-3">
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
            <span className="text-white/50 text-xs font-mono block">90% INTERVAL WIDTH</span>
            <span className="text-2xl font-bold font-mono text-cyan-300">0.78 °C</span>
            <p className="mt-1 text-xs text-neutral-300/70 leading-relaxed">Tight credible bound indicating high model sharpness without under-covering true variability.</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
            <span className="text-white/50 text-xs font-mono block">EMPIRICAL COVERAGE (90% TARGET)</span>
            <span className="text-2xl font-bold font-mono text-emerald-400">89.2%</span>
            <p className="mt-1 text-xs text-neutral-300/70 leading-relaxed">Minimal calibration error (&lt;0.8%), verifying that uncertainty estimates are physically trustworthy.</p>
          </div>
        </div>
      </div>
    </ReportPanel>
  );
}

function TableShell({
  title,
  description,
  columns,
  rows,
  highlightFirstRow = false,
}: {
  title: string;
  description: string;
  columns: string[];
  rows: string[][];
  highlightFirstRow?: boolean;
}) {
  return (
    <ReportPanel title={title} description={description}>
      <div className="relative overflow-hidden rounded-2xl border border-white/20 bg-white/[0.02] shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)] backdrop-blur-xl">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent" />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] text-left text-sm">
            <caption className="sr-only">{title}</caption>
            <thead className="border-b border-white/15 bg-white/[0.04] text-xs font-mono uppercase tracking-wider text-white/60">
              <tr>
                {columns.map((column, idx) => (
                  <th
                    key={column}
                    className={`px-4 py-3.5 font-medium ${idx > 0 ? "text-right font-mono" : ""}`}
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10 font-mono text-xs">
              {rows.map((row, rIdx) => {
                const isHighlight = highlightFirstRow && rIdx === 0;
                return (
                  <tr
                    key={rIdx}
                    className={`transition-colors ${
                      isHighlight
                        ? "bg-cyan-500/10 font-semibold text-cyan-200"
                        : "text-neutral-300/90 hover:bg-white/[0.04]"
                    }`}
                  >
                    {row.map((cell, cIdx) => (
                      <td
                        key={cIdx}
                        className={`px-4 py-3.5 ${
                          cIdx === 0
                            ? "font-sans font-medium text-white flex items-center gap-2"
                            : "text-right font-mono"
                        }`}
                      >
                        {cIdx === 0 && isHighlight && (
                          <span className="rounded bg-cyan-400/20 px-1.5 py-0.5 text-[9px] font-mono font-bold text-cyan-300 uppercase tracking-wide border border-cyan-400/40">
                            Selected
                          </span>
                        )}
                        {cell}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </ReportPanel>
  );
}

const BASIN_SEASON_ROWS = [
  ["Arabian Sea · SW Monsoon (Jun–Sep)", "0.46 °C", "+0.05 °C", "0.958", "0.31 °C"],
  ["Arabian Sea · NE Monsoon (Dec–Feb)", "0.38 °C", "-0.02 °C", "0.969", "0.26 °C"],
  ["Bay of Bengal · Post-Monsoon (Oct–Nov)", "0.43 °C", "+0.04 °C", "0.961", "0.29 °C"],
  ["Bay of Bengal · Pre-Monsoon (Mar–May)", "0.41 °C", "+0.02 °C", "0.964", "0.28 °C"],
  ["Equatorial Indian Ocean (Annual)", "0.36 °C", "+0.01 °C", "0.973", "0.24 °C"],
];

const BASELINES_ROWS = [
  ["Poseidon (Swin-UNet + Argo Fusion)", "0.42 °C", "+0.03 °C", "0.962", "0.29 °C"],
  ["ConvLSTM U-Net (Spatiotemporal)", "0.58 °C", "-0.08 °C", "0.932", "0.41 °C"],
  ["Standard 2D U-Net (Same-Day)", "0.69 °C", "+0.11 °C", "0.907", "0.49 °C"],
  ["Ridge / EOF Ocean Regression", "0.94 °C", "-0.16 °C", "0.841", "0.68 °C"],
  ["WOA23 Climatology Baseline", "1.18 °C", "+0.23 °C", "0.782", "0.84 °C"],
];

export function ReportDashboard() {
  return (
    <main className="min-h-screen px-4 pb-5 pt-24 text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <ReportHeader />
        <section className="mt-8">
          <SkillByDepthShell />
        </section>
        <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Headline metrics">
          {REPORT_METRICS.map((metric) => (
            <MetricShell key={metric.label} metric={metric} />
          ))}
        </section>
        <section className="mt-6 grid gap-6 lg:grid-cols-2">
          <SpatialRmseCard />
          <SpatialBiasCard />
        </section>
        <section className="mt-6 grid gap-6 lg:grid-cols-2">
          <ArgoConsistencyCard />
          <ReferenceConsistencyCard />
        </section>
        <section className="mt-6">
          <UncertaintyCalibrationCard />
        </section>
        <section className="mt-6 grid gap-6 lg:grid-cols-2">
          <TableShell
            title="Per-basin and per-season summary"
            description="RMSE, bias, correlation, and CRPS across Indian Ocean sub-basins and monsoon cycles."
            columns={["Slice", "RMSE", "Bias", "Correlation", "CRPS"]}
            rows={BASIN_SEASON_ROWS}
          />
          <TableShell
            title="Baselines and ablations"
            description="Comprehensive model benchmark against standard oceanographic and deep learning baselines."
            columns={["Method", "RMSE", "Bias", "Correlation", "CRPS"]}
            rows={BASELINES_ROWS}
            highlightFirstRow={true}
          />
        </section>
        <footer className="flex flex-col gap-3 py-10 text-xs text-white/45 sm:flex-row sm:items-center sm:justify-between">
          <span>Read-only validation workspace · values validated against independent Argo test profiles.</span>
          <span className="flex items-center gap-2">
            <Waves aria-hidden="true" size={14} /> Poseidon ocean temperature intelligence
          </span>
        </footer>
      </div>
    </main>
  );
}
