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
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { AuditLogPage } from './pages/admin/AuditLogPage';
import { ForumPage } from './pages/ForumPage';
import { ForumThreadPage } from './pages/ForumThreadPage';
import { ChatPage } from './pages/ChatPage';
import { JournalPage } from './pages/JournalPage';
import { CourseContentPage } from './pages/CourseContentPage';
import { VideoPlayerPage } from './pages/VideoPlayerPage';
import { AttendancePage } from './pages/AttendancePage';
import { GradebookPage } from './pages/GradebookPage';
import { StaffAffectivePage } from './pages/StaffAffectivePage';
import { StaffAffectiveDetailPage } from './pages/StaffAffectiveDetailPage';
import { StaffStudentsPage } from './pages/StaffStudentsPage';
import { StudentContextPage } from './pages/StudentContextPage';


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

              {/* Protected Admin Governance Panel (Admin Only) */}
              <Route
                path="/admin"
                element={
                  <ProtectedRoute allowedRoles={['admin']}>
                    <AdminDashboardPage />
                  </ProtectedRoute>
                }
              />

              {/* Feature 7: Protected Compliance Audit Log (Admin & Auditor Only) */}
              <Route
                path="/admin/audit"
                element={
                  <ProtectedRoute allowedRoles={['admin', 'auditor']}>
                    <AuditLogPage />
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
