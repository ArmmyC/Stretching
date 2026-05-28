const DATA = {
  hamstring: {
    title: "Hamstring Stretch Progress Dashboard",
    label: "Hamstring Stretch",
    badge: "Hamstring Explorer",
    level: "L2",
    metricMode: "forward bend",
    angleTarget: 40,
    rules: [
      ["Start the stretch", "stretch angle reaches 20 deg", "ok"],
      ["Deep enough", "stretch angle reaches 30 deg", "ok"],
      ["Good hold", "hold deep stretch for 6-8s with slow movement", "ok"],
      ["Twist warning", "body tilts too far sideways", "warning"],
    ],
    recommendations: [
      "Use Day 5 as the target for holding the stretch.",
      "Stay still for the first second before starting.",
      "Add a before/after reach test to prove flexibility gains.",
    ],
    days: [
      { day: 1, date: "May 24", score: 83, stretchDepth: 42.1, deepHold: 7.0, stableHold: 6.6, stability: 94.3, peakGyro: 63.8, smoothness: 45.2 },
      { day: 2, date: "May 25", score: 83, stretchDepth: 44.4, deepHold: 6.9, stableHold: 6.7, stability: 97.1, peakGyro: 74.0, smoothness: 32.5 },
      { day: 3, date: "May 26", score: 87, stretchDepth: 40.1, deepHold: 6.6, stableHold: 6.5, stability: 98.5, peakGyro: 49.9, smoothness: 62.6 },
      { day: 4, date: "May 27", score: 82, stretchDepth: 36.7, deepHold: 6.1, stableHold: 5.9, stability: 96.7, peakGyro: 47.9, smoothness: 65.1 },
      { day: 5, date: "May 28", score: 94, stretchDepth: 39.0, deepHold: 8.8, stableHold: 8.7, stability: 98.9, peakGyro: 48.3, smoothness: 64.6 },
    ],
  },
  neck: {
    title: "Neck Stretch Progress Dashboard",
    label: "Neck Stretch",
    badge: "Neck Mobility Scout",
    level: "L2",
    metricMode: "multi-axis neck angle",
    angleTarget: 25,
    rules: [
      ["Start the stretch", "head angle changes by 12 deg", "ok"],
      ["Deep enough", "head angle changes by 18 deg", "ok"],
      ["Good hold", "hold the angle without shaking", "ok"],
      ["Speed warning", "head moves too fast", "warning"],
    ],
    recommendations: [
      "Day 5 reaches the largest angle, but the movement is too fast.",
      "Move more smoothly before trying to stretch farther.",
      "Use camera pose tracking to check head and shoulder alignment.",
    ],
    days: [
      { day: 1, date: "May 24", score: 54, stretchDepth: 18.2, deepHold: 0.1, stableHold: 0.1, stability: 100.0, peakGyro: 23.8, smoothness: 95.2 },
      { day: 2, date: "May 25", score: 62, stretchDepth: 27.5, deepHold: 3.3, stableHold: 2.8, stability: 84.8, peakGyro: 66.3, smoothness: 42.1 },
      { day: 3, date: "May 26", score: 75, stretchDepth: 26.9, deepHold: 4.5, stableHold: 4.3, stability: 95.6, peakGyro: 46.3, smoothness: 67.1 },
      { day: 4, date: "May 27", score: 65, stretchDepth: 35.5, deepHold: 3.9, stableHold: 3.3, stability: 84.6, peakGyro: 61.1, smoothness: 48.6 },
      { day: 5, date: "May 28", score: 63, stretchDepth: 59.2, deepHold: 6.5, stableHold: 4.6, stability: 70.8, peakGyro: 86.6, smoothness: 16.8 },
    ],
  },
  hipFlexor: {
    title: "Kneeling Hip Flexor Stretch Progress Dashboard",
    label: "Kneeling Hip Flexor Stretch",
    badge: "Hip Opener",
    level: "L2",
    metricMode: "sample IMU series",
    angleTarget: 32,
    rules: [
      ["Start the stretch", "hip angle changes by 14 deg", "ok"],
      ["Deep enough", "stretch angle reaches 24 deg", "ok"],
      ["Good hold", "hold for 8s with slow movement", "ok"],
      ["Posture warning", "body leans or arches too much", "warning"],
    ],
    recommendations: [
      "Keep the hips and upper body aligned.",
      "Day 5 shows the best balance of angle and hold time.",
      "Use camera tracking to check knee, hip, and shoulder position.",
    ],
    days: [
      { day: 1, date: "May 24", score: 66, stretchDepth: 25.2, deepHold: 4.9, stableHold: 4.1, stability: 84.5, peakGyro: 58.2, smoothness: 52.3 },
      { day: 2, date: "May 25", score: 72, stretchDepth: 27.8, deepHold: 5.6, stableHold: 5.0, stability: 88.1, peakGyro: 51.7, smoothness: 60.4 },
      { day: 3, date: "May 26", score: 78, stretchDepth: 29.0, deepHold: 6.9, stableHold: 6.2, stability: 91.8, peakGyro: 45.9, smoothness: 67.6 },
      { day: 4, date: "May 27", score: 81, stretchDepth: 30.4, deepHold: 7.4, stableHold: 6.9, stability: 93.0, peakGyro: 42.6, smoothness: 71.8 },
      { day: 5, date: "May 28", score: 86, stretchDepth: 32.1, deepHold: 8.5, stableHold: 7.8, stability: 94.4, peakGyro: 39.8, smoothness: 75.3 },
    ],
  },
  chest: {
    title: "Doorway Chest Stretch Progress Dashboard",
    label: "Doorway / Standing Chest Stretch",
    badge: "Posture Builder",
    level: "L2",
    metricMode: "sample IMU series",
    angleTarget: 28,
    rules: [
      ["Start the stretch", "chest opens by 12 deg", "ok"],
      ["Deep enough", "stretch angle reaches 22 deg", "ok"],
      ["Good hold", "hold for 8s with slow movement", "ok"],
      ["Posture warning", "shoulders lift or body leans too much", "warning"],
    ],
    recommendations: [
      "Hold time improves steadily across the week.",
      "Day 4 has the smoothest start; repeat that pace.",
      "Use camera tracking to compare left and right shoulders.",
    ],
    days: [
      { day: 1, date: "May 24", score: 61, stretchDepth: 21.3, deepHold: 4.2, stableHold: 3.7, stability: 82.6, peakGyro: 55.4, smoothness: 55.8 },
      { day: 2, date: "May 25", score: 68, stretchDepth: 23.6, deepHold: 5.1, stableHold: 4.8, stability: 88.0, peakGyro: 47.2, smoothness: 66.0 },
      { day: 3, date: "May 26", score: 74, stretchDepth: 25.4, deepHold: 6.3, stableHold: 5.9, stability: 90.5, peakGyro: 42.1, smoothness: 72.4 },
      { day: 4, date: "May 27", score: 82, stretchDepth: 27.1, deepHold: 7.8, stableHold: 7.3, stability: 94.2, peakGyro: 36.8, smoothness: 79.0 },
      { day: 5, date: "May 28", score: 85, stretchDepth: 27.9, deepHold: 8.4, stableHold: 7.9, stability: 95.0, peakGyro: 38.5, smoothness: 76.9 },
    ],
  },
  shoulder: {
    title: "Cross-Body Shoulder Stretch Progress Dashboard",
    label: "Cross-Body Shoulder Stretch",
    badge: "Shoulder Guardian",
    level: "L2",
    metricMode: "sample IMU series",
    angleTarget: 31,
    rules: [
      ["Start the stretch", "arm crosses body by 15 deg", "ok"],
      ["Deep enough", "stretch angle reaches 26 deg", "ok"],
      ["Good hold", "hold for 8s with slow movement", "ok"],
      ["Twist warning", "torso turns too much", "warning"],
    ],
    recommendations: [
      "Keep the torso still while pulling the arm across.",
      "Day 5 is the strongest overall session.",
      "Compare left and right shoulders in the next data capture.",
    ],
    days: [
      { day: 1, date: "May 24", score: 64, stretchDepth: 24.2, deepHold: 4.7, stableHold: 4.0, stability: 85.2, peakGyro: 57.5, smoothness: 53.1 },
      { day: 2, date: "May 25", score: 70, stretchDepth: 26.8, deepHold: 5.8, stableHold: 5.2, stability: 88.9, peakGyro: 49.6, smoothness: 63.0 },
      { day: 3, date: "May 26", score: 76, stretchDepth: 28.1, deepHold: 6.8, stableHold: 6.3, stability: 92.3, peakGyro: 44.5, smoothness: 69.4 },
      { day: 4, date: "May 27", score: 73, stretchDepth: 29.4, deepHold: 6.1, stableHold: 5.7, stability: 90.7, peakGyro: 52.0, smoothness: 60.0 },
      { day: 5, date: "May 28", score: 84, stretchDepth: 31.0, deepHold: 8.0, stableHold: 7.4, stability: 94.1, peakGyro: 40.6, smoothness: 74.3 },
    ],
  },
};

const liveHistory = DATA.shoulder.days.slice(0, 4).map((day) => ({ ...day }));

DATA.live = {
  title: "Live Stretch Progress Dashboard",
  label: "Live Session",
  badge: "Live Form Coach",
  level: "L1",
  metricMode: "Nano IMU + pose score",
  angleTarget: 90,
  rules: [
    ["User visible", "camera pose is detected", "ok"],
    ["Arm angle", "Nano roll or accel Z reaches target range", "ok"],
    ["Good hold", "hold with low gyro movement", "ok"],
    ["Form warning", "camera and IMU disagree or movement is unstable", "warning"],
  ],
  recommendations: [
    "Keep the Nano on the side of the upper arm during the whole session.",
    "Use roll for side raises and accel Z for overhead raises.",
    "Keep gyro movement low while holding to improve steadiness.",
  ],
  days: [
    ...liveHistory,
    { day: 5, date: "Live", score: 0, stretchDepth: 0, deepHold: 0, stableHold: 0, stability: 0, peakGyro: 0, smoothness: 0 },
  ],
};

const COLORS = {
  stretchDepth: "#b57a00",
  deepHold: "#0f8b8d",
  stableHold: "#41b883",
  stability: "#17252f",
  peakGyro: "#c96d4a",
  score: "#b57a00",
};

const SERIES = [
  ["stretchDepth", "Stretch Angle (deg)", COLORS.stretchDepth],
  ["deepHold", "Deep Hold Time (s)", COLORS.deepHold],
  ["stableHold", "Good Hold Time (s)", COLORS.stableHold],
  ["stability", "Steadiness While Holding (%)", COLORS.stability],
  ["peakGyro", "Fastest Movement", COLORS.peakGyro],
];

const SCORE_WEIGHTS = [
  ["Hold Time", "hold", 40, "#b57a00"],
  ["Steadiness", "steadiness", 25, "#0f8b8d"],
  ["Stretch Angle", "angle", 20, "#17252f"],
  ["Smoothness", "smoothness", 15, "#c96d4a"],
];

const ICONS = {
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 11l9-8 9 8"/><path d="M5 10v11h14V10"/><path d="M9 21v-7h6v7"/></svg>',
  stretch: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20h16"/><path d="M7 18l4-8 4 8"/><path d="M12 10l4-5"/><path d="M14 4a2 2 0 1 0-4 0 2 2 0 0 0 4 0z"/><path d="M16 5l3 2"/></svg>',
  bars: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 20V9"/><path d="M12 20V4"/><path d="M19 20v-7"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l2.7 5.5 6.1.9-4.4 4.3 1 6-5.4-2.8-5.4 2.8 1-6-4.4-4.3 6.1-.9L12 3z"/></svg>',
  device: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 2h6"/><path d="M10 6h4"/><rect x="7" y="6" width="10" height="13" rx="2"/><path d="M12 19v3"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"/><path d="M3 12h2m14 0h2M12 3v2m0 14v2m-6.4-2.4 1.4-1.4m10-10 1.4-1.4m0 12.8-1.4-1.4m-10-10L5.6 5.6"/></svg>',
  body: '<svg viewBox="0 0 72 72" fill="none" stroke="currentColor" stroke-width="2"><circle cx="45" cy="11" r="5"/><path d="M40 18c-7 7-9 15-7 25"/><path d="M38 25l-13 14"/><path d="M33 43L16 62h13l13-15 14 13"/><path d="M35 36l19-2"/></svg>',
  calendar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/></svg>',
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
  medal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="9" r="5"/><path d="M8 13l-2 8 6-3 6 3-2-8"/><path d="M12 6v6M9 9h6"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 6v6h5"/><path d="M4 12h2M18 12h2M12 4v2M12 18v2"/></svg>',
  angle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 20h16"/><path d="M4 20L17 5"/><path d="M9 20a7 7 0 0 1 4-6"/></svg>',
  shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3l8 3v6c0 5-3.3 8.3-8 10-4.7-1.7-8-5-8-10V6l8-3z"/><path d="M8 12l3 3 6-7"/></svg>',
  bulb: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18h6"/><path d="M10 22h4"/><path d="M8 14a6 6 0 1 1 8 0c-1 1-1 2-1 4H9c0-2 0-3-1-4z"/></svg>',
  pulse: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12h4l2-6 4 13 2-7h6"/></svg>',
  clipboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4a3 3 0 0 1 6 0"/><path d="M9 9h6M9 13h6M9 17h4"/></svg>',
  flame: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M13 2s1 4-2 7c-2 2-4 4-4 8a5 5 0 0 0 10 0c0-3-2-5-2-5s4 2 4 6a7 7 0 1 1-14 0c0-4 3-7 5-9 2-2 3-4 3-7z"/></svg>',
  hex: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l8 5v10l-8 5-8-5V7l8-5z"/></svg>',
  mountain: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 20h18"/><path d="M5 20l6-12 4 8 2-4 4 8"/><path d="M10 10l2 2 1-2"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/></svg>',
};

let currentKey = "live";

function setIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((node) => {
    node.innerHTML = ICONS[node.dataset.icon] || "";
  });
}

function bestBy(days, key, lowerIsBetter = false) {
  return days.reduce((best, day) => {
    if (!best) return day;
    return lowerIsBetter ? (day[key] < best[key] ? day : best) : day[key] > best[key] ? day : best;
  }, null);
}

function fmt(value, digits = 1) {
  return Number(value).toFixed(digits);
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

function getSourceLabel(key) {
  if (key === "live") return "Live app status + Nano IMU";
  return key === "hamstring" || key === "neck" ? "Real Arduino sensor data" : "Sample data for prototype";
}

function getWeekRange(days) {
  return `${days[0].date} - ${days[days.length - 1].date}, 2026`;
}

function getProgressStats(days) {
  const totalScore = days.reduce((sum, day) => sum + day.score, 0);
  const avgScore = totalScore / days.length;
  const level = Math.max(1, Math.min(5, Math.floor(avgScore / 20) + 1));
  const xpMax = 800;
  const xp = Math.min(xpMax, Math.round(totalScore));
  const improved = days[days.length - 1].score >= days[0].score;
  return {
    level: `L${level}`,
    xp,
    xpMax,
    xpPct: Math.round((xp / xpMax) * 100),
    streak: days.length,
    caption: improved ? "Improved this week" : "Keep practicing",
  };
}

function getScoreParts(stretch) {
  const latest = stretch.days[stretch.days.length - 1];
  const holdScore = Math.min(100, (latest.stableHold / 8) * 100);
  const steadinessScore = latest.stability;
  const angleScore = Math.min(100, (latest.stretchDepth / stretch.angleTarget) * 100);
  const smoothnessScore = latest.smoothness;
  const raw = {
    hold: holdScore * 0.4,
    steadiness: steadinessScore * 0.25,
    angle: angleScore * 0.2,
    smoothness: smoothnessScore * 0.15,
  };
  return SCORE_WEIGHTS.map(([label, key, maxPoints, color]) => ({
    label,
    color,
    maxPoints,
    points: raw[key],
    display: `${fmt(raw[key], 1)}/${maxPoints}`,
  }));
}

function buildInsights(stretch) {
  const days = stretch.days;
  const latest = days[days.length - 1];
  const first = days[0];
  const bestScore = bestBy(days, "score");
  const bestHold = bestBy(days, "stableHold");
  const bestDepth = bestBy(days, "stretchDepth");
  const bestStability = bestBy(days, "stability");
  const smootherAfterDay2 = days.slice(2).every((day) => day.peakGyro < days[1].peakGyro);
  const scoreChange = latest.score - first.score;

  const insights = [
    `Latest score is ${latest.score}/100, ${scoreChange >= 0 ? "up" : "down"} ${Math.abs(scoreChange)} points from Day ${first.day}.`,
    `Best overall score is Day ${bestScore.day} at ${bestScore.score}/100.`,
    `Best good hold is Day ${bestHold.day} at ${fmt(bestHold.stableHold)}s.`,
    `Best stretch angle is Day ${bestDepth.day} at ${fmt(bestDepth.stretchDepth)} deg.`,
  ];

  if (smootherAfterDay2) {
    insights.push("Movement became smoother after Day 2.");
  } else if (latest.peakGyro > 60) {
    insights.push(`Day ${latest.day} movement is fast, so slow down the start and finish.`);
  } else {
    insights.push(`Best steadiness is Day ${bestStability.day} at ${fmt(bestStability.stability)}%.`);
  }

  return insights;
}

function drawLineChart(stretch) {
  const svg = document.getElementById("progressChart");
  const width = 940;
  const rowHeight = 76;
  const height = 460;
  const pad = { left: 180, right: 34, top: 22, bottom: 44 };
  const chartWidth = width - pad.left - pad.right;
  const days = stretch.days;
  const x = (index) => pad.left + (chartWidth / (days.length - 1)) * index;
  const formatValue = (key, value) => (key === "score" ? fmt(value, 0) : fmt(value, 1));
  const paddedRange = (values) => {
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = Math.max(max - min, 1);
    return { min: min - span * 0.18, max: max + span * 0.18 };
  };

  let html = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">`;

  days.forEach((day, index) => {
    html += `<text class="axis-text" x="${x(index)}" y="${height - 28}" text-anchor="middle">Day ${day.day}</text>`;
    html += `<text class="axis-text" x="${x(index)}" y="${height - 12}" text-anchor="middle">${day.date}</text>`;
  });

  SERIES.forEach(([key, label, color], seriesIndex) => {
    const rowTop = pad.top + seriesIndex * rowHeight;
    const rowMid = rowTop + rowHeight / 2;
    const values = days.map((day) => day[key]);
    const range = paddedRange(values);
    const y = (value) => rowTop + rowHeight - 16 - ((value - range.min) / (range.max - range.min)) * (rowHeight - 30);
    const points = days.map((day, index) => `${x(index)},${y(day[key])}`).join(" ");

    html += `<rect x="${pad.left - 8}" y="${rowTop + 6}" width="${chartWidth + 16}" height="${rowHeight - 12}" rx="8" fill="${seriesIndex % 2 === 0 ? "rgba(24,33,42,.035)" : "rgba(255,255,255,.32)"}" />`;
    html += `<text class="chart-row-title" fill="${color}" x="${pad.left - 18}" y="${rowMid - 6}" text-anchor="end">${label}</text>`;
    html += `<text class="axis-text" x="${pad.left - 18}" y="${rowMid + 12}" text-anchor="end">${fmt(Math.min(...values), 1)} - ${fmt(Math.max(...values), 1)}</text>`;
    html += `<line x1="${pad.left}" y1="${rowMid}" x2="${width - pad.right}" y2="${rowMid}" stroke="rgba(24,33,42,.08)" stroke-dasharray="4 7" />`;
    html += `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="3" vector-effect="non-scaling-stroke" />`;
    days.forEach((day, index) => {
      const valueY = y(day[key]);
      const previous = index > 0 ? days[index - 1][key] : null;
      const delta = previous === null ? 0 : day[key] - previous;
      html += `<circle cx="${x(index)}" cy="${valueY}" r="5.5" fill="${color}" stroke="#fff" stroke-width="2" />`;
      html += `<text class="value-label" fill="${color}" x="${x(index)}" y="${valueY - 10}" text-anchor="middle">${formatValue(key, day[key])}</text>`;
      if (index > 0 && Math.abs(delta) >= 0.05) {
        html += `<text class="delta-label" fill="${delta >= 0 ? "#0f8b8d" : "#c96d4a"}" x="${x(index)}" y="${valueY + 19}" text-anchor="middle">${delta >= 0 ? "+" : ""}${fmt(delta, 1)}</text>`;
      }
    });
  });
  html += "</svg>";
  svg.outerHTML = html.replace("<svg ", '<svg id="progressChart" role="img" aria-label="5-day progress line chart" ');
}

function drawDonut(stretch) {
  const svg = document.getElementById("donutChart");
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  const parts = getScoreParts(stretch);
  const totalPoints = parts.reduce((sum, part) => sum + part.points, 0) || 1;
  let html = `<svg id="donutChart" viewBox="0 0 120 120" role="img" aria-label="Score breakdown donut chart">`;
  html += `<circle cx="60" cy="60" r="${radius}" fill="none" stroke="rgba(221,235,237,.14)" stroke-width="24"/>`;
  parts.forEach(({ points, color }) => {
    const dash = (points / totalPoints) * circumference;
    html += `<circle cx="60" cy="60" r="${radius}" fill="none" stroke="${color}" stroke-width="24" stroke-dasharray="${dash} ${circumference - dash}" stroke-dashoffset="${-offset}" transform="rotate(-90 60 60)"/>`;
    offset += dash;
  });
  html += `<circle cx="60" cy="60" r="24" fill="#faf9f6" stroke="rgba(24,33,42,.08)" stroke-width="1"/></svg>`;
  svg.outerHTML = html;

  document.getElementById("breakdownList").innerHTML = parts.map(
    ({ label, display, color }) => `
      <div class="breakdown-row">
        <span class="row-dot" style="background:${color}"></span>
        <span>${label}</span>
        <strong>${display}</strong>
      </div>
    `,
  ).join("");
}

function renderTable(stretch) {
  const head = document.getElementById("metricTableHead");
  const body = document.getElementById("metricTableBody");
  head.innerHTML = `
    <tr>
      <th>Metric</th>
      ${stretch.days.map((day) => `<th>Day ${day.day}</th>`).join("")}
    </tr>
  `;
  const rows = [
    ["stretchDepth", "Stretch Angle (deg)", COLORS.stretchDepth, 1],
    ["deepHold", "Deep Hold Time (s)", COLORS.deepHold, 1],
    ["stableHold", "Good Hold Time (s)", COLORS.stableHold, 1],
    ["stability", "Steadiness While Holding (%)", COLORS.stability, 1],
    ["peakGyro", "Fastest Movement", COLORS.peakGyro, 1],
    ["score", "Overall Score", COLORS.score, 0],
  ];
  body.innerHTML = rows.map(([key, label, color, digits]) => `
    <tr>
      <td><span class="row-label"><span class="row-dot" style="background:${color}"></span>${label}</span></td>
      ${stretch.days.map((day) => `<td>${fmt(day[key], digits)}</td>`).join("")}
    </tr>
  `).join("");
}

function renderLegend() {
  document.getElementById("legend").innerHTML = SERIES.map(
    ([, label, color]) => `<span class="legend-item"><span class="legend-dot" style="background:${color}"></span>${label}</span>`,
  ).join("");
}

function renderRules(stretch) {
  document.getElementById("rulesList").innerHTML = stretch.rules.map(([label, rule, status]) => `
    <div class="rule-row ${status === "warning" ? "warning" : ""}">
      <span data-icon="${status === "warning" ? "x" : "check"}"></span>
      <span>${label}</span>
      <code>${rule}</code>
    </div>
  `).join("");
  setIcons(document.getElementById("rulesList"));
}

function renderRecommendations(stretch) {
  document.getElementById("recommendations").innerHTML = stretch.recommendations.map(
    (item, index) => `<li><span>${index + 1}</span>${item}</li>`,
  ).join("");
}

function renderCalculation(stretch) {
  const latest = stretch.days[stretch.days.length - 1];
  const items = [
    `Hold time: ${fmt(latest.stableHold)}s of good hold, worth 40% of the score.`,
    `Steadiness: ${fmt(latest.stability)}% while holding, worth 25%.`,
    `Stretch angle: ${fmt(latest.stretchDepth)} deg, worth 20%.`,
    `Smoothness: ${fmt(latest.smoothness)}%, based on how slowly and smoothly the body moves, worth 15%.`,
  ];
  document.getElementById("calculationList").innerHTML = items.map((item) => `<li>${item}</li>`).join("");
}

function renderGamification(stretch) {
  const stats = getProgressStats(stretch.days);
  setText("streakDays", `${stats.streak} days`);
  setText("streakCaption", stats.caption);
  setText("levelMark", stats.level);
  setText("xpText", `${stats.xp} / ${stats.xpMax} XP`);
  setText("badgeName", stretch.badge);
  const fill = document.getElementById("xpBarFill");
  if (fill) fill.style.width = `${stats.xpPct}%`;
  const dots = document.getElementById("streakDots");
  if (dots) {
    dots.innerHTML = stretch.days.map((day) => `<span title="Day ${day.day}: ${day.score}/100"></span>`).join("");
  }
}

function renderDashboard(key) {
  currentKey = key;
  const stretch = DATA[key] || DATA.live;
  const days = stretch.days;
  const d5 = days[days.length - 1];
  const bestScore = bestBy(days, "score");
  const bestHold = bestBy(days, "stableHold");
  const bestDepth = bestBy(days, "stretchDepth");
  const bestStability = bestBy(days, "stability");

  setText("pageTitle", stretch.title);
  setText("heroStretchName", stretch.label);
  setText("weekRange", getWeekRange(days));
  setText("dataSourceLabel", getSourceLabel(key));

  setText("bestScore", bestScore.score);
  setText("bestScoreDay", `Day ${bestScore.day} Best`);
  setText("bestHold", fmt(bestHold.stableHold));
  setText("bestHoldDay", `Day ${bestHold.day} Best`);
  setText("bestDepth", fmt(bestDepth.stretchDepth));
  setText("bestDepthDay", `Day ${bestDepth.day} Best`);
  setText("bestStability", fmt(bestStability.stability));
  setText("bestStabilityDay", `Day ${bestStability.day} Best`);
  setText("dayFiveScore", d5.score);
  setText("latestScoreLabel", `Day ${d5.day} Score`);
  setText("heroScore", d5.score);
  setText("heroScoreLabel", `Day ${d5.day} Score`);
  setText("heroHold", `${fmt(d5.stableHold)}s`);
  setText("heroAngle", `${fmt(d5.stretchDepth)} deg`);
  setText("heroSteadiness", `${fmt(d5.stability)}%`);
  setText("heroSummary", `Latest session: ${d5.score}/100 overall score with ${fmt(d5.stableHold)}s good hold and ${fmt(d5.stretchDepth)} deg stretch angle.`);
  const ring = document.getElementById("heroScoreRing");
  if (ring) ring.style.setProperty("--score", d5.score);

  document.getElementById("insights").innerHTML = buildInsights(stretch).map((item) => `<li>${item}</li>`).join("");

  renderLegend();
  drawLineChart(stretch);
  drawDonut(stretch);
  renderTable(stretch);
  renderRules(stretch);
  renderRecommendations(stretch);
  renderCalculation(stretch);
  renderGamification(stretch);

  const select = document.getElementById("stretchSelect");
  if (select) select.value = key;
}

function finiteNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function liveAngleFromNano(nano) {
  const roll = finiteNumber(nano.roll, NaN);
  if (Number.isFinite(roll)) return Math.abs(roll);

  const pitch = finiteNumber(nano.relative_pitch, NaN);
  if (Number.isFinite(pitch)) return Math.abs(pitch);

  const az = finiteNumber(nano.az, NaN);
  if (Number.isFinite(az)) return clamp((1 - az) * 45, 0, 90);

  return 0;
}

function liveDayFromStatus(status) {
  const session = status.session || {};
  const nano = status.nano_imu || {};
  const model = session.stretch_model || {};
  const modelMetrics = model.metrics || {};
  const score = Math.round(clamp(finiteNumber(session.score), 0, 100));
  const elapsed = clamp(finiteNumber(session.elapsed_time), 0, 999);
  const gyro = Math.max(0, finiteNumber(nano.gyro_avg, finiteNumber(nano.gyro_mag)));
  const stability = clamp(
    finiteNumber(nano.stability_score, nano.stable ? 100 : score),
    0,
    100,
  );
  const isHolding = ["HOLDING", "HOLD_STEADY", "GOOD", "DONE", "COMPLETE"].includes(String(session.state || ""));
  const today = new Date().toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const modelAngle = finiteNumber(
    modelMetrics.lateral_tilt,
    finiteNumber(modelMetrics.hip_fold_angle, NaN),
  );

  return {
    day: 5,
    date: today,
    score,
    stretchDepth: Number.isFinite(modelAngle) ? modelAngle : liveAngleFromNano(nano),
    deepHold: elapsed,
    stableHold: isHolding || score >= 70 ? elapsed : 0,
    stability,
    peakGyro: gyro,
    smoothness: clamp(100 - gyro * 2.5, 0, 100),
  };
}

function updateLiveDashboard(status) {
  const session = status.session || {};
  const nano = status.nano_imu || {};
  const model = session.stretch_model || {};
  const label = String(session.current_stretch || "Live Session");
  const nanoFresh = nano.fresh === false ? "Nano signal waiting" : "Nano IMU connected";
  const modelReady = Boolean(model.available);
  const modelScore = finiteNumber(model.score, 0);

  DATA.live.label = label;
  DATA.live.title = `${label} Progress Dashboard`;
  DATA.live.days = [...liveHistory, liveDayFromStatus(status)];
  DATA.live.rules = [
    ["User visible", "camera pose is detected", status.pose && status.pose.user_visible ? "ok" : "warning"],
    ["Stretch model", modelReady ? `${model.label}: ${modelScore.toFixed(1)}/100` : "waiting for matching landmarks", modelReady && modelScore >= 55 ? "ok" : "warning"],
    ["Arm angle", "Nano roll / accel Z matches stretch range", liveAngleFromNano(nano) >= 35 || modelReady ? "ok" : "warning"],
    ["Good hold", "stable hold time contributes to score", finiteNumber(session.score) >= 70 ? "ok" : "warning"],
    ["Steadiness", "gyro movement remains low", finiteNumber(nano.gyro_mag) <= 20 ? "ok" : "warning"],
  ];
  DATA.live.recommendations = [
    String(model.feedback || session.instruction || "Start a stretch session to see live coaching."),
    nanoFresh,
    nano.ambient !== undefined ? `Brightness ${finiteNumber(nano.ambient).toFixed(0)}, proximity ${finiteNumber(nano.proximity).toFixed(0)}, mic ${finiteNumber(nano.mic_level).toFixed(1)}%.` : "Optional Nano sensors will appear here when forwarded.",
    "For upper-arm stretches, use roll near +/-90 for side raise and accel Z near -1 for overhead raise.",
  ];

  if (currentKey === "live") {
    renderDashboard("live");
  }
}

function normalizeDashboardAction(action) {
  const raw = String(action || "").toUpperCase();
  const aliases = {
    BUTTON_A: "CONFIRM",
    BUTTON_B: "BACK",
    BUTTON_C: "ALT",
    BUTTON_A_LONG: "CONFIRM_LONG",
    BUTTON_B_LONG: "BACK_LONG",
    BUTTON_C_LONG: "ALT_LONG",
    KNOB_PRESS: "CONFIRM",
    KNOB_PRESS_LONG: "CONFIRM_LONG",
    KNOB_RIGHT: "NEXT",
    KNOB_LEFT: "PREV",
  };
  return aliases[raw] || raw;
}

let lastDashboardHardwareAt = 0;

function dashboardHardwareReady() {
  const now = performance.now();
  if (now - lastDashboardHardwareAt < 150) return false;
  lastDashboardHardwareAt = now;
  return true;
}

function focusStretchPicker() {
  const select = document.getElementById("stretchSelect");
  if (!select) return;
  select.focus({ preventScroll: true });
  if (typeof select.showPicker === "function") {
    try {
      select.showPicker();
    } catch (error) {
      /* Some browsers only allow showPicker from direct user gestures. */
    }
  }
}

function moveStretchPicker(delta) {
  const select = document.getElementById("stretchSelect");
  if (!select) return;
  const optionCount = select.options.length;
  if (!optionCount) return;
  select.selectedIndex = (select.selectedIndex + delta + optionCount) % optionCount;
  renderDashboard(select.value);
}

function handleDashboardHardware(event) {
  if (!dashboardHardwareReady()) return;
  const action = normalizeDashboardAction(event.detail && event.detail.action);
  const select = document.getElementById("stretchSelect");
  const pickerFocused = select && document.activeElement === select;

  if (action === "BACK" || action === "BACK_LONG") {
    window.location.href = "/";
    return;
  }

  if (action === "CONFIRM" || action === "CONFIRM_LONG" || action === "ALT") {
    focusStretchPicker();
    return;
  }

  if (action === "NEXT" || action === "PREV") {
    const delta = action === "NEXT" ? 1 : -1;
    if (pickerFocused) {
      moveStretchPicker(delta);
    } else {
      window.scrollBy({ top: delta * 280, behavior: "smooth" });
    }
  }
}

async function refreshLiveStatus() {
  try {
    const response = await fetch("/api/status?debug=1", { cache: "no-store" });
    if (!response.ok) return;
    updateLiveDashboard(await response.json());
  } catch (error) {
    setText("dataSourceLabel", "Waiting for app status");
  }
}

document.getElementById("stretchSelect").addEventListener("change", (event) => {
  renderDashboard(event.target.value);
});

window.addEventListener("YUEDMAI:nano-imu", (event) => {
  refreshLiveStatus();
});
window.addEventListener("YUEDMAI:hardware", handleDashboardHardware);
window.addEventListener("yuedmai:hardware", handleDashboardHardware);
window.addEventListener("stretchsense:hardware", handleDashboardHardware);

setIcons();
renderDashboard(currentKey);
refreshLiveStatus();
setInterval(refreshLiveStatus, 1000);
