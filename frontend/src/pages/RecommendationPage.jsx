import { ArrowLeft, Bot, RefreshCw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, setLastStudentId } from "../api";
import {
  Avatar,
  C3Bars,
  EmptyState,
  ErrorBanner,
  InterventionIcon,
  Loading,
  RiskBadge,
  ScoreBar,
  TrendIcon,
} from "../components/ui";
import { formatDate, formatDateTime, score } from "../format";
import { useReference } from "../reference";

export default function RecommendationPage() {
  const { assessmentId } = useParams();
  const { reference } = useReference();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");
    api(`/assessments/${assessmentId}`)
      .then((result) => {
        setData(result);
        setLastStudentId(result.student.id);
      })
      .catch((err) => setError(err.message));
  }, [assessmentId]);

  if (error) return <div className="page"><ErrorBanner message={error} /></div>;
  if (!data || !reference) return <Loading label="Loading recommendation…" />;

  const { assessment, student, past } = data;
  const { inputs } = assessment;
  const [top, ...others] = assessment.recommendations;

  return (
    <div className="page">
      <Link to={`/students/${student.id}`} className="back-link">
        <ArrowLeft size={16} /> {student.name}'s dashboard
      </Link>
      <header className="page-header">
        <div>
          <h1 className="page-title">Intervention Recommendation</h1>
          <p className="muted">
            Assessed {formatDateTime(assessment.created_at)} · {assessment.model} model
          </p>
        </div>
        <div className="person">
          <Avatar name={student.name} size={40} />
          <div>
            <strong>{student.name}</strong>
            <span className="muted small">
              {student.id}
            </span>
          </div>
        </div>
      </header>

      <div className="detail-grid">
        <div className="detail-main">
          {/* Top recommendation */}
          <section className="card top-recommendation">
            <span className="eyebrow">Top recommendation</span>
            <div className="recommendation-body">
              <InterventionIcon name={top.intervention} size={30} />
              <div className="recommendation-text">
                <strong className="recommendation-name">{top.intervention}</strong>
                <p className="muted">{reference.interventions[top.intervention]}</p>
              </div>
              <div className="suitability">
                <span className="metric-label">Suitability Score</span>
                <span className="suitability-value">{score(top.suitability)}</span>
              </div>
            </div>
            <ScoreBar value={top.suitability} colour="var(--success)" />
            <p className="rationale">
              <span className="label-strong">Rationale:</span> {assessment.rationale}
            </p>
          </section>

          {/* The other two options from the model */}
          <h2 className="section-title">Other Options</h2>
          <section className="options-grid">
            {others.map((option, index) => (
              <div key={option.intervention} className="card option-card">
                <span className="eyebrow muted">Option {index + 2}</span>
                <div className="option-head">
                  <InterventionIcon name={option.intervention} size={22} />
                  <strong>{option.intervention}</strong>
                </div>
                <p className="muted small">{reference.interventions[option.intervention]}</p>
                <div className="suitability option-suitability">
                  <span className="metric-label">Suitability Score</span>
                  <span className="suitability-value">{score(option.suitability)}</span>
                </div>
              </div>
            ))}
          </section>

          <AiExplanation assessment={assessment} pastCount={past.length} reference={reference} />
        </div>

        <aside className="detail-side">
          <section className="card">
            <h2 className="card-title">Inputs Used</h2>
            <dl className="input-list">
              <div><dt>Condition</dt><dd>{inputs.c1_condition}</dd></div>
              <div>
                <dt>Trajectory</dt>
                <dd className="inline-icon"><TrendIcon trajectory={inputs.c2_trajectory} size={16} /> {inputs.c2_trajectory}</dd>
              </div>
              <div>
                <dt>Dropout risk</dt>
                <dd><RiskBadge tier={inputs.risk_tier} probability={inputs.risk_probability} /></dd>
              </div>
            </dl>
            <h3 className="subheading">Causal Risk Strength</h3>
            <C3Bars c3={inputs.c3} dominant={inputs.c3_dominant} />
          </section>

          <section className="card">
            <div className="card-title-row">
              <h2 className="card-title">Past Recommendations</h2>
              <Link to={`/history?student=${student.id}`} className="text-link">
                Full history
              </Link>
            </div>
            {past.length === 0 ? (
              <p className="muted small">No earlier recommendations for {student.name}.</p>
            ) : (
              <ul className="timeline">
                {[...past].reverse().map((item) => (
                  <li key={item.id}>
                    <Link to={`/assessments/${item.id}`}>
                      <span className="timeline-date">{formatDate(item.created_at)}</span>
                      <strong>{item.recommendations[0].intervention}</strong>
                      <span className="muted small">
                        {item.inputs.c1_condition} · {item.inputs.risk_tier} risk
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}

function AiExplanation({ assessment, pastCount, reference }) {
  const [explanation, setExplanation] = useState(assessment.explanation);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const requested = useRef(null);

  const generate = useCallback(
    async (refresh) => {
      setLoading(true);
      setError("");
      try {
        setExplanation(await api(`/assessments/${assessment.id}/explanation`, { method: "POST", body: { refresh } }));
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [assessment.id],
  );

  // Ask for an explanation once per assessment if none is saved yet.
  useEffect(() => {
    setExplanation(assessment.explanation);
    setError("");
    if (!assessment.explanation && reference.openai_configured && requested.current !== assessment.id) {
      requested.current = assessment.id;
      generate(false);
    }
  }, [assessment, reference.openai_configured, generate]);

  return (
    <section className="card ai-card" aria-labelledby="ai-title">
      <div className="card-title-row">
        <h2 className="card-title" id="ai-title">
          <Sparkles size={18} aria-hidden="true" /> Why this recommendation?
        </h2>
        <span className="ai-badge">
          <Bot size={14} aria-hidden="true" /> AI-generated
        </span>
      </div>

      {!reference.openai_configured && !explanation ? (
        <EmptyState title="AI explanation is turned off">
          <p className="muted small">Add OPENAI_API_KEY to backend/.env and restart the backend to turn it on.</p>
        </EmptyState>
      ) : loading ? (
        <Loading label="Generating an AI explanation…" />
      ) : (
        <>
          <ErrorBanner message={error} />
          {explanation && (
            <>
              <p className="ai-notice">
                <strong>This explanation was written by AI</strong> (OpenAI {explanation.model}). It may contain mistakes —
                check it against the inputs before acting.
              </p>
              <p className="ai-text">{explanation.text}</p>
              <p className="muted small">
                Generated {formatDateTime(explanation.generated_at)} from this assessment
                {explanation.past_recommendations_used
                  ? ` and ${explanation.past_recommendations_used} past recommendation${explanation.past_recommendations_used > 1 ? "s" : ""}`
                  : ""}
                .
              </p>
            </>
          )}
          {reference.openai_configured && (
            <button className="button ghost small" onClick={() => generate(Boolean(explanation))} disabled={loading}>
              <RefreshCw size={15} /> {explanation ? "Regenerate" : "Generate explanation"}
            </button>
          )}
        </>
      )}
      {pastCount > 0 && !explanation && !loading && reference.openai_configured && (
        <p className="muted small">The explanation will also take {pastCount} past recommendation(s) into account.</p>
      )}
    </section>
  );
}
