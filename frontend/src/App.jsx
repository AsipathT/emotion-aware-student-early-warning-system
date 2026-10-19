import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import AssessmentFormPage from "./pages/AssessmentFormPage";
import { CurrentDashboard, CurrentRecommendation } from "./pages/CurrentStudent";
import HistoryPage from "./pages/HistoryPage";
import NotFoundPage from "./pages/NotFoundPage";
import RecommendationPage from "./pages/RecommendationPage";
import StudentDashboardPage from "./pages/StudentDashboardPage";
import StudentsPage from "./pages/StudentsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
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
