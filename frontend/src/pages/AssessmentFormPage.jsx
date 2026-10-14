import { ArrowLeft, Info, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, setLastStudentId } from "../api";
import { Avatar, ConditionIcon, ErrorBanner, Loading, RiskBadge, TrendIcon } from "../components/ui";
import { formatDate } from "../format";
import { riskTierFor, useReference } from "../reference";

const C3_FIELDS = [
  { key: "affective", label: "Affective", hint: "Emotional factors such as stress or low mood" },
  { key: "behavioural", label: "Behavioural", hint: "Attendance, participation and study habits" },
  { key: "academic", label: "Academic", hint: "Understanding of content and grades" },
];

const DEFAULTS = {
  c1_condition: "Exam Anxiety",
  c2_trajectory: "Stable",
  risk_probability: "0.50",
  c3: { affective: "0.34", behavioural: "0.33", academic: "0.33" },
};

function fromAssessment(inputs) {
  return {
    c1_condition: inputs.c1_condition,
    c2_trajectory: inputs.c2_trajectory,
    risk_probability: inputs.risk_probability.toFixed(2),
    c3: Object.fromEntries(C3_FIELDS.map(({ key }) => [key, inputs.c3[key].toFixed(2)])),
  };
}

// Numbers are kept as text while typing and checked before sending.
function toNumber(text) {
  const value = Number(text);
  return text !== "" && Number.isFinite(value) && value >= 0 && value <= 1 ? value : null;
}

export default function AssessmentFormPage() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const { reference, error: referenceError } = useReference();
  const [data, setData] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setLastStudentId(studentId);
    api(`/students/${studentId}`)
      .then((result) => {
        setData(result);
        setForm(result.latest_assessment ? fromAssessment(result.latest_assessment.inputs) : DEFAULTS);
      })
      .catch((err) => setError(err.message));
  }, [studentId]);

  const probability = form ? toNumber(form.risk_probability) : null;
  const c3Values = useMemo(
    () => (form ? Object.fromEntries(C3_FIELDS.map(({ key }) => [key, toNumber(form.c3[key])])) : {}),
    [form],
  );
  const c3Valid = C3_FIELDS.every(({ key }) => c3Values[key] !== null) && C3_FIELDS.some(({ key }) => c3Values[key] > 0);
  const dominant = c3Valid
    ? C3_FIELDS.reduce((best, field) => (c3Values[field.key] > c3Values[best.key] ? field : best)).label
    : null;
  const canSubmit = form && probability !== null && c3Valid && !submitting;

  if (error && !data) return <div className="page"><ErrorBanner message={error} /></div>;
  if (referenceError) return <div className="page"><ErrorBanner message={referenceError} /></div>;
  if (!data || !form || !reference) return <Loading label="Loading student…" />;

  const { student, latest_assessment: latest } = data;
  const update = (changes) => setForm((current) => ({ ...current, ...changes }));
  const updateC3 = (key, value) => setForm((current) => ({ ...current, c3: { ...current.c3, [key]: value } }));

  async function handleSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError("");
    try {
      await api(`/students/${studentId}/assessments`, {
        method: "POST",
        body: {
          c1_condition: form.c1_condition,
          c2_trajectory: form.c2_trajectory,
          risk_probability: probability,
          c3: c3Values,
        },
      });
      navigate(`/students/${studentId}`);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <div className="page">
      <Link to="/students" className="back-link">
        <ArrowLeft size={16} /> Students
      </Link>
      <header className="page-header">
        <div>
          <h1 className="page-title">New Assessment</h1>
          <p className="muted">Enter the inputs the model needs. The recommendation is made when you submit.</p>
        </div>
      </header>

      <section className="card student-strip">
        <Avatar name={student.name} size={48} />
        <div>
          <strong>{student.name}</strong>
          <span className="muted small">
            {student.id} · Grade {student.grade} ({student.class_name})
          </span>
        </div>
        <span className="muted small student-strip-note">
          {latest ? `Filled in from the last assessment on ${formatDate(latest.created_at)}` : "First assessment for this student"}
        </span>
      </section>

      <form onSubmit={handleSubmit} className="form-grid">
        <section className="card">
          <h2 className="card-title">C1 · Condition</h2>
          <div className="choice-grid">
            {Object.entries(reference.conditions).map(([name, description]) => (
              <label key={name} className={`choice ${form.c1_condition === name ? "selected" : ""}`}>
                <input
                  type="radio"
                  name="c1"
                  value={name}
                  checked={form.c1_condition === name}
                  onChange={() => update({ c1_condition: name })}
                />
                <ConditionIcon name={name} size={24} />
                <span>
                  <strong>{name}</strong>
                  <span className="muted small">{description}</span>
                </span>
              </label>
            ))}
          </div>
        </section>

        <section className="card">
          <h2 className="card-title">C2 · Engagement Trajectory</h2>
          <div className="segmented" role="radiogroup" aria-label="Engagement trajectory">
            {Object.keys(reference.trajectories).map((name) => (
              <label key={name} className={`segment ${form.c2_trajectory === name ? "selected" : ""}`}>
                <input
                  type="radio"
                  name="c2"
                  value={name}
                  checked={form.c2_trajectory === name}
                  onChange={() => update({ c2_trajectory: name })}
                />
                <TrendIcon trajectory={name} size={18} />
                {name}
              </label>
            ))}
          </div>
          <p className="muted small">{reference.trajectories[form.c2_trajectory]}</p>

          <h2 className="card-title spaced">Dropout Risk Score</h2>
          <div className="slider-row">
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={probability ?? 0}
              onChange={(e) => update({ risk_probability: Number(e.target.value).toFixed(2) })}
              aria-label="Dropout risk score slider"
            />
            <input
              type="number"
              className={`number-input ${probability === null ? "invalid" : ""}`}
              min="0"
              max="1"
              step="0.01"
              value={form.risk_probability}
              onChange={(e) => update({ risk_probability: e.target.value })}
              aria-label="Dropout risk score"
            />
          </div>
          <div className="derived">
            Risk tier (set from the score): <RiskBadge tier={probability === null ? null : riskTierFor(probability, reference)} />
          </div>
          {probability === null && <p className="field-error">Enter a number between 0 and 1.</p>}
        </section>

        <section className="card">
          <h2 className="card-title">C3 · Causal Risk Strength</h2>
          {C3_FIELDS.map(({ key, label, hint }) => (
            <div key={key} className="c3-input">
              <div className="c3-input-label">
                <strong>{label}</strong>
                <span className="muted small">{hint}</span>
              </div>
              <div className="slider-row">
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={c3Values[key] ?? 0}
                  onChange={(e) => updateC3(key, Number(e.target.value).toFixed(2))}
                  aria-label={`${label} slider`}
                />
                <input
                  type="number"
                  className={`number-input ${c3Values[key] === null ? "invalid" : ""}`}
                  min="0"
                  max="1"
                  step="0.01"
                  value={form.c3[key]}
                  onChange={(e) => updateC3(key, e.target.value)}
                  aria-label={label}
                />
              </div>
            </div>
          ))}
          {c3Valid ? (
            <div className="derived">
              Strongest factor: <span className="chip">{dominant}</span>
            </div>
          ) : (
            <p className="field-error">Each value must be between 0 and 1, and at least one must be above 0.</p>
          )}
          <p className="hint">
            <Info size={15} aria-hidden="true" />
            The model uses the strongest of the three factors.
          </p>
        </section>

        <div className="form-actions">
          <ErrorBanner message={error} />
          <Link to="/students" className="button ghost">
            Cancel
          </Link>
          <button className="button primary" disabled={!canSubmit}>
            <Sparkles size={18} />
            {submitting ? "Getting recommendation…" : "Get recommendation"}
          </button>
        </div>
      </form>
    </div>
  );
}
