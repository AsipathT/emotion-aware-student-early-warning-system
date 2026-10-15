import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../hooks/useAuth';
import { apiClient } from '../api/client';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { BookOpen, Users, Brain, ShieldAlert, Award } from 'lucide-react';
import IdentityRevealModal from '../components/privacy/IdentityRevealModal';

interface CourseItem {
  id: string;
  title: string;
  description: string | null;
  is_published: boolean;
  created_at: string;
  modules?: Array<{ id: string; title: string }>;
}

const affectiveTrendData = [
  { week: 'W1', stress: 20, engagement: 85, motivation: 90 },
  { week: 'W2', stress: 25, engagement: 80, motivation: 85 },
  { week: 'W3', stress: 45, engagement: 70, motivation: 65 },
  { week: 'W4', stress: 65, engagement: 55, motivation: 50 },
  { week: 'W5', stress: 80, engagement: 40, motivation: 35 },
  { week: 'W6', stress: 55, engagement: 65, motivation: 60 },
  { week: 'W7', stress: 35, engagement: 80, motivation: 75 },
];

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();

  const { data: courses = [], isLoading: isLoadingCourses } = useQuery<CourseItem[]>({
    queryKey: ['courses'],
    queryFn: async () => {
      const response = await apiClient.get<CourseItem[]>('/courses');
      return response.data;
    },
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

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Courses</p>
            <p className="text-2xl font-bold text-gray-900">{courses.length}</p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-rose-50 text-rose-600 rounded-xl">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Disengagement Risk</p>
            <p className="text-2xl font-bold text-gray-900">Low (12%)</p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-emerald-50 text-emerald-600 rounded-xl">
            <Award className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Average Retention</p>
            <p className="text-2xl font-bold text-gray-900">88.4%</p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-amber-50 text-amber-600 rounded-xl">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Interventions</p>
            <p className="text-2xl font-bold text-gray-900">3 Pending</p>
          </div>
        </div>
      </div>

      <div className="mt-8 p-6 bg-white rounded-lg shadow border border-gray-200">
        <h3 className="text-lg font-bold text-gray-800 mb-4">Test Feature 5: Privacy Reveal</h3>
        <p className="text-sm text-gray-600 mb-4">Testing reveal for pseudonym: STU_cdbe990a</p>
        <IdentityRevealModal pid="STU_fa91e2c6" />
      </div>

      {/* Analytics Chart & Courses Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Longitudinal Affective Trends Chart */}
        <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-gray-900">Affective & Engagement Longitudinal Trends</h2>
              <p className="text-xs text-gray-500">Multimodal stress vs engagement progression (Weeks 1 - 7)</p>
            </div>
            <span className="text-xs font-semibold px-2.5 py-1 bg-indigo-50 text-indigo-700 rounded-lg">
              Recharts Analytics
            </span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={affectiveTrendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="week" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="stress" stroke="#ef4444" strokeWidth={2.5} name="Stress Score" />
                <Line type="monotone" dataKey="engagement" stroke="#6366f1" strokeWidth={2.5} name="Engagement (%)" />
                <Line type="monotone" dataKey="motivation" stroke="#10b981" strokeWidth={2.5} name="Motivation Score" />
              </LineChart>
            </ResponsiveContainer>
          </div>
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
                  <div className="mt-2 text-[11px] text-gray-400 flex items-center justify-between">
                    <span>{course.modules?.length || 0} Modules</span>
                    <span>Created: {new Date(course.created_at).toLocaleDateString()}</span>
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
