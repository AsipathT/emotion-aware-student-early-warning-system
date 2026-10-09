import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../hooks/useAuth';
import { apiClient } from '../api/client';
import { RiskScoreCards } from '../components/dashboard/RiskScoreCards';
import { ActiveAlertsTable } from '../components/dashboard/ActiveAlertsTable';
import { analyticsApi, DashboardSummary } from '../api/analytics';
import { Brain } from 'lucide-react';

interface CourseItem {
  id: string;
  title: string;
  description: string | null;
  is_published: boolean;
  created_at: string;
  modules?: Array<{ id: string; title: string }>;
}



export const DashboardPage: React.FC = () => {
  const { user } = useAuth();

  const { data: courses = [], isLoading: isLoadingCourses } = useQuery<CourseItem[]>({
    queryKey: ['courses'],
    queryFn: async () => {
      const response = await apiClient.get<CourseItem[]>('/courses');
      return response.data;
    },
  });

  const { data: dashboardSummary = null } = useQuery<DashboardSummary>({
    queryKey: ['dashboard_summary'],
    queryFn: () => analyticsApi.getDashboardSummary(),
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-indigo-700 via-indigo-600 to-purple-600 rounded-2xl p-6 sm:p-8 text-white shadow-md">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <span className="inline-block px-3 py-1 bg-white/20 rounded-full text-xs font-semibold tracking-wide uppercase mb-2">
              Platform Overview
            </span>
            <h1 className="text-3xl font-extrabold tracking-tight">
              Welcome back, {user?.full_name || 'User'}!
            </h1>
            <p className="mt-1 text-indigo-100 text-sm max-w-2xl">
              Role: <span className="font-semibold capitalize text-white">{user?.role}</span> &bull; 
              Institutional ID: <span className="font-mono text-white">{user?.profile?.student_id || 'N/A'}</span>
            </p>
          </div>
          <div className="flex items-center space-x-2 bg-white/10 px-4 py-2.5 rounded-xl backdrop-blur-sm border border-white/10">
            <Brain className="w-5 h-5 text-indigo-200" />
            <span className="text-sm font-medium">Affective Tracking: Active</span>
          </div>
        </div>
      </div>

      {/* New KPI Cards from Member 2 */}
      <RiskScoreCards summary={dashboardSummary} />

      {/* Analytics Chart & Courses Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Active Alerts Table */}
        <div className="lg:col-span-2">
          <ActiveAlertsTable summary={dashboardSummary} />
        </div>

        {/* Courses List */}
        <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-gray-900">Courses Curriculum</h2>
            <span className="text-xs text-gray-500">{courses.length} enrolled</span>
          </div>

          {isLoadingCourses ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            </div>
          ) : courses.length === 0 ? (
            <div className="text-center py-12 text-gray-400 text-sm">
              No courses registered yet.
            </div>
          ) : (
            <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
              {courses.map((course) => (
                <div key={course.id} className="p-3.5 bg-gray-50 rounded-xl border border-gray-100 hover:border-indigo-200 transition">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-sm text-gray-900 truncate">{course.title}</h3>
                    <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${
                      course.is_published ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                    }`}>
                      {course.is_published ? 'Published' : 'Draft'}
                    </span>
                  </div>
                  {course.description && (
                    <p className="text-xs text-gray-500 mt-1 line-clamp-2">{course.description}</p>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Link to={`/courses/${course.id}/analytics`} className="text-xs text-indigo-600 hover:text-indigo-800 font-medium bg-indigo-50 px-2 py-1 rounded">Analytics</Link>
                    <Link to={`/courses/${course.id}/content`} className="text-xs text-gray-600 hover:text-gray-800 font-medium bg-gray-200 px-2 py-1 rounded">Content</Link>
                    <Link to={`/courses/${course.id}/video`} className="text-xs text-purple-600 hover:text-purple-800 font-medium bg-purple-50 px-2 py-1 rounded">Video Player</Link>
                    <Link to={`/courses/${course.id}/attendance`} className="text-xs text-blue-600 hover:text-blue-800 font-medium bg-blue-50 px-2 py-1 rounded">Attendance</Link>
                    <Link to={`/courses/${course.id}/gradebook`} className="text-xs text-green-600 hover:text-green-800 font-medium bg-green-50 px-2 py-1 rounded">Gradebook</Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
