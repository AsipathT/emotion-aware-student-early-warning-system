import { ChevronRight, PlusCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Avatar, EmptyState, ErrorBanner, Loading, RiskBadge, TrendIcon } from "../components/ui";
import { formatDateTime, percent } from "../format";

export default function HistoryPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const studentId = params.get("student") || "";
  const [students, setStudents] = useState([]);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/students")
      .then(setStudents)
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setRows(null);
    const query = studentId ? `?student_id=${encodeURIComponent(studentId)}` : "";
    api(`/assessments${query}`)
      .then(setRows)
      .catch((err) => setError(err.message));
  }, [studentId]);

  const selected = students.find((s) => s.id === studentId);
  const chooseStudent = (id) => setParams(id ? { student: id } : {});

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1 className="page-title">Intervention History</h1>
          <p className="muted">Every recommendation made by the model, newest first. Select a row to see its details.</p>
        </div>
        {selected && (
          <Link className="button primary" to={`/students/${selected.id}/assess`}>
            <PlusCircle size={17} /> New assessment for {selected.name.split(" ")[0]}
          </Link>
        )}
      </header>

      <ErrorBanner message={error} />

      <section className="card">
        <div className="toolbar">
          <select value={studentId} onChange={(e) => chooseStudent(e.target.value)} aria-label="Filter by student">
            <option value="">All students</option>
            {students.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.id})
              </option>
            ))}
          </select>
          {rows && <span className="muted small">{rows.length} recommendation{rows.length === 1 ? "" : "s"}</span>}
        </div>

        {!rows ? (
          <Loading label="Loading history…" />
        ) : rows.length === 0 ? (
          <EmptyState title="No recommendations yet">
            <p className="muted small">Recommendations appear here after an assessment is submitted.</p>
          </EmptyState>
        ) : (
          <div className="table-wrap">
            <table className="table table-clickable">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Student</th>
                  <th>Condition</th>
                  <th>Trajectory</th>
                  <th>Risk</th>
                  <th>Top recommendation</th>
                  <th aria-label="Open" />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const open = () => navigate(`/assessments/${row.id}`);
                  return (
                    <tr key={row.id} onClick={open} onKeyDown={(e) => e.key === "Enter" && open()} tabIndex={0}>
                      <td data-label="Date" className="nowrap">{formatDateTime(row.created_at)}</td>
                      <td data-label="Student">
                        <div className="person">
                          <Avatar name={row.student_name} size={32} />
                          <div>
                            <strong>{row.student_name}</strong>
                            <span className="muted small">{row.student_id}</span>
                          </div>
                        </div>
                      </td>
                      <td data-label="Condition">{row.c1_condition}</td>
                      <td data-label="Trajectory">
                        <span className="inline-icon">
                          <TrendIcon trajectory={row.c2_trajectory} size={16} /> {row.c2_trajectory}
                        </span>
                      </td>
                      <td data-label="Risk">
                        <RiskBadge tier={row.risk_tier} probability={row.risk_probability} />
                      </td>
                      <td data-label="Recommendation">
                        <strong>{row.top_intervention}</strong> <span className="muted small">{percent(row.suitability)}</span>
                      </td>
                      <td className="row-chevron">
                        <ChevronRight size={18} aria-hidden="true" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
