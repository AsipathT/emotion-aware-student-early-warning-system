import { AlertTriangle, ChevronRight, ClipboardCheck, LayoutDashboard, Search, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Avatar, EmptyState, ErrorBanner, Loading, RiskBadge } from "../components/ui";
import { formatDate, percent } from "../format";

export default function StudentsPage() {
  const navigate = useNavigate();
  const [students, setStudents] = useState(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [grade, setGrade] = useState("all");

  useEffect(() => {
    api("/students")
      .then(setStudents)
      .catch((err) => setError(err.message));
  }, []);

  const grades = useMemo(() => [...new Set((students || []).map((s) => s.grade))].sort(), [students]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (students || []).filter(
      (s) =>
        (grade === "all" || String(s.grade) === grade) &&
        (!q || s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q)),
    );
  }, [students, query, grade]);

  if (error) return <div className="page"><ErrorBanner message={error} /></div>;
  if (!students) return <Loading label="Loading students…" />;

  const assessed = students.filter((s) => s.latest_assessment).length;
  const highRisk = students.filter((s) => ["High", "Critical"].includes(s.latest_assessment?.risk_tier)).length;
  const openAssessment = (student) => navigate(`/students/${student.id}/assess`);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1 className="page-title">Students</h1>
          <p className="muted">Select a student to enter their C1, C2 and C3 inputs and get an intervention recommendation.</p>
        </div>
      </header>

      <section className="stat-row">
        <Stat Icon={Users} label="Students" value={students.length} />
        <Stat Icon={ClipboardCheck} label="Assessed" value={`${assessed} / ${students.length}`} />
        <Stat Icon={AlertTriangle} label="High or critical risk" value={highRisk} tone="danger" />
      </section>

      <section className="card">
        <div className="toolbar">
          <label className="search">
            <Search size={18} aria-hidden="true" />
            <input
              placeholder="Search by name or student ID"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search students"
            />
          </label>
          <select value={grade} onChange={(e) => setGrade(e.target.value)} aria-label="Filter by grade">
            <option value="all">All grades</option>
            {grades.map((g) => (
              <option key={g} value={String(g)}>
                Grade {g}
              </option>
            ))}
          </select>
        </div>

        {visible.length === 0 ? (
          <EmptyState title="No students match your search" />
        ) : (
          <div className="table-wrap">
            <table className="table table-clickable">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Grade</th>
                  <th>Latest risk</th>
                  <th>Latest recommendation</th>
                  <th>Last assessed</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {visible.map((student) => {
                  const latest = student.latest_assessment;
                  return (
                    <tr
                      key={student.id}
                      onClick={() => openAssessment(student)}
                      onKeyDown={(e) => e.key === "Enter" && openAssessment(student)}
                      tabIndex={0}
                      title="Enter inputs for this student"
                    >
                      <td data-label="Student">
                        <div className="person">
                          <Avatar name={student.name} size={38} />
                          <div>
                            <strong>{student.name}</strong>
                            <span className="muted small">{student.id}</span>
                          </div>
                        </div>
                      </td>
                      <td data-label="Grade" className="nowrap">
                        {student.grade} <span className="muted small">({student.class_name})</span>
                      </td>
                      <td data-label="Latest risk">
                        <RiskBadge tier={latest?.risk_tier} probability={latest?.risk_probability} />
                      </td>
                      <td data-label="Recommendation">
                        {latest ? (
                          <>
                            {latest.top_intervention} <span className="muted small">{percent(latest.suitability)}</span>
                          </>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td data-label="Last assessed" className="nowrap">
                        {latest ? formatDate(latest.created_at) : <span className="muted">—</span>}
                      </td>
                      <td>
                        <div className="row-actions">
                          {latest && (
                            <button
                              className="button small ghost"
                              title="Open this student's dashboard"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/students/${student.id}`);
                              }}
                            >
                              <LayoutDashboard size={16} /> Dashboard
                            </button>
                          )}
                          <ChevronRight size={18} className="muted" aria-hidden="true" />
                        </div>
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

function Stat({ Icon, label, value, tone }) {
  return (
    <div className={`stat ${tone ? `stat-${tone}` : ""}`}>
      <div className="stat-icon">
        <Icon size={20} aria-hidden="true" />
      </div>
      <div>
        <span className="muted small">{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}
