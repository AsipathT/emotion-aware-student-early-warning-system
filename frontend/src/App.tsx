import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Navbar } from './components/Navbar';
import { ConsentGate } from './components/consent/ConsentGate';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { DashboardPage } from './pages/DashboardPage';
import { ProfilePage } from './pages/ProfilePage';
import { CourseCatalogPage } from './pages/CourseCatalogPage';
import { CourseDetailPage } from './pages/CourseDetailPage';
import { CourseAssignmentsPage } from './pages/CourseAssignmentsPage';
import { AssignmentDetailPage } from './pages/AssignmentDetailPage';
import { CourseGradebookPage } from './pages/CourseGradebookPage';
import { MyEnrollmentsPage } from './pages/MyEnrollmentsPage';
import { AdminLayout } from './components/admin/AdminLayout';
import { ForumPage } from './pages/ForumPage';

// Lazy-loaded admin pages to optimize bundle size
const AdminOverviewPage = React.lazy(() => import('./pages/admin/AdminOverviewPage').then(m => ({ default: m.AdminOverviewPage })));
const AdminUsersPage = React.lazy(() => import('./pages/admin/AdminUsersPage').then(m => ({ default: m.AdminUsersPage })));
const AdminCoursesPage = React.lazy(() => import('./pages/admin/AdminCoursesPage').then(m => ({ default: m.AdminCoursesPage })));
const AdminEnrolmentsPage = React.lazy(() => import('./pages/admin/AdminEnrolmentsPage').then(m => ({ default: m.AdminEnrolmentsPage })));
const AdminConsentPage = React.lazy(() => import('./pages/admin/AdminConsentPage').then(m => ({ default: m.AdminConsentPage })));
const AuditLogPage = React.lazy(() => import('./pages/admin/AuditLogPage').then(m => ({ default: m.AuditLogPage })));
const AdminPipelinePage = React.lazy(() => import('./pages/admin/AdminPipelinePage').then(m => ({ default: m.AdminPipelinePage })));
const AdminIngestionPage = React.lazy(() => import('./pages/admin/AdminIngestionPage').then(m => ({ default: m.AdminIngestionPage })));
const AdminPrivacyPage = React.lazy(() => import('./pages/admin/AdminPrivacyPage').then(m => ({ default: m.AdminPrivacyPage })));
const AdminExportsPage = React.lazy(() => import('./pages/admin/AdminExportsPage').then(m => ({ default: m.AdminExportsPage })));
const AdminSystemPage = React.lazy(() => import('./pages/admin/AdminSystemPage').then(m => ({ default: m.AdminSystemPage })));
import { ForumThreadPage } from './pages/ForumThreadPage';
import { ChatPage } from './pages/ChatPage';
import { JournalPage } from './pages/JournalPage';
import { CourseContentPage } from './pages/CourseContentPage';
import { CourseQuizzesPage } from './pages/CourseQuizzesPage';
import { VideoPlayerPage } from './pages/VideoPlayerPage';
import { AttendancePage } from './pages/AttendancePage';
import { GradebookPage } from './pages/GradebookPage';
import { StaffAffectivePage } from './pages/StaffAffectivePage';
import { StaffAffectiveDetailPage } from './pages/StaffAffectiveDetailPage';
import { StaffStudentsPage } from './pages/StaffStudentsPage';
import { StudentContextPage } from './pages/StudentContextPage';
import { StaffRecommendationsPage } from './pages/StaffRecommendationsPage';
import { StaffRecommendationDetailPage } from './pages/StaffRecommendationDetailPage';
import { StaffInterventionsPage } from './pages/StaffInterventionsPage';
import { StaffInterventionDetailPage } from './pages/StaffInterventionDetailPage';
import { NotificationsPage } from './pages/NotificationsPage';
import { SupportPage } from './pages/SupportPage';
import { StaffResourcesPage } from './pages/StaffResourcesPage';
import { StaffSlotsPage } from './pages/StaffSlotsPage';
import { StaffValidationPage } from './pages/StaffValidationPage';
import { ExportPipelinePage } from './pages/ExportPipelinePage';
import { CohortRiskPage } from './pages/CohortRiskPage';


import { ClickstreamTracker } from './components/telemetry/ClickstreamTracker';


const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 5, // 5 minutes
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ClickstreamTracker />
        <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
          <ConsentGate />
          <Navbar />
          <main className="flex-1">

            <Routes>
              {/* Public Authentication Routes */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />

              {/* Protected LMS Dashboard */}
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <DashboardPage />
                  </ProtectedRoute>
                }
              />

              {/* Protected Course & Curriculum Management */}
              <Route
                path="/courses"
                element={
                  <ProtectedRoute>
                    <CourseCatalogPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/courses/:courseId"
                element={
                  <ProtectedRoute>
                    <CourseDetailPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/courses/:courseId/assignments"
                element={
                  <ProtectedRoute>
                    <CourseAssignmentsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/courses/:courseId/assignments/:assignmentId"
                element={
                  <ProtectedRoute>
                    <AssignmentDetailPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/courses/:courseId/gradebook"
                element={
                  <ProtectedRoute>
                    <CourseGradebookPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/courses/:courseId/content"
                element={
                  <ProtectedRoute>
                    <CourseContentPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/courses/:courseId/quizzes"
                element={
                  <ProtectedRoute>
                    <CourseQuizzesPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/courses/:courseId/video"
                element={
                  <ProtectedRoute>
                    <VideoPlayerPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/courses/:courseId/attendance"
                element={
                  <ProtectedRoute>
                    <AttendancePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/gradebook"
                element={
                  <ProtectedRoute>
                    <GradebookPage />
                  </ProtectedRoute>
                }
              />

              {/* Protected Student Enrollments (Student Only) */}
              <Route
                path="/my-courses"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <MyEnrollmentsPage />
                  </ProtectedRoute>
                }
              />

              {/* Protected User Profile Dashboard */}
              <Route
                path="/profile"
                element={
                  <ProtectedRoute>
                    <ProfilePage />
                  </ProtectedRoute>
                }
              />

              {/* Feature 40: Protected Admin & Auditor Governance Console */}
              <Route
                path="/admin"
                element={
                  <ProtectedRoute allowedRoles={['admin', 'auditor']}>
                    <AdminLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<AdminOverviewPage />} />
                <Route
                  path="users"
                  element={
                    <ProtectedRoute allowedRoles={['admin']}>
                      <AdminUsersPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="courses"
                  element={
                    <ProtectedRoute allowedRoles={['admin', 'auditor']}>
                      <AdminCoursesPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="enrolments"
                  element={
                    <ProtectedRoute allowedRoles={['admin', 'auditor']}>
                      <AdminEnrolmentsPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="consent"
                  element={
                    <ProtectedRoute allowedRoles={['admin', 'auditor']}>
                      <AdminConsentPage />
                    </ProtectedRoute>
                  }
                />
                <Route path="audit" element={<AuditLogPage />} />
                <Route path="pipeline" element={<AdminPipelinePage />} />
                <Route path="ingestion" element={<AdminIngestionPage />} />
                <Route path="privacy" element={<AdminPrivacyPage />} />
                <Route path="exports" element={<AdminExportsPage />} />
                <Route path="system" element={<AdminSystemPage />} />
              </Route>

              {/* Feature 42 & 20: Research Data Export & Telemetry Pipeline (Admin & Lecturer) */}
              <Route
                path="/export"
                element={
                  <ProtectedRoute allowedRoles={['admin', 'lecturer']}>
                    <ExportPipelinePage />
                  </ProtectedRoute>
                }
              />

              {/* Feature 27: Cohort Risk Overview Dashboard (Admin & Lecturer) */}
              <Route
                path="/cohort-risk"
                element={
                  <ProtectedRoute allowedRoles={['admin', 'lecturer']}>
                    <CohortRiskPage />
                  </ProtectedRoute>
                }
              />

              {/* Dushan: forum */}
              <Route
                path="/courses/:courseId/forum"
                element={
                  <ProtectedRoute>
                    <ForumPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/courses/:courseId/forum/:threadId"
                element={
                  <ProtectedRoute>
                    <ForumThreadPage />
                  </ProtectedRoute>
                }
              />

              {/* Dushan: chat */}
              <Route
                path="/messages"
                element={
                  <ProtectedRoute allowedRoles={['student', 'lecturer', 'counsellor']}>
                    <ChatPage />
                  </ProtectedRoute>
                }
              />

              {/* Dushan: journal */}
              <Route
                path="/journal"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <JournalPage />
                  </ProtectedRoute>
                }
              />

              {/* Dushan: F30 */}
              <Route
                path="/staff"
                element={
                  <ProtectedRoute allowedRoles={['counsellor', 'admin']}>
                    <Navigate to="/staff/students" replace />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/staff/affective"
                element={
                  <ProtectedRoute allowedRoles={['counsellor', 'admin']}>
                    <StaffAffectivePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/staff/affective/:pid"
                element={
                  <ProtectedRoute allowedRoles={['counsellor', 'admin']}>
                    <StaffAffectiveDetailPage />
                  </ProtectedRoute>
                }
              />

              {/* Dushan: F31 */}
              <Route
                path="/staff/students"
                element={
                  <ProtectedRoute allowedRoles={['counsellor', 'admin']}>
                    <StaffStudentsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/staff/students/:pid"
                element={
                  <ProtectedRoute allowedRoles={['counsellor', 'admin']}>
                    <StudentContextPage />
                  </ProtectedRoute>
                }
              />

              {/* Dushan: F32 */}
              <Route
                path="/staff/recommendations"
                element={
                  <ProtectedRoute allowedRoles={['counsellor', 'admin']}>
                    <StaffRecommendationsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/staff/recommendations/:id"
                element={
                  <ProtectedRoute allowedRoles={['counsellor', 'admin']}>
                    <StaffRecommendationDetailPage />
                  </ProtectedRoute>
                }
              />

              {/* Dushan: F34 */}
              <Route
                path="/staff/interventions"
                element={
                  <ProtectedRoute allowedRoles={['counsellor', 'admin']}>
                    <StaffInterventionsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/staff/interventions/:id"
                element={
                  <ProtectedRoute allowedRoles={['counsellor', 'admin']}>
                    <StaffInterventionDetailPage />
                  </ProtectedRoute>
                }
              />

              {/* Dushan: F38-C */}
              <Route
                path="/staff/resources"
                element={
                  <ProtectedRoute allowedRoles={['counsellor', 'admin']}>
                    <StaffResourcesPage />
                  </ProtectedRoute>
                }
              />

              {/* Dushan: F38-B */}
              <Route
                path="/staff/slots"
                element={
                  <ProtectedRoute allowedRoles={['counsellor', 'admin']}>
                    <StaffSlotsPage />
                  </ProtectedRoute>
                }
              />

              {/* Dushan: F36 */}
              <Route
                path="/staff/validation"
                element={
                  <ProtectedRoute allowedRoles={['counsellor', 'admin']}>
                    <StaffValidationPage />
                  </ProtectedRoute>
                }
              />


              {/* Dushan: F37 */}
              <Route
                path="/notifications"
                element={
                  <ProtectedRoute>
                    <NotificationsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/support"
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <SupportPage />
                  </ProtectedRoute>
                }
              />

              {/* Fallback redirect */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
