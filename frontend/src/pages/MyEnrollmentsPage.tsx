import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { enrollmentsApi, EnrollmentResponse } from '../api/enrollments';
import {
  BookOpen,
  Calendar,
  CheckCircle2,
  Clock,
  ArrowRight,
  Search,
  Sparkles,
  AlertCircle,
  GraduationCap,
  Layers,
} from 'lucide-react';

export const MyEnrollmentsPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch student enrollments
  const {
    data: enrollments = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<EnrollmentResponse[]>({
    queryKey: ['myEnrollments'],
    queryFn: enrollmentsApi.getMyEnrollments,
  });

  const filteredEnrollments = enrollments.filter((enrollment) => {
    const courseTitle = enrollment.course?.title || '';
    const courseDesc = enrollment.course?.description || '';
    const q = searchQuery.toLowerCase();
    return courseTitle.toLowerCase().includes(q) || courseDesc.toLowerCase().includes(q);
  });

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        <p className="text-sm font-medium text-slate-500">Loading your enrolled courses...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16">
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl flex items-start space-x-3 text-rose-800">
          <AlertCircle className="w-6 h-6 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-bold text-base">Failed to Load Enrollments</h3>
            <p className="text-sm mt-1 text-rose-700">
              {(error as any)?.response?.data?.detail || 'Could not retrieve your enrolled courses.'}
            </p>
            <button
              onClick={() => refetch()}
              className="mt-4 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-semibold transition"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100/80 text-indigo-700 text-xs font-medium mb-3">
            <GraduationCap className="w-3.5 h-3.5" />
            <span>Student Learning Hub</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            My Enrolled Courses
          </h1>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
            Access learning modules, curriculum materials, and track your ongoing study progress across all enrolled classes.
          </p>
        </div>

        <div className="flex items-center space-x-3 flex-shrink-0">
          <div className="px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-center">
            <div className="text-xl font-bold text-slate-900">{enrollments.length}</div>
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Enrolled Courses
            </div>
          </div>
          <Link
            to="/courses"
            className="inline-flex items-center px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm rounded-xl shadow-sm transition"
          >
            <BookOpen className="w-4 h-4 mr-1.5" />
            Browse Catalog
          </Link>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      {enrollments.length > 0 && (
        <div className="bg-white rounded-2xl p-4 border border-slate-200/80 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="relative w-full sm:max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search your courses by title or topic..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-50/50 border border-slate-200 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
            />
          </div>
          <div className="text-xs text-slate-500 font-medium self-end sm:self-center">
            Showing {filteredEnrollments.length} of {enrollments.length} enrolled
          </div>
        </div>
      )}

      {/* Courses Grid or Empty State */}
      {enrollments.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200/80 p-12 text-center shadow-sm space-y-4">
          <div className="inline-flex p-4 bg-indigo-50 text-indigo-600 rounded-2xl shadow-inner">
            <BookOpen className="w-10 h-10" />
          </div>
          <div className="max-w-md mx-auto space-y-2">
            <h3 className="text-lg font-bold text-slate-900">
              You haven't enrolled in any courses yet
            </h3>
            <p className="text-sm text-slate-500 leading-relaxed">
              Explore available courses in the catalog and register to start learning with interactive modules and emotion-aware feedback.
            </p>
          </div>
          <div className="pt-2">
            <Link
              to="/courses"
              className="inline-flex items-center px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl shadow-sm transition"
            >
              Explore Course Catalog
              <ArrowRight className="w-4 h-4 ml-2" />
            </Link>
          </div>
        </div>
      ) : filteredEnrollments.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200/80 p-12 text-center shadow-sm">
          <div className="inline-flex p-3 bg-slate-100 text-slate-400 rounded-2xl mb-3">
            <Search className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-slate-800">No matching enrolled courses</h3>
          <p className="text-xs text-slate-500 mt-1">
            No courses match your search "{searchQuery}".
          </p>
          <button
            onClick={() => setSearchQuery('')}
            className="mt-4 px-3 py-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-800"
          >
            Clear Search
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredEnrollments.map((enrollment) => {
            const course = enrollment.course;
            return (
              <div
                key={enrollment.id}
                className="group bg-white rounded-2xl border border-slate-200/80 hover:border-indigo-300 hover:shadow-md transition duration-200 flex flex-col overflow-hidden"
              >
                {/* Card Top Banner / Badge */}
                <div className="p-6 flex-1 flex flex-col justify-between space-y-4">
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/80">
                        <CheckCircle2 className="w-3 h-3 mr-1" />
                        {enrollment.status.toUpperCase()}
                      </span>
                      <span className="inline-flex items-center text-xs text-slate-400 font-mono">
                        <Calendar className="w-3.5 h-3.5 mr-1" />
                        {new Date(enrollment.enrolled_at).toLocaleDateString()}
                      </span>
                    </div>

                    <h3 className="text-lg font-bold text-slate-900 group-hover:text-indigo-600 transition line-clamp-1">
                      {course?.title || 'Untitled Course'}
                    </h3>

                    <p className="text-sm text-slate-500 mt-2 line-clamp-3 leading-relaxed">
                      {course?.description ||
                        'No detailed course description provided. Open the curriculum to inspect the modules.'}
                    </p>
                  </div>

                  <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                    <span className="flex items-center text-slate-400">
                      <Clock className="w-3.5 h-3.5 mr-1" />
                      Active Student
                    </span>
                    <span className="flex items-center text-indigo-600 font-medium">
                      <Layers className="w-3.5 h-3.5 mr-1" />
                      Self-Paced
                    </span>
                  </div>
                </div>

                {/* Card Action Footer */}
                <div className="px-6 py-4 bg-slate-50/70 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-600 group-hover:text-indigo-600 flex items-center transition">
                    <Sparkles className="w-3.5 h-3.5 mr-1 text-indigo-500" />
                    Enrolled
                  </span>
                  <Link
                    to={`/courses/${enrollment.course_id}`}
                    className="inline-flex items-center px-3.5 py-1.5 bg-white group-hover:bg-indigo-600 group-hover:text-white text-slate-700 font-semibold text-xs rounded-xl border border-slate-200 group-hover:border-transparent shadow-sm transition"
                  >
                    View Curriculum
                    <ArrowRight className="w-3.5 h-3.5 ml-1.5 group-hover:translate-x-0.5 transition" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
