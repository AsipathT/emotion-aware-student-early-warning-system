import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coursesApi, CourseResponse } from '../api/courses';
import { assessmentApi, Quiz, QuizAttempt } from '../api/assessment';
import { useAuth } from '../hooks/useAuth';
import { QuizPlayerModal } from '../components/quiz/QuizPlayerModal';
import { QuizEditorModal } from '../components/quiz/QuizEditorModal';
import {
  HelpCircle,
  Plus,
  ArrowLeft,
  Clock,
  Award,
  CheckCircle2,
  AlertCircle,
  Edit2,
  Trash2,
  Play,
  Users,
  Eye,
  X,
} from 'lucide-react';

export const CourseQuizzesPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const isInstructor = user?.role === 'lecturer' || user?.role === 'admin';
  const isStudent = user?.role === 'student';

  // Modal states
  const [selectedQuizIdForPlayer, setSelectedQuizIdForPlayer] = useState<string | null>(null);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [quizToEdit, setQuizToEdit] = useState<Quiz | null>(null);

  // Lecturer view attempts modal
  const [viewAttemptsQuizId, setViewAttemptsQuizId] = useState<string | null>(null);

  // Banners
  const [successBanner, setSuccessBanner] = useState<string | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  // 1. Course Details
  const { data: course } = useQuery<CourseResponse>({
    queryKey: ['course', courseId],
    queryFn: () => coursesApi.getCourseById(courseId!),
    enabled: !!courseId,
  });

  // 2. Fetch Quizzes List
  const {
    data: quizzes = [],
    isLoading: isLoadingQuizzes,
    isError: isQuizzesError,
  } = useQuery<Quiz[]>({
    queryKey: ['course_quizzes', courseId],
    queryFn: () => assessmentApi.getQuizzes(courseId!),
    enabled: !!courseId,
  });

  // 3. Lecturer Attempts List for Selected Quiz
  const { data: quizAttempts = [], isLoading: isLoadingAttempts } = useQuery<QuizAttempt[]>({
    queryKey: ['quizAttempts', courseId, viewAttemptsQuizId],
    queryFn: () => assessmentApi.listQuizAttempts(courseId!, viewAttemptsQuizId!),
    enabled: !!courseId && !!viewAttemptsQuizId && isInstructor,
  });

  // 4. Delete Quiz Mutation
  const deleteMutation = useMutation({
    mutationFn: (quizId: string) => assessmentApi.deleteQuiz(courseId!, quizId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['course_quizzes', courseId] });
      setSuccessBanner('Quiz removed successfully.');
    },
    onError: (err: any) => {
      setErrorBanner(err?.response?.data?.detail || 'Failed to delete quiz.');
    },
  });

  const handleDelete = (quizId: string, title: string) => {
    if (window.confirm(`Are you sure you want to permanently delete quiz "${title}"?`)) {
      deleteMutation.mutate(quizId);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Toast Banners */}
      {successBanner && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center justify-between text-emerald-800 text-sm animate-fade-in shadow-sm">
          <div className="flex items-center space-x-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <span className="font-semibold">{successBanner}</span>
          </div>
          <button onClick={() => setSuccessBanner(null)} className="text-emerald-600 hover:text-emerald-800 p-1">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {errorBanner && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl flex items-center justify-between text-rose-800 text-sm animate-fade-in shadow-sm">
          <div className="flex items-center space-x-2.5">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <span className="font-semibold">{errorBanner}</span>
          </div>
          <button onClick={() => setErrorBanner(null)} className="text-rose-600 hover:text-rose-800 p-1">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Navigation Breadcrumb */}
      <div>
        <Link
          to={`/courses/${courseId}`}
          className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-indigo-600 transition group"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5 group-hover:-translate-x-1 transition" />
          Back to Course Overview
        </Link>
      </div>

      {/* Hero Card */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/80 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <div className="flex items-center space-x-2 text-xs font-bold text-purple-600 uppercase tracking-wider mb-2">
            <HelpCircle className="w-4 h-4" />
            <span>Interactive Module Assessments</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            {course?.title ? `${course.title} — Online Quizzes` : 'Online Quizzes & Tests'}
          </h1>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl">
            Auto-graded quizzes for continuous knowledge verification. Completed scores synchronize directly into the course Gradebook.
          </p>
        </div>

        {/* Action Button for Lecturer */}
        {isInstructor && (
          <button
            type="button"
            onClick={() => {
              setQuizToEdit(null);
              setIsEditorOpen(true);
            }}
            className="inline-flex items-center px-5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold text-sm rounded-xl shadow-sm transition"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            Create Quiz
          </button>
        )}
      </div>

      {/* Quizzes List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-900">
            Available Quizzes ({quizzes.length})
          </h2>
        </div>

        {isLoadingQuizzes && (
          <div className="bg-white rounded-3xl border border-slate-200/80 p-12 text-center">
            <div className="w-8 h-8 border-3 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-xs font-medium text-slate-500">Loading module quizzes...</p>
          </div>
        )}

        {isQuizzesError && (
          <div className="bg-rose-50 border border-rose-200 rounded-3xl p-6 text-center text-rose-700 text-sm">
            Failed to retrieve course quizzes.
          </div>
        )}

        {!isLoadingQuizzes && quizzes.length === 0 && (
          <div className="bg-white rounded-3xl border border-slate-200/80 p-12 text-center space-y-3">
            <div className="w-12 h-12 bg-purple-50 text-purple-500 rounded-2xl mx-auto flex items-center justify-center">
              <HelpCircle className="w-6 h-6" />
            </div>
            <h3 className="text-base font-bold text-slate-800">No Quizzes Scheduled</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              {isInstructor
                ? 'Click "Create Quiz" above to add your first interactive test for this course.'
                : 'There are no active online tests published for this module yet.'}
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {quizzes.map((quiz) => (
            <div
              key={quiz.id}
              className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm hover:shadow-md transition flex flex-col justify-between space-y-4"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                      quiz.is_published
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-amber-50 text-amber-700 border border-amber-200'
                    }`}
                  >
                    {quiz.is_published ? 'Published' : 'Draft'}
                  </span>

                  <div className="flex items-center space-x-2 text-xs font-semibold text-slate-500">
                    <Award className="w-3.5 h-3.5 text-indigo-600" />
                    <span>Max {quiz.max_score} pts</span>
                  </div>
                </div>

                <div>
                  <h3 className="text-base font-bold text-slate-900 group-hover:text-purple-600 transition">
                    {quiz.title}
                  </h3>
                  <p className="text-xs text-slate-500 line-clamp-2 mt-1">
                    {quiz.description || 'Module knowledge verification quiz.'}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 font-medium">
                  {quiz.time_limit_minutes ? (
                    <span className="flex items-center">
                      <Clock className="w-3.5 h-3.5 mr-1 text-slate-400" />
                      {quiz.time_limit_minutes} mins
                    </span>
                  ) : (
                    <span>Untimed</span>
                  )}

                  <span>•</span>

                  <span>Max {quiz.max_attempts} {quiz.max_attempts === 1 ? 'attempt' : 'attempts'}</span>

                  <span>•</span>

                  <span>Weight: {quiz.weight}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                {/* Student: Start / Retake Quiz */}
                {isStudent && (
                  <button
                    type="button"
                    onClick={() => setSelectedQuizIdForPlayer(quiz.id)}
                    className="inline-flex items-center px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold text-xs rounded-xl shadow-sm transition"
                  >
                    <Play className="w-3.5 h-3.5 mr-1.5" />
                    Take Quiz
                  </button>
                )}

                {/* Lecturer Controls */}
                {isInstructor && (
                  <div className="flex items-center space-x-2 w-full justify-between">
                    <button
                      type="button"
                      onClick={() => setViewAttemptsQuizId(quiz.id)}
                      className="inline-flex items-center px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl transition"
                    >
                      <Users className="w-3.5 h-3.5 mr-1.5" />
                      View Attempts
                    </button>

                    <div className="flex items-center space-x-1.5">
                      <button
                        type="button"
                        onClick={() => setSelectedQuizIdForPlayer(quiz.id)}
                        className="p-2 text-slate-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition"
                        title="Preview Quiz as Student"
                      >
                        <Eye className="w-4 h-4" />
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          setQuizToEdit(quiz);
                          setIsEditorOpen(true);
                        }}
                        className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition"
                        title="Edit Quiz"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>

                      <button
                        type="button"
                        onClick={() => handleDelete(quiz.id, quiz.title)}
                        className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                        title="Delete Quiz"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 1. Student / Preview Interactive Quiz Player Modal */}
      {selectedQuizIdForPlayer && (
        <QuizPlayerModal
          courseId={courseId!}
          quizId={selectedQuizIdForPlayer}
          isOpen={!!selectedQuizIdForPlayer}
          onClose={() => setSelectedQuizIdForPlayer(null)}
          onCompleted={() => {
            setSuccessBanner('Quiz submitted and scored successfully!');
          }}
        />
      )}

      {/* 2. Lecturer Quiz Editor Modal */}
      {isEditorOpen && (
        <QuizEditorModal
          courseId={courseId!}
          isOpen={isEditorOpen}
          onClose={() => {
            setIsEditorOpen(false);
            setQuizToEdit(null);
          }}
          quizToEdit={quizToEdit}
          onSaved={() => {
            setSuccessBanner(quizToEdit ? 'Quiz updated successfully.' : 'Quiz created successfully.');
          }}
        />
      )}

      {/* 3. Lecturer Student Attempts Drawer Modal */}
      {viewAttemptsQuizId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-3xl border border-slate-200 shadow-2xl w-full max-w-2xl my-8 overflow-hidden flex flex-col max-h-[85vh]">
            <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <Users className="w-5 h-5 text-indigo-400" />
                <h3 className="font-bold text-base">Student Quiz Submissions</h3>
              </div>
              <button
                onClick={() => setViewAttemptsQuizId(null)}
                className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1 space-y-4">
              {isLoadingAttempts ? (
                <div className="py-12 text-center text-xs text-slate-400">Loading student attempts...</div>
              ) : quizAttempts.length === 0 ? (
                <div className="py-12 text-center text-xs text-slate-400">
                  No students have completed this quiz yet.
                </div>
              ) : (
                <div className="divide-y divide-slate-100 border border-slate-200/80 rounded-2xl overflow-hidden">
                  {quizAttempts.map((att) => (
                    <div key={att.id} className="p-4 bg-white flex items-center justify-between text-sm">
                      <div>
                        <span className="font-mono text-xs font-bold text-slate-700 block">
                          Student Ref: {att.student_id.slice(0, 12)}...
                        </span>
                        <span className="text-[11px] text-slate-400">
                          {att.completed_at ? new Date(att.completed_at).toLocaleString() : 'In progress'}
                        </span>
                      </div>

                      <div className="flex items-center space-x-3">
                        <span className="px-2.5 py-1 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-lg font-bold text-xs">
                          {att.score !== null ? `${att.score.toFixed(1)} / ${att.max_score} pts` : 'Pending'}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                            att.submitted ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {att.submitted ? 'Submitted' : 'Ongoing'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
