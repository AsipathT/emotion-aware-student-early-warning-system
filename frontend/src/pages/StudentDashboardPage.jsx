import { ChevronRight, History, PlusCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, setLastStudentId } from "../api";
import {
  Avatar,
  C3Bars,
  ConditionIcon,
  EmptyState,
  ErrorBanner,
  InterventionIcon,
  Loading,
  RISK_COLOURS,
  RiskBadge,
  TrajectoryGlyph,
  TrendIcon,
  trendColour,
} from "../components/ui";
import { formatDate, formatDateTime, percent, score } from "../format";
import { useReference } from "../reference";

export default function StudentDashboardPage() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const { reference } = useReference();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");
    setLastStudentId(studentId);
    api(`/students/${studentId}`)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [studentId]);

  if (error) return <div className="page"><ErrorBanner message={error} /></div>;
  if (!data) return <Loading label="Loading dashboard…" />;

  const { student, latest_assessment: assessment, history } = data;
  const newAssessment = () => navigate(`/students/${studentId}/assess`);

  const header = (
    <header className="page-header">
      <h1 className="page-title">Student Intervention Dashboard</h1>
      <div className="header-actions">
        <Link className="button ghost" to={`/history?student=${studentId}`}>
          <History size={17} /> History
        </Link>
        <button className="button primary" onClick={newAssessment}>
          <PlusCircle size={17} /> New assessment
        </button>
      </div>
    </header>
  );

  if (!assessment) {
    return (
      <div className="page">
        {header}
        <section className="card student-strip">
          <Avatar name={student.name} size={48} />
          <div>
            <strong>{student.name}</strong>
            <span className="muted small">
              {student.id}
            </span>
          </div>
        </section>
        <EmptyState title="No assessment yet">
          <p className="muted">Enter this student's inputs to get their first recommendation.</p>
          <button className="button primary" onClick={newAssessment}>
            Start assessment
          </button>
        </EmptyState>
      </div>
    );
  }

  const { inputs } = assessment;
  const top = assessment.recommendations[0];
  const riskColour = RISK_COLOURS[inputs.risk_tier];
  const openDetails = () => navigate(`/assessments/${assessment.id}`);

  return (
    <div className="page">
      {header}

      {/* Student summary */}
      <section className="card summary-card">
        <div className="summary-person">
          <Avatar name={student.name} size={84} />
          <dl className="summary-facts">
            <div><dt>Student ID:</dt><dd>{student.id}</dd></div>
            <div><dt>Name:</dt><dd>{student.name}</dd></div>
            <div><dt>Risk Category:</dt><dd style={{ color: riskColour, fontWeight: 700 }}>{inputs.risk_tier}</dd></div>
          </dl>
        </div>
        <div className="summary-metric">
          <span className="metric-label">Dropout Risk Score</span>
          <span className="metric-value" style={{ color: riskColour }}>{score(inputs.risk_probability)}</span>
          <span className="metric-caption" style={{ color: riskColour }}>{inputs.risk_tier} Risk</span>
        </div>
        <div className="summary-metric">
          <span className="metric-label">Trend</span>
          <TrendIcon trajectory={inputs.c2_trajectory} size={34} />
          <span className="metric-caption" style={{ color: trendColour(inputs.c2_trajectory) }}>{inputs.c2_trajectory}</span>
        </div>
        <div className="summary-metric">
          <span className="metric-label">Last Updated</span>
          <span className="metric-text">{formatDateTime(assessment.created_at)}</span>
          <Link className="button primary small" to={`/history?student=${studentId}`}>
            View History
          </Link>
        </div>
      </section>

      {/* Inputs used by the model */}
      <h2 className="section-title">Key Student Context (From C1, C2, C3)</h2>
      <section className="context-grid">
        <div className="card context-card">
          <h3>Condition (C1)</h3>
          <div className="context-main">
            <ConditionIcon name={inputs.c1_condition} size={34} />
            <strong>{inputs.c1_condition}</strong>
          </div>
          <p className="muted small">{reference?.conditions[inputs.c1_condition]}</p>
        </div>

        <div className="card context-card">
          <h3>Engagement Trajectory (C2)</h3>
          <TrajectoryGlyph trajectory={inputs.c2_trajectory} />
          <strong style={{ color: trendColour(inputs.c2_trajectory) }}>{inputs.c2_trajectory}</strong>
          <p className="muted small">{reference?.trajectories[inputs.c2_trajectory]}</p>
        </div>

        <div className="card context-card">
          <h3>Risk Tier</h3>
          <div className="context-main">
            <RiskBadge tier={inputs.risk_tier} />
          </div>
          <RiskGauge probability={inputs.risk_probability} bounds={reference?.risk_tier_bounds} />
          <p className="muted small">Dropout risk score {score(inputs.risk_probability)} on a 0–1 scale.</p>
        </div>

        <div className="card context-card">
          <h3>Causal Risk Strength (C3)</h3>
          <C3Bars c3={inputs.c3} dominant={inputs.c3_dominant} />
          <p className="muted small">
            Strongest: <strong>{inputs.c3_dominant}</strong> (0 – 1 scale)
          </p>
        </div>
      </section>

      {/* Top recommendation */}
      <section
        className="card recommendation-card clickable"
        onClick={openDetails}
        onKeyDown={(e) => e.key === "Enter" && openDetails()}
        tabIndex={0}
        role="link"
        aria-label={`Open details for ${top.intervention}`}
      >
        <h2 className="card-title">Current Recommended Intervention (Top Recommendation)</h2>
        <div className="recommendation-body">
          <InterventionIcon name={top.intervention} />
          <div className="recommendation-text">
            <strong className="recommendation-name">{top.intervention}</strong>
            <p>
              <span className="label-strong">Rationale:</span> {assessment.rationale}
            </p>
          </div>
          <div className="suitability">
            <span className="metric-label">Suitability Score</span>
            <span className="suitability-value">{score(top.suitability)}</span>
            <span className="button primary small">
              View Details <ChevronRight size={16} />
            </span>
          </div>
        </div>
      </section>

      {/* Recent history */}
      {history.length > 1 && (
        <section className="card">
          <div className="card-title-row">
            <h2 className="card-title">Recommendation History</h2>
            <Link to={`/history?student=${studentId}`} className="text-link">
              View all
            </Link>
          </div>
          <ul className="timeline">
            {history.slice(0, 5).map((item) => (
              <li key={item.id}>
                <Link to={`/assessments/${item.id}`} className={item.id === assessment.id ? "current" : ""}>
                  <span className="timeline-date">{formatDate(item.created_at)}</span>
                  <strong>{item.top_intervention}</strong>
                  <span className="muted small">{percent(item.suitability)}</span>
                  <RiskBadge tier={item.risk_tier} probability={item.risk_probability} />
                  {item.id === assessment.id && <span className="chip">Current</span>}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function RiskGauge({ probability, bounds }) {
  if (!bounds) return null;
  let lower = 0;
  return (
    <div className="risk-gauge" aria-hidden="true">
      <div className="risk-gauge-track">
        {bounds.map(({ upper, tier }) => {
          const width = (upper - lower) * 100;
          lower = upper;
          return <span key={tier} style={{ width: `${width}%`, background: RISK_COLOURS[tier] }} />;
        })}
      </div>
      <div className="risk-gauge-marker" style={{ left: `${probability * 100}%` }} />
    </div>
  );
}
