import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coursesApi, CourseResponse } from '../api/courses';
import {
  assessmentApi,
  Assignment,
  AssignmentSubmission,
  AssignmentSubmissionCreatePayload,
  AssignmentSubmissionGradePayload,
} from '../api/assessment';
import { useAuth } from '../hooks/useAuth';
import {
  ArrowLeft,
  Calendar,
  Award,
  Percent,
  CheckCircle2,
  Clock,
  AlertCircle,
  ExternalLink,
  Send,
  Check,
  X,
  FileText,
  AlertTriangle,
} from 'lucide-react';

export const AssignmentDetailPage: React.FC = () => {
  const { courseId, assignmentId } = useParams<{ courseId: string; assignmentId: string }>();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const isInstructor = user?.role === 'lecturer' || user?.role === 'admin';
  const isStudent = user?.role === 'student';

  // Student form state
  const [contentText, setContentText] = useState('');
  const [fileUrl, setFileUrl] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  // Lecturer grading modal state
  const [gradingStudent, setGradingStudent] = useState<AssignmentSubmission | null>(null);
  const [gradeScore, setGradeScore] = useState<number>(0);
  const [gradeFeedback, setGradeFeedback] = useState<string>('');
  const [gradeError, setGradeError] = useState<string | null>(null);
  const [gradeSuccess, setGradeSuccess] = useState<string | null>(null);

  // 1. Fetch course details
  const { data: course } = useQuery<CourseResponse>({
    queryKey: ['course', courseId],
    queryFn: () => coursesApi.getCourseById(courseId!),
    enabled: !!courseId,
  });

  // 2. Fetch assignment details
  const {
    data: assignment,
    isLoading: isAssignmentLoading,
    isError: isAssignmentError,
    error: assignmentError,
  } = useQuery<Assignment>({
    queryKey: ['assignment', courseId, assignmentId],
    queryFn: () => assessmentApi.getAssignment(courseId!, assignmentId!),
    enabled: !!courseId && !!assignmentId,
  });

  // 3. For student: fetch current user's submission
  const {
    data: mySubmission,
    refetch: refetchMySubmission,
  } = useQuery<AssignmentSubmission | null>({
    queryKey: ['mySubmission', courseId, assignmentId],
    queryFn: () => assessmentApi.getMySubmission(courseId!, assignmentId!),
    enabled: isStudent && !!courseId && !!assignmentId,
  });

  // Prepopulate form if student already has a submission
  React.useEffect(() => {
    if (mySubmission) {
      if (!contentText && mySubmission.content_text) {
        setContentText(mySubmission.content_text);
      }
      if (!fileUrl && mySubmission.file_url) {
        setFileUrl(mySubmission.file_url);
      }
    }
  }, [mySubmission]);

  // 4. For lecturer: fetch all submissions
  const {
    data: submissions = [],
    isLoading: isSubmissionsLoading,
  } = useQuery<AssignmentSubmission[]>({
    queryKey: ['submissions', courseId, assignmentId],
    queryFn: () => assessmentApi.listSubmissions(courseId!, assignmentId!),
    enabled: isInstructor && !!courseId && !!assignmentId,
  });

  // 5. Student Submit Mutation
  const submitMutation = useMutation({
    mutationFn: (payload: AssignmentSubmissionCreatePayload) =>
      assessmentApi.submitAssignment(courseId!, assignmentId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mySubmission', courseId, assignmentId] });
      queryClient.invalidateQueries({ queryKey: ['studentSubmissionsMap', courseId] });
      setSubmitSuccess('Your submission has been recorded.');
      setSubmitError(null);
      refetchMySubmission();
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 403) {
        setSubmitError(detail || 'You are not actively enrolled in this course.');
      } else if (err.response?.status === 409) {
        setSubmitError('Assignment has already been graded. Further submissions are prohibited.');
      } else {
        setSubmitError(detail || 'Failed to submit assignment. Please try again.');
      }
    },
  });

  // 6. Lecturer Grade Mutation
  const gradeMutation = useMutation({
    mutationFn: ({ studentId, payload }: { studentId: string; payload: AssignmentSubmissionGradePayload }) =>
      assessmentApi.gradeSubmission(courseId!, assignmentId!, studentId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['submissions', courseId, assignmentId] });
      setGradingStudent(null);
      setGradeSuccess('Grade successfully recorded and posted to course gradebook.');
      setGradeError(null);
    },
    onError: (err: any) => {
      setGradeError(err.response?.data?.detail || 'Failed to submit grade.');
    },
  });

  const handleStudentSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(null);

    if (!contentText.trim() && !fileUrl.trim()) {
      setSubmitError('Please enter submission content or provide a deliverable URL.');
      return;
    }

    submitMutation.mutate({
      content_text: contentText.trim() || null,
      file_url: fileUrl.trim() || null,
    });
  };

  const handleOpenGradeModal = (sub: AssignmentSubmission) => {
    setGradingStudent(sub);
    setGradeScore(sub.score !== null ? sub.score : assignment ? assignment.max_score : 100);
    setGradeFeedback(sub.feedback || '');
    setGradeError(null);
  };

  const handleGradeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!gradingStudent || !assignment) return;

    if (gradeScore < 0) {
      setGradeError('Score cannot be negative.');
      return;
    }
    if (gradeScore > assignment.max_score) {
      setGradeError(`Score cannot exceed maximum points of ${assignment.max_score}.`);
      return;
    }

    gradeMutation.mutate({
      studentId: gradingStudent.student_id,
      payload: {
        score: Number(gradeScore),
        feedback: gradeFeedback.trim() || null,
      },
    });
  };

  if (isAssignmentLoading) {
    return (
      <div className="py-24 text-center space-y-3">
        <div className="w-8 h-8 border-3 border-indigo-600/30 border-t-indigo-600 rounded-full animate-spin mx-auto" />
        <p className="text-xs text-slate-400">Loading assignment details...</p>
      </div>
    );
  }

  if (isAssignmentError || !assignment) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="bg-rose-50 border border-rose-200 rounded-3xl p-8 text-center text-rose-800 space-y-3">
          <AlertCircle className="w-10 h-10 mx-auto text-rose-600" />
          <h2 className="text-lg font-bold">Assignment Unavailable</h2>
          <p className="text-xs text-rose-600">
            {(assignmentError as any)?.response?.data?.detail || 'This assignment does not exist or has not been published.'}
          </p>
          <Link
            to={`/courses/${courseId}/assignments`}
            className="inline-flex items-center text-xs font-bold text-indigo-600 hover:text-indigo-800"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Return to Assignments
          </Link>
        </div>
      </div>
    );
  }

  const isAlreadyGraded = Boolean(mySubmission && mySubmission.score !== null);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center space-x-2 text-xs font-semibold text-slate-400">
        <Link to="/courses" className="hover:text-slate-600">Courses</Link>
        <span>/</span>
        <Link to={`/courses/${courseId}`} className="hover:text-slate-600">{course?.title || 'Course'}</Link>
        <span>/</span>
        <Link to={`/courses/${courseId}/assignments`} className="hover:text-slate-600">Assignments</Link>
        <span>/</span>
        <span className="text-slate-900 truncate max-w-xs">{assignment.title}</span>
      </div>

      {/* Assignment Header Card */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/80 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 pb-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-lg text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-100">
                Assignment
              </span>
              {isInstructor && (
                <span
                  className={`px-2 py-0.5 rounded-lg text-xs font-bold uppercase tracking-wider ${
                    assignment.is_published
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {assignment.is_published ? 'Published' : 'Draft'}
                </span>
              )}
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              {assignment.title}
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs">
            <div className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl flex items-center">
              <Calendar className="w-4 h-4 mr-1.5 text-slate-400" />
              <div>
                <span className="text-slate-400 block text-[10px] font-bold uppercase">Due Date</span>
                <span className="font-semibold text-slate-800">
                  {assignment.due_at ? new Date(assignment.due_at).toLocaleString() : 'Open deadline'}
                </span>
              </div>
            </div>
            <div className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl flex items-center">
              <Award className="w-4 h-4 mr-1.5 text-indigo-500" />
              <div>
                <span className="text-slate-400 block text-[10px] font-bold uppercase">Points</span>
                <span className="font-semibold text-slate-800">{assignment.max_score} max pts</span>
              </div>
            </div>
            <div className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl flex items-center">
              <Percent className="w-4 h-4 mr-1.5 text-indigo-500" />
              <div>
                <span className="text-slate-400 block text-[10px] font-bold uppercase">Weight</span>
                <span className="font-semibold text-slate-800">{(assignment.weight * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>
        </div>

        {/* Assignment Instructions */}
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Instructions & Rubric
          </h3>
          <div className="text-sm text-slate-700 leading-relaxed bg-slate-50/50 p-4 rounded-2xl border border-slate-100 whitespace-pre-wrap">
            {assignment.description || 'No detailed instructions provided for this assignment.'}
          </div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* STUDENT VIEW: Submission Status & Form                        */}
      {/* ============================================================== */}
      {isStudent && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left 2 Cols: Submit Form */}
          <div className="lg:col-span-2 bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/80 shadow-sm space-y-6">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <h2 className="text-lg font-bold text-slate-900 flex items-center">
                <Send className="w-5 h-5 mr-2 text-indigo-600" />
                {mySubmission ? 'Your Submission' : 'Submit Your Deliverable'}
              </h2>
              {mySubmission && (
                <span
                  className={`px-3 py-1 rounded-full text-xs font-bold ${
                    mySubmission.is_late
                      ? 'bg-orange-100 text-orange-800'
                      : 'bg-emerald-100 text-emerald-800'
                  }`}
                >
                  {mySubmission.is_late
                    ? `Submitted Late (${mySubmission.delay_days} days)`
                    : 'Submitted On Time'}
                </span>
              )}
            </div>

            {submitSuccess && (
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-emerald-800 text-xs flex items-center">
                <CheckCircle2 className="w-4 h-4 mr-2 flex-shrink-0 text-emerald-600" />
                <span>{submitSuccess}</span>
              </div>
            )}

            {submitError && (
              <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-xs flex items-center">
                <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0 text-rose-600" />
                <span>{submitError}</span>
              </div>
            )}

            {isAlreadyGraded && (
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl text-amber-800 text-xs flex items-start">
                <AlertTriangle className="w-4 h-4 mr-2 flex-shrink-0 text-amber-600 mt-0.5" />
                <div>
                  <p className="font-bold">Grading Finalized</p>
                  <p className="mt-0.5">
                    This assignment has already been evaluated and graded by the course instructor. Further edits or resubmissions are disabled.
                  </p>
                </div>
              </div>
            )}

            <form onSubmit={handleStudentSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Submission Text / Notes / Solution *
                </label>
                <textarea
                  rows={6}
                  disabled={isAlreadyGraded}
                  value={contentText}
                  onChange={(e) => setContentText(e.target.value)}
                  placeholder="Paste your code, documentation, reflections, or answer details here..."
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl focus:outline-none focus:border-indigo-600 text-xs font-mono transition disabled:opacity-60 disabled:cursor-not-allowed"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Deliverable URL (Optional Repository or Cloud Link)
                </label>
                <input
                  type="url"
                  disabled={isAlreadyGraded}
                  value={fileUrl}
                  onChange={(e) => setFileUrl(e.target.value)}
                  placeholder="https://github.com/your-username/repo-name or cloud link"
                  className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-2xl focus:outline-none focus:border-indigo-600 text-xs transition disabled:opacity-60 disabled:cursor-not-allowed"
                />
              </div>

              <div className="flex items-center justify-between pt-2">
                <p className="text-[11px] text-slate-400">
                  {mySubmission
                    ? `Last updated: ${new Date(mySubmission.submitted_at).toLocaleString()}`
                    : 'Late submissions are automatically calculated against the due date.'}
                </p>

                <button
                  type="submit"
                  disabled={isAlreadyGraded || submitMutation.isPending}
                  className="inline-flex items-center px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-sm transition"
                >
                  {submitMutation.isPending ? (
                    'Recording...'
                  ) : mySubmission ? (
                    <>
                      <Check className="w-4 h-4 mr-1.5" />
                      Update Submission
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4 mr-1.5" />
                      Submit Assignment
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>

          {/* Right Col: Grade & Feedback Card */}
          <div className="space-y-6">
            <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm space-y-4">
              <h3 className="text-sm font-bold text-slate-900 flex items-center border-b border-slate-100 pb-3">
                <Award className="w-4 h-4 mr-2 text-indigo-600" />
                Evaluation & Grade
              </h3>

              {mySubmission && mySubmission.score !== null ? (
                <div className="space-y-4">
                  <div className="p-4 bg-gradient-to-br from-indigo-50 to-purple-50 rounded-2xl border border-indigo-100 text-center">
                    <span className="text-3xl font-extrabold text-indigo-900">
                      {mySubmission.score}
                    </span>
                    <span className="text-xs font-semibold text-indigo-500">
                      {' '}
                      / {assignment.max_score} pts
                    </span>
                    <p className="text-xs font-bold text-indigo-700 mt-1">
                      {((mySubmission.score / assignment.max_score) * 100).toFixed(1)}% Score
                    </p>
                  </div>

                  {mySubmission.feedback && (
                    <div className="space-y-1">
                      <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                        Instructor Feedback
                      </span>
                      <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-xs text-slate-700 leading-relaxed italic">
                        "{mySubmission.feedback}"
                      </div>
                    </div>
                  )}

                  <div className="text-[11px] text-slate-400 text-center">
                    Evaluated on {new Date(mySubmission.graded_at || mySubmission.updated_at).toLocaleDateString()}
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-slate-400 space-y-2">
                  <Clock className="w-8 h-8 mx-auto text-slate-300" />
                  <p className="text-xs font-semibold text-slate-600">Pending Instructor Evaluation</p>
                  <p className="text-[11px] text-slate-400 max-w-xs mx-auto">
                    {mySubmission
                      ? 'Your submission is queued for grading.'
                      : 'Submit your solution to receive marks and qualitative feedback.'}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* LECTURER / ADMIN VIEW: Submissions Table & Grading Roster      */}
      {/* ============================================================== */}
      {isInstructor && (
        <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/80 shadow-sm space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900 flex items-center">
                <FileText className="w-5 h-5 mr-2 text-indigo-600" />
                Student Submissions Roster
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Review submitted deliverables and assign marks synchronized with the LMS Gradebook.
              </p>
            </div>
            <div className="flex items-center space-x-2 text-xs font-semibold">
              <span className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-xl border border-indigo-100">
                {submissions.length} Submissions Received
              </span>
              <span className="px-3 py-1 bg-emerald-50 text-emerald-700 rounded-xl border border-emerald-100">
                {submissions.filter((s) => s.score !== null).length} Graded
              </span>
            </div>
          </div>

          {gradeSuccess && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-2xl text-emerald-800 text-xs flex items-center justify-between">
              <div className="flex items-center">
                <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-600" />
                <span>{gradeSuccess}</span>
              </div>
              <button onClick={() => setGradeSuccess(null)} className="text-emerald-600 hover:text-emerald-800">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {isSubmissionsLoading ? (
            <div className="py-12 text-center text-xs text-slate-400">Loading submissions...</div>
          ) : submissions.length === 0 ? (
            <div className="py-12 text-center text-slate-400 space-y-2">
              <FileText className="w-8 h-8 mx-auto text-slate-300" />
              <p className="text-xs font-semibold text-slate-600">No student submissions yet</p>
              <p className="text-[11px] text-slate-400">
                Submissions from enrolled students will appear here once submitted.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-400 uppercase text-[10px] font-bold tracking-wider">
                    <th className="py-3 px-4">Student ID</th>
                    <th className="py-3 px-4">Submitted At</th>
                    <th className="py-3 px-4">Timeliness</th>
                    <th className="py-3 px-4">Content / Link</th>
                    <th className="py-3 px-4">Score</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {submissions.map((sub) => (
                    <tr key={sub.id} className="hover:bg-slate-50/80 transition">
                      <td className="py-3.5 px-4 font-mono font-semibold text-slate-800">
                        {sub.student_id.slice(0, 8)}...
                      </td>
                      <td className="py-3.5 px-4 text-slate-500">
                        {new Date(sub.submitted_at).toLocaleString()}
                      </td>
                      <td className="py-3.5 px-4">
                        {sub.is_late ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-orange-100 text-orange-800">
                            Late ({sub.delay_days}d)
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-100 text-emerald-800">
                            On Time
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 max-w-xs">
                        <div className="truncate text-slate-700 font-mono text-[11px]">
                          {sub.content_text || '(No text)'}
                        </div>
                        {sub.file_url && (
                          <a
                            href={sub.file_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center text-indigo-600 hover:text-indigo-800 text-[10px] font-semibold mt-0.5"
                          >
                            <ExternalLink className="w-3 h-3 mr-1" />
                            {sub.file_url}
                          </a>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        {sub.score !== null ? (
                          <span className="font-bold text-slate-900">
                            {sub.score} / {assignment.max_score}
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">Not graded</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <button
                          onClick={() => handleOpenGradeModal(sub)}
                          className="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-600 hover:text-white text-indigo-700 font-bold rounded-lg text-xs transition"
                        >
                          {sub.score !== null ? 'Re-grade' : 'Grade'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Lecturer Grading Modal */}
      {gradingStudent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl border border-slate-100 space-y-6 relative">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Grade Student Deliverable</h3>
                <p className="text-xs text-slate-400 font-mono mt-0.5">
                  Student: {gradingStudent.student_id}
                </p>
              </div>
              <button
                onClick={() => setGradingStudent(null)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Student's submitted work snippet */}
            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200/80 space-y-2 text-xs">
              <span className="font-bold text-slate-500 uppercase text-[10px]">Submitted Content</span>
              <p className="text-slate-800 whitespace-pre-wrap font-mono text-[11px] max-h-36 overflow-y-auto">
                {gradingStudent.content_text || '(No text content provided)'}
              </p>
              {gradingStudent.file_url && (
                <div className="pt-1">
                  <a
                    href={gradingStudent.file_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center text-indigo-600 hover:text-indigo-800 text-xs font-semibold"
                  >
                    <ExternalLink className="w-3.5 h-3.5 mr-1" />
                    Open Deliverable Link
                  </a>
                </div>
              )}
            </div>

            {gradeError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-center">
                <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
                <span>{gradeError}</span>
              </div>
            )}

            <form onSubmit={handleGradeSubmit} className="space-y-4 text-xs font-medium">
              <div>
                <label className="block text-slate-700 mb-1 font-semibold">
                  Score (out of {assignment.max_score} pts) *
                </label>
                <input
                  type="number"
                  min={0}
                  max={assignment.max_score}
                  step={0.5}
                  required
                  value={gradeScore}
                  onChange={(e) => setGradeScore(Number(e.target.value))}
                  className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-indigo-600 text-sm font-bold transition"
                />
              </div>

              <div>
                <label className="block text-slate-700 mb-1 font-semibold">
                  Qualitative Feedback & Guidance
                </label>
                <textarea
                  rows={4}
                  value={gradeFeedback}
                  onChange={(e) => setGradeFeedback(e.target.value)}
                  placeholder="Provide constructive feedback for the student..."
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:border-indigo-600 transition"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setGradingStudent(null)}
                  className="px-4 py-2 border border-slate-200 rounded-xl text-slate-600 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={gradeMutation.isPending}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-sm transition disabled:opacity-60"
                >
                  {gradeMutation.isPending ? 'Saving Grade...' : 'Save & Upsert Gradebook'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
