// The Dashboard and Recommendations menu items open the student who was viewed last.
import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { api, getLastStudentId, setLastStudentId } from "../api";
import { EmptyState, ErrorBanner, Loading } from "../components/ui";

function ChooseStudent({ title }) {
  return (
    <div className="page">
      <h1 className="page-title">{title}</h1>
      <EmptyState title="No student selected">
        <p className="muted">Choose a student from the list first.</p>
        <Link className="button primary" to="/students">
          Choose a student
        </Link>
      </EmptyState>
    </div>
  );
}

export function CurrentDashboard() {
  const studentId = getLastStudentId();
  if (!studentId) return <ChooseStudent title="Student Intervention Dashboard" />;
  return <Navigate to={`/students/${studentId}`} replace />;
}

export function CurrentRecommendation() {
  const studentId = getLastStudentId();
  const [target, setTarget] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!studentId) return;
    api(`/students/${studentId}`)
      .then((data) => setTarget(data.latest_assessment ? `/assessments/${data.latest_assessment.id}` : `/students/${studentId}`))
      .catch((err) => {
        if (err.status === 404) setLastStudentId(null);
        setError(err.message);
      });
  }, [studentId]);

  if (!studentId) return <ChooseStudent title="Intervention Recommendations" />;
  if (error) {
    return (
      <div className="page">
        <ErrorBanner message={error} />
      </div>
    );
  }
  if (!target) return <Loading />;
  return <Navigate to={target} replace />;
}
