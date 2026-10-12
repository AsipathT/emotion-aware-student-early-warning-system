import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coursesApi, CourseResponse } from '../api/courses';
import { enrollmentsApi, EnrollmentResponse } from '../api/enrollments';
import {
  gradebookApi,
  CourseGradebookResponse,
  MyGradebookResponse,
  ManualGradePayload,
} from '../api/gradebook';
import { useAuth } from '../hooks/useAuth';
import {
  Award,
  ArrowLeft,
  Download,
  Plus,
  Search,
  CheckCircle2,
  AlertCircle,
  X,
  TrendingUp,
  Users,
  GraduationCap,
  Percent,
} from 'lucide-react';

export const CourseGradebookPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const isInstructor = user?.role === 'lecturer' || user?.role === 'admin';
  const isStudent = user?.role === 'student';

  // Search filter for instructor view
  const [searchQuery, setSearchQuery] = useState('');

  // Manual grade modal state
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [targetStudentId, setTargetStudentId] = useState('');
  const [manualTitle, setManualTitle] = useState('');
  const [manualScore, setManualScore] = useState<number>(100);
  const [manualMaxScore, setManualMaxScore] = useState<number>(100);
  const [manualWeight, setManualWeight] = useState<number>(0.1);
  const [manualError, setManualError] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  // 1. Fetch course details
  const { data: course } = useQuery<CourseResponse>({
    queryKey: ['course', courseId],
    queryFn: () => coursesApi.getCourseById(courseId!),
    enabled: !!courseId,
  });

  // 2. Fetch instructor full gradebook
  const {
    data: instructorGradebook,
    isLoading: isInstructorLoading,
    isError: isInstructorError,
    error: instructorError,
  } = useQuery<CourseGradebookResponse>({
    queryKey: ['courseGradebook', courseId],
    queryFn: () => gradebookApi.getCourseGradebook(courseId!),
    enabled: isInstructor && !!courseId,
  });

  // 3. Fetch course roster (to populate manual grade student selector)
  const { data: roster = [] } = useQuery<EnrollmentResponse[]>({
    queryKey: ['courseRoster', courseId],
    queryFn: () => enrollmentsApi.getCourseRoster(courseId!),
    enabled: isInstructor && isManualModalOpen && !!courseId,
  });

  // 4. Fetch student personal gradebook
  const {
    data: studentGradebook,
    isLoading: isStudentLoading,
    isError: isStudentError,
    error: studentError,
  } = useQuery<MyGradebookResponse>({
    queryKey: ['myGradebook', courseId],
    queryFn: () => gradebookApi.getMyGradebook(courseId!),
    enabled: isStudent && !!courseId,
  });

  // 5. Add manual grade mutation
  const manualGradeMutation = useMutation({
    mutationFn: (payload: ManualGradePayload) =>
      gradebookApi.addManualGrade(courseId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courseGradebook', courseId] });
      setIsManualModalOpen(false);
      setManualTitle('');
      setTargetStudentId('');
      setManualScore(100);
      setManualMaxScore(100);
      setManualWeight(0.1);
      setManualError(null);
      setSuccessBanner('Manual grade entry recorded successfully.');
    },
    onError: (err: unknown) => {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setManualError(axiosErr.response?.data?.detail || 'Failed to record manual grade.');
    },
  });

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setManualError(null);

    if (!targetStudentId.trim()) {
      setManualError('Please select or specify a student ID.');
      return;
    }
    if (!manualTitle.trim()) {
      setManualError('Title cannot be empty.');
      return;
    }
    if (manualScore < 0) {
      setManualError('Score cannot be negative.');
      return;
    }
    if (manualMaxScore <= 0) {
      setManualError('Max score must be greater than zero.');
      return;
    }

    manualGradeMutation.mutate({
      student_id: targetStudentId.trim(),
      title: manualTitle.trim(),
      score: Number(manualScore),
      max_score: Number(manualMaxScore),
      weight: Number(manualWeight),
    });
  };

  const handleExportCsv = async () => {
    try {
      await gradebookApi.downloadGradebookCsv(courseId!, course?.title);
    } catch {
      alert('Failed to download CSV export. Please try again.');
    }
  };

  const getScoreBadgeColor = (percentage: number) => {
    if (percentage >= 80) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    if (percentage >= 65) return 'bg-indigo-50 text-indigo-700 border-indigo-200';
    if (percentage >= 50) return 'bg-amber-50 text-amber-700 border-amber-200';
    return 'bg-rose-50 text-rose-700 border-rose-200';
  };

  const getGradeLetter = (percentage: number) => {
    if (percentage >= 85) return 'A+';
    if (percentage >= 75) return 'A';
    if (percentage >= 65) return 'B';
    if (percentage >= 55) return 'C';
    if (percentage >= 45) return 'D';
    return 'F';
  };

  // Filter students for instructor matrix
  const filteredStudents = (instructorGradebook?.students || []).filter((s) => {
    const q = searchQuery.toLowerCase();
    return s.full_name.toLowerCase().includes(q) || s.email.toLowerCase().includes(q);
  });

  // Calculate instructor metrics
  const classAvg =
    instructorGradebook?.students?.length
      ? Math.round(
          (instructorGradebook.students.reduce((acc, curr) => acc + curr.score_so_far, 0) /
            instructorGradebook.students.length) *
            10
        ) / 10
      : 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center space-x-2 text-xs font-semibold text-slate-400">
        <Link to="/courses" className="hover:text-slate-600">Courses</Link>
        <span>/</span>
        <Link to={`/courses/${courseId}`} className="hover:text-slate-600">
          {course?.title || 'Course Details'}
        </Link>
        <span>/</span>
        <span className="text-slate-900">Official Gradebook</span>
      </div>

      {/* Success Banner */}
      {successBanner && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center justify-between text-emerald-800 text-xs shadow-sm">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span className="font-semibold">{successBanner}</span>
          </div>
          <button
            onClick={() => setSuccessBanner(null)}
            className="text-emerald-600 hover:text-emerald-900"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Hero Header */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/80 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-1.5">
          <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-indigo-50 text-indigo-700 border border-indigo-100">
            <Award className="w-3.5 h-3.5 mr-1 text-indigo-600" />
            <span>Academic Performance Record</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            {course?.title ? `${course.title} — Gradebook` : 'Course Gradebook'}
          </h1>
          <p className="text-xs text-slate-500">
            Consolidated academic standing across assignments, quizzes, and manual evaluations.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to={`/courses/${courseId}`}
            className="inline-flex items-center px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
            Back to Course
          </Link>

          {isInstructor && (
            <>
              <button
                onClick={handleExportCsv}
                className="inline-flex items-center px-4 py-2.5 bg-slate-900 hover:bg-black text-white font-semibold text-xs rounded-xl shadow-sm transition"
              >
                <Download className="w-3.5 h-3.5 mr-1.5" />
                Export CSV
              </button>
              <button
                onClick={() => setIsManualModalOpen(true)}
                className="inline-flex items-center px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-sm transition"
              >
                <Plus className="w-3.5 h-3.5 mr-1.5" />
                Manual Grade
              </button>
            </>
          )}
        </div>
      </div>

      {/* ============================================================== */}
      {/* INSTRUCTOR / ADMIN VIEW                                        */}
      {/* ============================================================== */}
      {isInstructor && (
        <div className="space-y-6">
          {/* Quick Stats Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4">
              <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl">
                <TrendingUp className="w-6 h-6" />
              </div>
              <div>
                <p className="text-xs font-bold uppercase text-slate-400">Class Average</p>
                <p className="text-xl font-extrabold text-slate-900">{classAvg}%</p>
              </div>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4">
              <div className="p-3 bg-purple-50 text-purple-600 rounded-xl">
                <Users className="w-6 h-6" />
              </div>
              <div>
                <p className="text-xs font-bold uppercase text-slate-400">Enrolled Students</p>
                <p className="text-xl font-extrabold text-slate-900">
                  {instructorGradebook?.students?.length || 0}
                </p>
              </div>
            </div>

            <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4">
              <div className="p-3 bg-emerald-50 text-emerald-600 rounded-xl">
                <GraduationCap className="w-6 h-6" />
              </div>
              <div>
                <p className="text-xs font-bold uppercase text-slate-400">Assessment Items</p>
                <p className="text-xl font-extrabold text-slate-900">
                  {instructorGradebook?.items?.length || 0}
                </p>
              </div>
            </div>
          </div>

          {/* Search Bar */}
          <div className="flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search students by name or email..."
                className="w-full pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-indigo-600 transition"
              />
            </div>
            <span className="text-xs text-slate-400 font-medium">
              Showing {filteredStudents.length} of {instructorGradebook?.students?.length || 0} students
            </span>
          </div>

          {/* Loading State */}
          {isInstructorLoading && (
            <div className="py-20 text-center space-y-3">
              <div className="w-8 h-8 border-3 border-indigo-600/30 border-t-indigo-600 rounded-full animate-spin mx-auto" />
              <p className="text-xs text-slate-400">Loading course gradebook matrix...</p>
            </div>
          )}

          {/* Error State */}
          {isInstructorError && (
            <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-xs flex items-center">
              <AlertCircle className="w-5 h-5 mr-2 text-rose-600 flex-shrink-0" />
              <span>
                {((instructorError as unknown) as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                  'Failed to load gradebook records.'}
              </span>
            </div>
          )}

          {/* Matrix Table */}
          {!isInstructorLoading && !isInstructorError && (
            <div className="bg-white rounded-3xl border border-slate-200/80 shadow-sm overflow-hidden">
              {filteredStudents.length === 0 ? (
                <div className="py-16 text-center space-y-2">
                  <Award className="w-10 h-10 text-slate-300 mx-auto" />
                  <p className="text-sm font-bold text-slate-700">No grades recorded yet</p>
                  <p className="text-xs text-slate-400 max-w-sm mx-auto">
                    Grade student assignments or click "+ Manual Grade" above to record marks.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                        <th className="px-6 py-4">Student</th>
                        {(instructorGradebook?.items || []).map((item) => (
                          <th key={item.key} className="px-4 py-4 text-center">
                            <div className="font-bold text-slate-800">{item.title}</div>
                            <div className="text-[10px] text-slate-400 lowercase font-normal">
                              max {item.max_score} • {(item.weight * 100).toFixed(0)}%
                            </div>
                          </th>
                        ))}
                        <th className="px-6 py-4 text-right">Weighted Total</th>
                        <th className="px-6 py-4 text-right">Score So Far</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-xs">
                      {filteredStudents.map((s) => (
                        <tr key={s.student_id} className="hover:bg-slate-50/50 transition">
                          <td className="px-6 py-4">
                            <div className="font-bold text-slate-900">{s.full_name}</div>
                            <div className="text-[11px] text-slate-400">{s.email}</div>
                          </td>

                          {(instructorGradebook?.items || []).map((item) => {
                            const entry = s.entries.find(
                              (e) => `${e.item_type}:${e.item_id || e.title}` === item.key
                            );
                            return (
                              <td key={item.key} className="px-4 py-4 text-center font-mono">
                                {entry ? (
                                  <span className="font-semibold text-slate-800">
                                    {entry.score}
                                    <span className="text-slate-400 text-[11px]">
                                      /{entry.max_score}
                                    </span>
                                  </span>
                                ) : (
                                  <span className="text-slate-300">-</span>
                                )}
                              </td>
                            );
                          })}

                          <td className="px-6 py-4 text-right font-mono font-bold text-slate-800">
                            {s.weighted_total.toFixed(2)}
                          </td>

                          <td className="px-6 py-4 text-right">
                            <span
                              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border ${getScoreBadgeColor(
                                s.score_so_far
                              )}`}
                            >
                              {s.score_so_far.toFixed(1)}% ({getGradeLetter(s.score_so_far)})
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ============================================================== */}
      {/* STUDENT VIEW (Personal Standing & Breakdown)                  */}
      {/* ============================================================== */}
      {isStudent && (
        <div className="space-y-6">
          {/* Loading State */}
          {isStudentLoading && (
            <div className="py-20 text-center space-y-3">
              <div className="w-8 h-8 border-3 border-indigo-600/30 border-t-indigo-600 rounded-full animate-spin mx-auto" />
              <p className="text-xs text-slate-400">Loading your grades...</p>
            </div>
          )}

          {/* Error State */}
          {isStudentError && (
            <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-xs flex items-center">
              <AlertCircle className="w-5 h-5 mr-2 text-rose-600 flex-shrink-0" />
              <span>
                {((studentError as unknown) as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                  'Failed to load your personal grade record.'}
              </span>
            </div>
          )}

          {!isStudentLoading && !isStudentError && (
            <>
              {/* Performance Summary Banner */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-gradient-to-br from-indigo-600 to-indigo-800 text-white p-6 rounded-3xl shadow-sm flex flex-col justify-between space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase font-bold tracking-wider text-indigo-200">
                      Overall Score
                    </span>
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-black bg-white/20 text-white">
                      Grade: {getGradeLetter(studentGradebook?.score_so_far || 0)}
                    </span>
                  </div>
                  <div>
                    <div className="text-3xl font-black">
                      {(studentGradebook?.score_so_far || 0).toFixed(1)}%
                    </div>
                    <p className="text-xs text-indigo-200 mt-0.5">Average across graded tasks</p>
                  </div>
                </div>

                <div className="bg-white p-6 rounded-3xl border border-slate-200/80 shadow-sm flex flex-col justify-between space-y-3">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-xs uppercase font-bold tracking-wider">
                      Weighted Total
                    </span>
                    <Award className="w-4 h-4 text-indigo-600" />
                  </div>
                  <div>
                    <div className="text-3xl font-black text-slate-900">
                      {(studentGradebook?.weighted_total || 0).toFixed(2)}
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">Points weighted towards final</p>
                  </div>
                </div>

                <div className="bg-white p-6 rounded-3xl border border-slate-200/80 shadow-sm flex flex-col justify-between space-y-3">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-xs uppercase font-bold tracking-wider">
                      Completed Evaluations
                    </span>
                    <Percent className="w-4 h-4 text-emerald-600" />
                  </div>
                  <div>
                    <div className="text-3xl font-black text-slate-900">
                      {studentGradebook?.entries?.length || 0}
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">Graded deliverables</p>
                  </div>
                </div>
              </div>

              {/* Items Breakdown Table */}
              <div className="bg-white rounded-3xl border border-slate-200/80 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-100 flex items-center justify-between">
                  <h3 className="font-bold text-slate-900 text-sm flex items-center">
                    <Award className="w-4 h-4 mr-2 text-indigo-600" />
                    Detailed Grades Breakdown
                  </h3>
                  <span className="text-xs text-slate-400">
                    {studentGradebook?.entries?.length || 0} evaluated items
                  </span>
                </div>

                {!studentGradebook?.entries?.length ? (
                  <div className="py-16 text-center space-y-2">
                    <Award className="w-10 h-10 text-slate-300 mx-auto" />
                    <p className="text-sm font-bold text-slate-700">No grades posted yet</p>
                    <p className="text-xs text-slate-400 max-w-sm mx-auto">
                      Your instructor has not yet graded any submissions for this course. Check back later!
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                          <th className="px-6 py-4">Assessment Title</th>
                          <th className="px-6 py-4">Type</th>
                          <th className="px-6 py-4 text-center">Score</th>
                          <th className="px-6 py-4 text-center">Weight</th>
                          <th className="px-6 py-4 text-right">Date Recorded</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-xs">
                        {studentGradebook.entries.map((e) => {
                          const pct = (e.score / (e.max_score || 100)) * 100;
                          return (
                            <tr key={e.id} className="hover:bg-slate-50/50 transition">
                              <td className="px-6 py-4 font-bold text-slate-900">{e.title}</td>
                              <td className="px-6 py-4">
                                <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-600">
                                  {e.item_type}
                                </span>
                              </td>
                              <td className="px-6 py-4 text-center font-mono">
                                <span className="font-bold text-slate-900">{e.score}</span>
                                <span className="text-slate-400"> / {e.max_score}</span>
                                <span
                                  className={`ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${getScoreBadgeColor(
                                    pct
                                  )}`}
                                >
                                  {pct.toFixed(0)}%
                                </span>
                              </td>
                              <td className="px-6 py-4 text-center font-mono text-slate-600">
                                {(e.weight * 100).toFixed(0)}%
                              </td>
                              <td className="px-6 py-4 text-right text-slate-400 font-mono text-[11px]">
                                {new Date(e.recorded_at).toLocaleDateString()}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Manual Grade Entry Modal */}
      {isManualModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white w-full max-w-md rounded-3xl shadow-xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Award className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-sm">Add Manual Grade</h3>
              </div>
              <button
                onClick={() => setIsManualModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleManualSubmit} className="p-6 space-y-4">
              {manualError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs flex items-center">
                  <AlertCircle className="w-4 h-4 mr-2 text-rose-600 flex-shrink-0" />
                  <span>{manualError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Target Student *
                </label>
                {roster.length > 0 ? (
                  <select
                    value={targetStudentId}
                    onChange={(e) => setTargetStudentId(e.target.value)}
                    required
                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-indigo-600 transition"
                  >
                    <option value="">Select Enrolled Student...</option>
                    {roster.map((r) => (
                      <option key={r.student_id} value={String(r.student_id)}>
                        {r.student?.full_name || 'Student'} ({r.student?.email || String(r.student_id).slice(0, 8)})
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    required
                    value={targetStudentId}
                    onChange={(e) => setTargetStudentId(e.target.value)}
                    placeholder="Enter Student UUID or ID..."
                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-indigo-600 transition"
                  />
                )}
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Assessment / Task Title *
                </label>
                <input
                  type="text"
                  required
                  value={manualTitle}
                  onChange={(e) => setManualTitle(e.target.value)}
                  placeholder="e.g. Midterm Lab Presentation"
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-indigo-600 transition"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Score *</label>
                  <input
                    type="number"
                    min={0}
                    step={0.5}
                    required
                    value={manualScore}
                    onChange={(e) => setManualScore(parseFloat(e.target.value) || 0)}
                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono focus:outline-none focus:border-indigo-600 transition"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Max Pts *</label>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    required
                    value={manualMaxScore}
                    onChange={(e) => setManualMaxScore(parseFloat(e.target.value) || 100)}
                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono focus:outline-none focus:border-indigo-600 transition"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Weight</label>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    value={manualWeight}
                    onChange={(e) => setManualWeight(parseFloat(e.target.value) || 0.1)}
                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono focus:outline-none focus:border-indigo-600 transition"
                  />
                </div>
              </div>

              <div className="pt-3 flex items-center justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setIsManualModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={manualGradeMutation.isPending}
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-sm transition disabled:opacity-60"
                >
                  {manualGradeMutation.isPending ? 'Recording...' : 'Post Grade'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
