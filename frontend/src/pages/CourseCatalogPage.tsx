import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coursesApi, CourseResponse, CourseCreatePayload } from '../api/courses';
import { useAuth } from '../hooks/useAuth';
import {
  BookOpen,
  Plus,
  Search,
  Layers,
  Calendar,
  AlertCircle,
  X,
  Lock,
  Globe,
  ArrowRight,
  GraduationCap,
} from 'lucide-react';

export const CourseCatalogPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const isInstructor = user?.role === 'lecturer' || user?.role === 'admin';

  // Search filter
  const [searchQuery, setSearchQuery] = useState('');
  const [filterPublished, setFilterPublished] = useState<'all' | 'published' | 'draft'>('all');

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newIsPublished, setNewIsPublished] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);

  // Fetch courses
  const {
    data: courses = [],
    isLoading,
    isError,
    error,
  } = useQuery<CourseResponse[]>({
    queryKey: ['courses'],
    queryFn: coursesApi.getCourses,
  });

  // Create course mutation
  const createMutation = useMutation({
    mutationFn: (payload: CourseCreatePayload) => coursesApi.createCourse(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courses'] });
      setIsModalOpen(false);
      setNewTitle('');
      setNewDescription('');
      setNewIsPublished(true);
      setFormError(null);
    },
    onError: (err: any) => {
      const detail =
        err.response?.data?.detail || 'Failed to create course. Please try again.';
      setFormError(detail);
    },
  });

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!newTitle.trim()) {
      setFormError('Course title cannot be empty.');
      return;
    }

    createMutation.mutate({
      title: newTitle.trim(),
      description: newDescription.trim() || null,
      is_published: newIsPublished,
    });
  };

  // Filtered courses
  const filteredCourses = courses.filter((course) => {
    const matchesSearch =
      course.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (course.description &&
        course.description.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!matchesSearch) return false;

    if (filterPublished === 'published') return course.is_published;
    if (filterPublished === 'draft') return !course.is_published;
    return true;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Banner & Action */}
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="inline-flex items-center space-x-2 px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full text-xs font-semibold uppercase tracking-wider mb-2">
            <GraduationCap className="w-4 h-4" />
            <span>Academic Curriculum</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Course & Curriculum Catalog
          </h1>
          <p className="mt-1 text-sm text-slate-500 max-w-xl">
            Explore academic courses, module syllabi, and structured learning pathways.
          </p>
        </div>

        {isInstructor && (
          <button
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center justify-center px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm rounded-xl shadow-sm hover:shadow transition"
          >
            <Plus className="w-5 h-5 mr-1.5" />
            Create Course
          </button>
        )}
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-96 shadow-sm">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
            <Search className="h-4 w-4" />
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search courses by title or topic..."
            className="block w-full pl-10 pr-4 py-2.5 bg-white border border-slate-300 rounded-xl text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
          />
        </div>

        {isInstructor && (
          <div className="flex items-center space-x-1.5 bg-slate-100 p-1 rounded-xl text-xs font-medium text-slate-600">
            <button
              onClick={() => setFilterPublished('all')}
              className={`px-3 py-1.5 rounded-lg transition ${
                filterPublished === 'all'
                  ? 'bg-white text-indigo-600 shadow-sm font-semibold'
                  : 'hover:text-slate-900'
              }`}
            >
              All ({courses.length})
            </button>
            <button
              onClick={() => setFilterPublished('published')}
              className={`px-3 py-1.5 rounded-lg transition ${
                filterPublished === 'published'
                  ? 'bg-white text-indigo-600 shadow-sm font-semibold'
                  : 'hover:text-slate-900'
              }`}
            >
              Published
            </button>
            <button
              onClick={() => setFilterPublished('draft')}
              className={`px-3 py-1.5 rounded-lg transition ${
                filterPublished === 'draft'
                  ? 'bg-white text-indigo-600 shadow-sm font-semibold'
                  : 'hover:text-slate-900'
              }`}
            >
              Drafts
            </button>
          </div>
        )}
      </div>

      {/* Loading & Error States */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-20 space-y-3">
          <div className="w-10 h-10 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
          <p className="text-sm text-slate-500 font-medium">Loading courses...</p>
        </div>
      )}

      {isError && (
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl flex items-start space-x-3 text-rose-800">
          <AlertCircle className="w-6 h-6 text-rose-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-bold text-base">Failed to load courses</h3>
            <p className="text-sm mt-1 text-rose-700">
              {(error as any)?.response?.data?.detail ||
                'Could not retrieve the course catalog. Please check server connectivity.'}
            </p>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !isError && filteredCourses.length === 0 && (
        <div className="text-center py-20 bg-white rounded-2xl border border-slate-200/80 shadow-sm p-8">
          <div className="inline-flex p-4 bg-indigo-50 text-indigo-600 rounded-2xl mb-3">
            <BookOpen className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-bold text-slate-900">No courses found</h3>
          <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">
            {searchQuery
              ? 'No courses matched your search query. Try searching for different keywords.'
              : isInstructor
              ? 'No courses have been added yet. Click "Create Course" to get started!'
              : 'There are currently no published courses available in the catalog.'}
          </p>
          {isInstructor && !searchQuery && (
            <button
              onClick={() => setIsModalOpen(true)}
              className="mt-5 inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700 transition"
            >
              <Plus className="w-4 h-4 mr-1.5" />
              Create First Course
            </button>
          )}
        </div>
      )}

      {/* Courses Cards Grid */}
      {!isLoading && !isError && filteredCourses.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredCourses.map((course) => {
            const moduleCount = course.modules?.length || 0;
            return (
              <div
                key={course.id}
                className="bg-white rounded-2xl border border-slate-200/80 shadow-sm hover:shadow-md hover:border-indigo-200 transition flex flex-col justify-between overflow-hidden group"
              >
                <div className="p-6 space-y-3.5">
                  <div className="flex items-start justify-between gap-3">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider ${
                        course.is_published
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      {course.is_published ? (
                        <>
                          <Globe className="w-3 h-3 mr-1" />
                          Published
                        </>
                      ) : (
                        <>
                          <Lock className="w-3 h-3 mr-1" />
                          Draft
                        </>
                      )}
                    </span>

                    <span className="text-[11px] text-slate-400 flex items-center font-mono">
                      <Calendar className="w-3 h-3 mr-1" />
                      {new Date(course.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                      })}
                    </span>
                  </div>

                  <div>
                    <h3 className="text-lg font-bold text-slate-900 group-hover:text-indigo-600 transition leading-snug line-clamp-2">
                      {course.title}
                    </h3>
                    <p className="text-xs text-slate-500 mt-2 line-clamp-3 leading-relaxed">
                      {course.description || 'No course syllabus description provided.'}
                    </p>
                  </div>
                </div>

                <div className="px-6 py-4 bg-slate-50/70 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
                  <div className="flex items-center space-x-1.5 font-medium">
                    <Layers className="w-4 h-4 text-indigo-500" />
                    <span>
                      {moduleCount} {moduleCount === 1 ? 'Module' : 'Modules'}
                    </span>
                  </div>

                  <Link
                    to={`/courses/${course.id}`}
                    className="inline-flex items-center text-xs font-semibold text-indigo-600 hover:text-indigo-700 group-hover:translate-x-0.5 transition"
                  >
                    <span>View Curriculum</span>
                    <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Course Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white w-full max-w-lg rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <BookOpen className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-base">Create New Academic Course</h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 rounded-lg p-1 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="p-6 space-y-4.5">
              {formError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start space-x-2 text-rose-800 text-xs">
                  <AlertCircle className="w-4 h-4 text-rose-600 mt-0.5 flex-shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Course Title *
                </label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. CS305: Advanced Distributed Systems"
                  className="block w-full px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                />
              </div>

              <div className="mt-4">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Syllabus & Overview Description
                </label>
                <textarea
                  rows={4}
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Summarize course learning objectives, weekly topics, and requirements..."
                  className="block w-full px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                />
              </div>

              <div className="mt-4 pt-1 flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200/60">
                <div>
                  <span className="text-xs font-semibold text-slate-800 block">
                    Publish to Student Catalog
                  </span>
                  <span className="text-[11px] text-slate-500">
                    If checked, course is immediately visible to enrolled students.
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={newIsPublished}
                  onChange={(e) => setNewIsPublished(e.target.checked)}
                  className="w-4 h-4 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500"
                />
              </div>

              <div className="pt-4 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 rounded-xl hover:bg-slate-100 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="inline-flex items-center px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60 transition"
                >
                  {createMutation.isPending ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <span>Create Course</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
