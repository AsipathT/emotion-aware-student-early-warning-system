import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coursesApi, CourseResponse, ModuleCreatePayload } from '../api/courses';
import { enrollmentsApi, EnrollmentResponse } from '../api/enrollments';
import { useAuth } from '../hooks/useAuth';
import {
  ArrowLeft,
  Plus,
  BookOpen,
  Calendar,
  Layers,
  Globe,
  Lock,
  X,
  AlertCircle,
  Clock,
  Sparkles,
  FileCode,
  GraduationCap,
  Users,
  CheckCircle2,
  Mail,
  UserCheck,
} from 'lucide-react';

export const CourseDetailPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const isInstructor = user?.role === 'lecturer' || user?.role === 'admin';
  const isStudent = user?.role === 'student';

  // Active view tab for instructors: 'curriculum' or 'roster'
  const [activeTab, setActiveTab] = useState<'curriculum' | 'roster'>('curriculum');

  // Success / error toast banners
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Auto-dismiss toast after 5 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Add Module Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [moduleTitle, setModuleTitle] = useState('');
  const [sequenceOrder, setSequenceOrder] = useState<number>(1);
  const [topicsInput, setTopicsInput] = useState('');
  const [readingTime, setReadingTime] = useState<number>(30);
  const [notesInput, setNotesInput] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  // 1. Fetch course details
  const {
    data: course,
    isLoading: isCourseLoading,
    isError: isCourseError,
    error: courseError,
  } = useQuery<CourseResponse>({
    queryKey: ['course', courseId],
    queryFn: () => coursesApi.getCourseById(courseId!),
    enabled: !!courseId,
  });

  // 2. Fetch student's own enrollments (to check if current student is enrolled)
  const { data: myEnrollments = [] } = useQuery<EnrollmentResponse[]>({
    queryKey: ['myEnrollments'],
    queryFn: enrollmentsApi.getMyEnrollments,
    enabled: isStudent,
  });

  const isEnrolled = isStudent && myEnrollments.some((e) => e.course_id === courseId);

  // 3. Fetch course roster (for instructors / admins)
  const {
    data: roster = [],
    isLoading: isRosterLoading,
    isError: isRosterError,
    error: rosterError,
  } = useQuery<EnrollmentResponse[]>({
    queryKey: ['courseRoster', courseId],
    queryFn: () => enrollmentsApi.getCourseRoster(courseId!),
    enabled: isInstructor && !!courseId,
  });

  // 4. Enroll in course mutation (students only)
  const enrollMutation = useMutation({
    mutationFn: () => enrollmentsApi.enrollInCourse(courseId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myEnrollments'] });
      queryClient.invalidateQueries({ queryKey: ['course', courseId] });
      queryClient.invalidateQueries({ queryKey: ['courseRoster', courseId] });
      setSuccessMessage('Successfully enrolled! You now have access to all course modules.');
      setActionError(null);
    },
    onError: (err: any) => {
      const detail =
        err.response?.data?.detail || 'Failed to enroll in course. Please try again.';
      setActionError(detail);
    },
  });

  // 5. Add module mutation (instructors only)
  const addModuleMutation = useMutation({
    mutationFn: (payload: ModuleCreatePayload) =>
      coursesApi.addModule(courseId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['course', courseId] });
      queryClient.invalidateQueries({ queryKey: ['courses'] });
      setIsModalOpen(false);
      setModuleTitle('');
      setTopicsInput('');
      setNotesInput('');
      setFormError(null);
      setSuccessMessage('Module successfully added to the curriculum.');
    },
    onError: (err: any) => {
      const detail =
        err.response?.data?.detail || 'Failed to add module. Please try again.';
      setFormError(detail);
    },
  });

  const handleOpenModal = () => {
    const nextOrder = (course?.modules?.length || 0) + 1;
    setSequenceOrder(nextOrder);
    setModuleTitle(`Module ${nextOrder}: `);
    setTopicsInput('');
    setReadingTime(30);
    setNotesInput('');
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleAddModuleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!moduleTitle.trim()) {
      setFormError('Module title is required.');
      return;
    }

    const topics = topicsInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

    const content_payload = {
      topics: topics.length > 0 ? topics : ['Core concepts'],
      estimated_reading_minutes: readingTime,
      instructor_notes: notesInput.trim() || undefined,
    };

    addModuleMutation.mutate({
      title: moduleTitle.trim(),
      sequence_order: Number(sequenceOrder) || 1,
      content_payload,
    });
  };

  if (isCourseLoading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-20 flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        <p className="text-sm font-medium text-slate-500">Loading course curriculum...</p>
      </div>
    );
  }

  if (isCourseError || !course) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16">
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl flex items-start space-x-3 text-rose-800">
          <AlertCircle className="w-6 h-6 text-rose-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-bold text-base">Course Not Found or Access Denied</h3>
            <p className="text-sm mt-1 text-rose-700">
              {(courseError as any)?.response?.data?.detail ||
                'This course might be unpublished or you do not have permission to view it.'}
            </p>
            <button
              onClick={() => navigate('/courses')}
              className="mt-4 inline-flex items-center text-xs font-semibold text-rose-800 hover:text-rose-950 underline"
            >
              <ArrowLeft className="w-3.5 h-3.5 mr-1" />
              Return to Course Catalog
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Sort modules chronologically by sequence_order
  const sortedModules = [...(course.modules || [])].sort(
    (a, b) => a.sequence_order - b.sequence_order
  );

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Toast Banners */}
      {successMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center justify-between text-emerald-800 text-sm animate-fade-in shadow-sm">
          <div className="flex items-center space-x-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <span className="font-medium">{successMessage}</span>
          </div>
          <button
            onClick={() => setSuccessMessage(null)}
            className="text-emerald-600 hover:text-emerald-800 p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {actionError && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl flex items-center justify-between text-rose-800 text-sm animate-fade-in shadow-sm">
          <div className="flex items-center space-x-2.5">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <span className="font-medium">{actionError}</span>
          </div>
          <button
            onClick={() => setActionError(null)}
            className="text-rose-600 hover:text-rose-800 p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Navigation Breadcrumb */}
      <div>
        <Link
          to={isStudent ? '/my-courses' : '/courses'}
          className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-indigo-600 transition group"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5 group-hover:-translate-x-1 transition" />
          {isStudent ? 'Back to My Enrolled Courses' : 'Back to Course Catalog'}
        </Link>
      </div>

      {/* Course Hero Header */}
      <div className="relative bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2.5 max-w-3xl">
            <div className="flex items-center space-x-3">
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${
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
                    Draft (Unpublished)
                  </>
                )}
              </span>

              <span className="text-xs text-slate-400 flex items-center font-mono">
                <Calendar className="w-3.5 h-3.5 mr-1" />
                Created {new Date(course.created_at).toLocaleDateString()}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              {course.title}
            </h1>

            <p className="text-sm text-slate-600 leading-relaxed">
              {course.description || 'No detailed syllabus description provided.'}
            </p>
          </div>

          {/* Action Area: Student Enroll button OR Instructor Add Module button */}
          <div className="flex md:flex-col items-end gap-3 flex-shrink-0">
            {/* Student Enrollment Control */}
            {isStudent && (
              <div>
                {isEnrolled ? (
                  <div className="inline-flex items-center px-4 py-2.5 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-700 font-semibold text-sm shadow-sm">
                    <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-600" />
                    Enrolled
                  </div>
                ) : (
                  <button
                    onClick={() => enrollMutation.mutate()}
                    disabled={enrollMutation.isPending || !course.is_published}
                    className="inline-flex items-center px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-60 text-white font-semibold text-sm rounded-xl shadow-sm hover:shadow transition"
                  >
                    {enrollMutation.isPending ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                        <span>Enrolling...</span>
                      </>
                    ) : (
                      <>
                        <UserCheck className="w-4 h-4 mr-1.5" />
                        Enroll in Course
                      </>
                    )}
                  </button>
                )}
              </div>
            )}

            {/* Instructor Actions */}
            {isInstructor && (
              <button
                onClick={handleOpenModal}
                className="inline-flex items-center px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm rounded-xl shadow-sm hover:shadow transition"
              >
                <Plus className="w-4 h-4 mr-1.5" />
                Add Module
              </button>
            )}

            <div className="inline-flex items-center px-3 py-1.5 bg-slate-50 border border-slate-200/80 rounded-xl text-xs text-slate-600 font-medium">
              <Layers className="w-3.5 h-3.5 mr-1.5 text-indigo-500" />
              <span>{sortedModules.length} Modules in Curriculum</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs navigation for Instructors / Admins */}
      {isInstructor && (
        <div className="flex border-b border-slate-200 space-x-8">
          <button
            onClick={() => setActiveTab('curriculum')}
            className={`pb-3 text-sm font-semibold flex items-center transition border-b-2 -mb-px ${
              activeTab === 'curriculum'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <GraduationCap className="w-4 h-4 mr-2" />
            Curriculum Modules ({sortedModules.length})
          </button>
          <button
            onClick={() => setActiveTab('roster')}
            className={`pb-3 text-sm font-semibold flex items-center transition border-b-2 -mb-px ${
              activeTab === 'roster'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Users className="w-4 h-4 mr-2" />
            Enrolled Students Roster ({roster.length})
          </button>
        </div>
      )}

      {/* Curriculum View (Default, and only view for students) */}
      {(activeTab === 'curriculum' || !isInstructor) && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center">
              <GraduationCap className="w-5 h-5 mr-2 text-indigo-600" />
              Curriculum Sequence
            </h2>
            <span className="text-xs text-slate-500">
              Ordered chronologically by sequence index
            </span>
          </div>

          {sortedModules.length === 0 ? (
            <div className="text-center py-16 bg-white rounded-2xl border border-slate-200/80 p-8 shadow-sm">
              <div className="inline-flex p-3 bg-indigo-50 text-indigo-600 rounded-2xl mb-3">
                <BookOpen className="w-7 h-7" />
              </div>
              <h3 className="font-bold text-slate-900 text-base">No modules created yet</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                This course does not have any learning units or assignments attached.
              </p>
              {isInstructor && (
                <button
                  onClick={handleOpenModal}
                  className="mt-4 inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold hover:bg-indigo-700 transition"
                >
                  <Plus className="w-4 h-4 mr-1" />
                  Add First Module
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {sortedModules.map((mod, index) => {
                const payload = mod.content_payload || {};
                const topics = Array.isArray(payload.topics) ? payload.topics : [];
                const readTime = payload.estimated_reading_minutes;
                const notes = payload.instructor_notes;

                return (
                  <div
                    key={mod.id}
                    className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm hover:border-indigo-200 transition space-y-3"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
                      <div className="flex items-center space-x-3">
                        <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-indigo-600 text-white font-bold text-xs shadow-sm">
                          {mod.sequence_order || index + 1}
                        </span>
                        <h3 className="text-base font-bold text-slate-900">
                          {mod.title}
                        </h3>
                      </div>

                      <div className="flex items-center space-x-3 text-xs text-slate-400">
                        {readTime && (
                          <span className="flex items-center text-slate-500 font-medium">
                            <Clock className="w-3.5 h-3.5 mr-1 text-slate-400" />
                            ~{readTime} mins
                          </span>
                        )}
                        <span>
                          Added {new Date(mod.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>

                    {/* Topics Pills */}
                    {topics.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mr-1">
                          Topics:
                        </span>
                        {topics.map((topic: string, i: number) => (
                          <span
                            key={i}
                            className="inline-flex items-center px-2.5 py-0.5 rounded-lg text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100"
                          >
                            <Sparkles className="w-3 h-3 mr-1 text-indigo-500" />
                            {topic}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Instructor Notes */}
                    {notes && (
                      <p className="text-xs text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-100 leading-relaxed">
                        <strong className="text-slate-700">Guide & Notes:</strong> {notes}
                      </p>
                    )}

                    {/* Raw Payload Inspection if customized */}
                    {Object.keys(payload).length > 0 && !topics.length && !notes && (
                      <div className="text-xs font-mono bg-slate-50 p-2.5 rounded-xl text-slate-600 overflow-x-auto flex items-center space-x-1.5">
                        <FileCode className="w-4 h-4 text-slate-400 flex-shrink-0" />
                        <span>{JSON.stringify(payload)}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Roster View (Instructors & Admins only) */}
      {isInstructor && activeTab === 'roster' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center">
              <Users className="w-5 h-5 mr-2 text-indigo-600" />
              Enrolled Students Roster
            </h2>
            <span className="text-xs text-slate-500 font-mono">
              Total Enrolled: {roster.length}
            </span>
          </div>

          {isRosterLoading ? (
            <div className="py-12 flex justify-center items-center">
              <div className="w-8 h-8 border-3 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
            </div>
          ) : isRosterError ? (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700">
              {(rosterError as any)?.response?.data?.detail || 'Failed to load course roster.'}
            </div>
          ) : roster.length === 0 ? (
            <div className="text-center py-16 bg-white rounded-2xl border border-slate-200/80 p-8 shadow-sm">
              <div className="inline-flex p-3 bg-slate-100 text-slate-500 rounded-2xl mb-3">
                <Users className="w-7 h-7" />
              </div>
              <h3 className="font-bold text-slate-900 text-base">No students enrolled yet</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Once students enroll in this published course, they will appear in this roster.
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50/75 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                      <th className="px-6 py-3.5">Student</th>
                      <th className="px-6 py-3.5">Email</th>
                      <th className="px-6 py-3.5">Department</th>
                      <th className="px-6 py-3.5">Enrolled Date</th>
                      <th className="px-6 py-3.5">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-sm">
                    {roster.map((enrollment) => {
                      const student = enrollment.student;
                      const initials = (student?.full_name || 'Student')
                        .split(' ')
                        .map((n) => n[0])
                        .join('')
                        .toUpperCase()
                        .slice(0, 2);

                      return (
                        <tr
                          key={enrollment.id}
                          className="hover:bg-slate-50/50 transition duration-150"
                        >
                          <td className="px-6 py-4 flex items-center space-x-3">
                            <div className="w-9 h-9 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center flex-shrink-0 shadow-inner">
                              {initials}
                            </div>
                            <div>
                              <div className="font-semibold text-slate-900">
                                {student?.full_name || 'Unknown Student'}
                              </div>
                              <div className="text-xs text-slate-400 capitalize">
                                {student?.role || 'student'}
                              </div>
                            </div>
                          </td>

                          <td className="px-6 py-4 text-slate-600">
                            <div className="flex items-center space-x-1.5 text-xs">
                              <Mail className="w-3.5 h-3.5 text-slate-400" />
                              <span>{student?.email || 'N/A'}</span>
                            </div>
                          </td>

                          <td className="px-6 py-4 text-xs text-slate-600">
                            {student?.profile?.department || 'Unassigned'}
                          </td>

                          <td className="px-6 py-4 text-xs text-slate-500 font-mono">
                            {new Date(enrollment.enrolled_at).toLocaleDateString()}
                          </td>

                          <td className="px-6 py-4">
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <CheckCircle2 className="w-3 h-3 mr-1" />
                              {enrollment.status.toUpperCase()}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Add Module Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white w-full max-w-lg rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Layers className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-base">Add Module to Curriculum</h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 rounded-lg p-1 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddModuleSubmit} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start space-x-2 text-rose-800 text-xs">
                  <AlertCircle className="w-4 h-4 text-rose-600 mt-0.5 flex-shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div className="grid grid-cols-4 gap-3">
                <div className="col-span-3">
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Module Title *
                  </label>
                  <input
                    type="text"
                    required
                    value={moduleTitle}
                    onChange={(e) => setModuleTitle(e.target.value)}
                    placeholder="e.g. Week 1: Graph Algorithms"
                    className="block w-full px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                  />
                </div>

                <div className="col-span-1">
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Order #
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={sequenceOrder}
                    onChange={(e) => setSequenceOrder(parseInt(e.target.value) || 1)}
                    className="block w-full px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Key Topics (comma separated)
                </label>
                <input
                  type="text"
                  value={topicsInput}
                  onChange={(e) => setTopicsInput(e.target.value)}
                  placeholder="e.g. Dijkstra, Bellman-Ford, A* Search"
                  className="block w-full px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Estimated Reading / Study Time (Minutes)
                </label>
                <input
                  type="number"
                  min={5}
                  step={5}
                  value={readingTime}
                  onChange={(e) => setReadingTime(parseInt(e.target.value) || 30)}
                  className="block w-full px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Instructor Instructions & Learning Objectives
                </label>
                <textarea
                  rows={3}
                  value={notesInput}
                  onChange={(e) => setNotesInput(e.target.value)}
                  placeholder="Specific student learning outcomes or assignment directions..."
                  className="block w-full px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
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
                  disabled={addModuleMutation.isPending}
                  className="inline-flex items-center px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60 transition"
                >
                  {addModuleMutation.isPending ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                      <span>Appending...</span>
                    </>
                  ) : (
                    <span>Append Module</span>
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
