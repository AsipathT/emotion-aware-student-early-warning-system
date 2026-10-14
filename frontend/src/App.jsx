import { Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./auth";
import Layout from "./components/Layout";
import AssessmentFormPage from "./pages/AssessmentFormPage";
import { CurrentDashboard, CurrentRecommendation } from "./pages/CurrentStudent";
import HistoryPage from "./pages/HistoryPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import RecommendationPage from "./pages/RecommendationPage";
import StudentDashboardPage from "./pages/StudentDashboardPage";
import StudentsPage from "./pages/StudentsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/students" replace />} />
        <Route path="students" element={<StudentsPage />} />
        <Route path="students/:studentId" element={<StudentDashboardPage />} />
        <Route path="students/:studentId/assess" element={<AssessmentFormPage />} />
        <Route path="assessments/:assessmentId" element={<RecommendationPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="dashboard" element={<CurrentDashboard />} />
        <Route path="recommendations" element={<CurrentRecommendation />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
