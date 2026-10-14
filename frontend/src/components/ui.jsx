import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BatteryLow,
  BookOpen,
  Brain,
  CalendarCheck,
  Clock,
  CloudRain,
  Compass,
  Frown,
  HeartHandshake,
  Hourglass,
  Inbox,
  LifeBuoy,
  Library,
  Loader2,
  MessagesSquare,
  Users,
  Wallet,
} from "lucide-react";
import { score } from "../format";

const AVATAR_COLOURS = ["#5b3fd1", "#0f7b8a", "#c2410c", "#2563eb", "#9d174d", "#15803d", "#7c3aed", "#b45309"];

export function initials(name = "") {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

export function Avatar({ name, size = 44 }) {
  const hash = [...name].reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
  return (
    <div
      className="avatar"
      style={{ width: size, height: size, fontSize: size * 0.38, background: AVATAR_COLOURS[hash % AVATAR_COLOURS.length] }}
      aria-hidden="true"
    >
      {initials(name)}
    </div>
  );
}

export const RISK_COLOURS = { Low: "#15803d", Medium: "#b7791f", High: "#e8590c", Critical: "#d62839" };

export function RiskBadge({ tier, probability }) {
  if (!tier) return <span className="muted">Not assessed</span>;
  return (
    <span className="risk-badge" style={{ "--risk": RISK_COLOURS[tier] }}>
      {tier}
      {probability != null && <span className="risk-badge-score">{score(probability)}</span>}
    </span>
  );
}

const TRENDS = {
  Improving: { Icon: ArrowUpRight, colour: "#15803d", path: "M2 30 L14 26 L24 27 L36 18 L48 15 L60 8 L72 4" },
  Stable: { Icon: ArrowRight, colour: "#6b7086", path: "M2 17 L14 15 L24 18 L36 16 L48 17 L60 15 L72 16" },
  Declining: { Icon: ArrowDownRight, colour: "#d62839", path: "M2 4 L12 6 L22 14 L32 10 L42 20 L54 24 L64 22 L72 31" },
  Volatile: { Icon: Activity, colour: "#e8590c", path: "M2 20 L10 6 L18 26 L28 8 L38 28 L48 10 L58 24 L66 6 L72 18" },
};

export function TrendIcon({ trajectory, size = 22 }) {
  const trend = TRENDS[trajectory] || TRENDS.Stable;
  return <trend.Icon size={size} color={trend.colour} strokeWidth={2.4} aria-hidden="true" />;
}

export const trendColour = (trajectory) => (TRENDS[trajectory] || TRENDS.Stable).colour;

// A drawn shape for the C2 category, not real data points.
export function TrajectoryGlyph({ trajectory }) {
  const trend = TRENDS[trajectory] || TRENDS.Stable;
  return (
    <svg className="trajectory-glyph" viewBox="0 0 74 35" role="img" aria-label={`${trajectory} trajectory`}>
      <path d={trend.path} fill="none" stroke={trend.colour} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

const INTERVENTION_ICONS = {
  "Academic Support": BookOpen,
  "Additional Learning Resources": Library,
  "Attendance Support": CalendarCheck,
  "Career Guidance": Compass,
  Counselling: HeartHandshake,
  "Engagement Support": MessagesSquare,
  "Financial Support": Wallet,
  "Peer Mentoring": Users,
  "Referral to Relevant Services": LifeBuoy,
  "Time Management Support": Clock,
};

export function InterventionIcon({ name, size = 26 }) {
  const Icon = INTERVENTION_ICONS[name] || BookOpen;
  return (
    <div className="intervention-icon" style={{ width: size * 1.9, height: size * 1.9 }}>
      <Icon size={size} aria-hidden="true" />
    </div>
  );
}

const CONDITION_ICONS = {
  "Exam Anxiety": Frown,
  "Conceptual Confusion": Brain,
  "Academic Helplessness": CloudRain,
  "Course Pacing Frustration": Hourglass,
  "Motivation Erosion": BatteryLow,
};

export function ConditionIcon({ name, size = 30 }) {
  const Icon = CONDITION_ICONS[name] || Brain;
  return <Icon size={size} className="condition-icon" aria-hidden="true" />;
}

export function ScoreBar({ value, colour = "var(--primary)" }) {
  return (
    <div className="score-bar" role="presentation">
      <div className="score-bar-fill" style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, background: colour }} />
    </div>
  );
}

const C3_COLOURS = { Academic: "#d62839", Behavioural: "#e8590c", Affective: "#f0a020" };

export function C3Bars({ c3, dominant }) {
  const rows = ["Academic", "Behavioural", "Affective"];
  return (
    <div className="c3-bars">
      {rows.map((name) => {
        const value = c3[name.toLowerCase()];
        return (
          <div key={name} className={`c3-row ${name === dominant ? "is-dominant" : ""}`}>
            <span className="c3-label">{name}</span>
            <ScoreBar value={value} colour={C3_COLOURS[name]} />
            <span className="c3-value" style={{ color: C3_COLOURS[name] }}>
              {score(value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function Loading({ label = "Loading…", fullPage = false }) {
  return (
    <div className={fullPage ? "loading loading-full" : "loading"}>
      <Loader2 className="spin" size={22} aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div className="error-banner" role="alert">
      <AlertCircle size={18} aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

export function EmptyState({ title, children }) {
  return (
    <div className="empty-state">
      <Inbox size={32} aria-hidden="true" />
      <h3>{title}</h3>
      {children}
    </div>
  );
}
