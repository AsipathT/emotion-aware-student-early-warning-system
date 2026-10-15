import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { assessmentApi, Quiz, QuizAttempt } from '../../api/assessment';
import {
  HelpCircle,
  Clock,
  CheckCircle2,
  AlertCircle,
  Award,
  ChevronRight,
  ChevronLeft,
  X,
  Send,
  RotateCcw,
  Sparkles,
} from 'lucide-react';

interface QuizPlayerModalProps {
  courseId: string;
  quizId: string;
  isOpen: boolean;
  onClose: () => void;
  onCompleted?: () => void;
}

export const QuizPlayerModal: React.FC<QuizPlayerModalProps> = ({
  courseId,
  quizId,
  isOpen,
  onClose,
  onCompleted,
}) => {
  const queryClient = useQueryClient();

  // Test session state
  const [activeAttempt, setActiveAttempt] = useState<QuizAttempt | null>(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({});
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const [submissionResult, setSubmissionResult] = useState<QuizAttempt | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [confirmSubmitOpen, setConfirmSubmitOpen] = useState(false);

  // 1. Fetch full quiz detail (contains questions)
  const {
    data: quiz,
    isLoading: isLoadingQuiz,
    isError: isQuizError,
    error: quizError,
  } = useQuery<Quiz>({
    queryKey: ['quiz', courseId, quizId],
    queryFn: () => assessmentApi.getQuiz(courseId, quizId),
    enabled: isOpen && !!courseId && !!quizId,
  });

  // 2. Fetch my past attempts
  const { data: myAttempts = [], refetch: refetchMyAttempts } = useQuery<QuizAttempt[]>({
    queryKey: ['myQuizAttempts', courseId, quizId],
    queryFn: () => assessmentApi.getMyQuizAttempts(courseId, quizId),
    enabled: isOpen && !!courseId && !!quizId,
  });

  const questions = quiz?.questions || [];
  const totalQuestions = questions.length;
  const currentQuestion = questions[currentQuestionIndex];

  const submittedAttempts = myAttempts.filter((a) => a.submitted);
  const attemptsUsed = submittedAttempts.length;
  const maxAttempts = quiz?.max_attempts ?? 1;
  const hasRemainingAttempts = attemptsUsed < maxAttempts;
  const bestScore = submittedAttempts.length
    ? Math.max(...submittedAttempts.map((a) => a.score ?? 0))
    : null;

  // 3. Start Attempt Mutation
  const startAttemptMutation = useMutation({
    mutationFn: () => assessmentApi.startQuizAttempt(courseId, quizId),
    onSuccess: (newAttempt) => {
      setActiveAttempt(newAttempt);
      setSelectedAnswers({});
      setCurrentQuestionIndex(0);
      setSubmissionResult(null);
      setErrorMessage(null);

      if (quiz?.time_limit_minutes) {
        setSecondsRemaining(quiz.time_limit_minutes * 60);
      } else {
        setSecondsRemaining(null);
      }
    },
    onError: (err: any) => {
      setErrorMessage(
        err?.response?.data?.detail || 'Failed to start quiz attempt. You may have reached the maximum attempt limit.'
      );
    },
  });

  // 4. Submit Attempt Mutation
  const submitAttemptMutation = useMutation({
    mutationFn: () => {
      if (!activeAttempt) throw new Error('No active attempt');
      return assessmentApi.submitQuizAttempt(courseId, quizId, activeAttempt.id, {
        answers: selectedAnswers,
      });
    },
    onSuccess: (result) => {
      setSubmissionResult(result);
      setActiveAttempt(null);
      setConfirmSubmitOpen(false);
      refetchMyAttempts();
      queryClient.invalidateQueries({ queryKey: ['course_gradebook', courseId] });
      queryClient.invalidateQueries({ queryKey: ['my_gradebook', courseId] });
      if (onCompleted) onCompleted();
    },
    onError: (err: any) => {
      setErrorMessage(err?.response?.data?.detail || 'Failed to submit quiz attempt.');
    },
  });

  // Timer countdown effect
  useEffect(() => {
    if (!activeAttempt || secondsRemaining === null || secondsRemaining <= 0) return;

    const timer = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(timer);
          // Auto submit when time runs out
          if (activeAttempt && !submitAttemptMutation.isPending) {
            submitAttemptMutation.mutate();
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [activeAttempt, secondsRemaining, submitAttemptMutation]);

  // Format seconds to mm:ss
  const formatTime = (totalSec: number) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleSelectOption = (questionId: string, optionId: string) => {
    setSelectedAnswers((prev) => ({
      ...prev,
      [questionId]: optionId,
    }));
  };

  const answeredCount = Object.keys(selectedAnswers).length;
  const progressPercent = totalQuestions > 0 ? (answeredCount / totalQuestions) * 100 : 0;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in overflow-y-auto">
      <div className="bg-white rounded-3xl border border-slate-200/80 shadow-2xl w-full max-w-3xl my-8 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Top Bar */}
        <div className="px-6 py-4 bg-gradient-to-r from-purple-700 to-indigo-700 text-white flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-xl bg-white/10 backdrop-blur flex items-center justify-center border border-white/20">
              <HelpCircle className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="text-[11px] font-semibold text-purple-200 uppercase tracking-wider block">
                Online Interactive Assessment
              </span>
              <h2 className="text-lg font-bold leading-tight truncate max-w-md">
                {quiz?.title || 'Interactive Quiz'}
              </h2>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-xl hover:bg-white/10 text-white/80 hover:text-white transition"
            title="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {/* Error Banner */}
          {errorMessage && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl flex items-start space-x-3 text-rose-800 text-sm">
              <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <span className="font-semibold">Notice:</span> {errorMessage}
              </div>
              <button onClick={() => setErrorMessage(null)} className="text-rose-500 hover:text-rose-700">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* STATE 1: Loading Quiz Data */}
          {isLoadingQuiz && (
            <div className="py-16 text-center space-y-4">
              <div className="w-10 h-10 border-4 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-sm font-medium text-slate-500">Loading test questions & environment...</p>
            </div>
          )}

          {/* STATE 2: Quiz Error */}
          {isQuizError && (
            <div className="py-12 text-center space-y-3">
              <AlertCircle className="w-10 h-10 text-rose-500 mx-auto" />
              <h3 className="text-base font-bold text-slate-800">Unable to Load Quiz</h3>
              <p className="text-sm text-slate-500 max-w-md mx-auto">
                {(quizError as any)?.response?.data?.detail || 'This quiz is currently unavailable or unpublished.'}
              </p>
            </div>
          )}

          {/* STATE 3: Ready to Start Screen (No active attempt & Not viewing result) */}
          {!isLoadingQuiz && !activeAttempt && !submissionResult && quiz && (
            <div className="space-y-6">
              {/* Quiz Overview Card */}
              <div className="bg-slate-50 rounded-2xl p-6 border border-slate-100 space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-xs font-bold uppercase tracking-wider">
                    {totalQuestions} Questions
                  </span>
                  <span className="px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full text-xs font-bold">
                    Max Score: {quiz.max_score} pts
                  </span>
                  {quiz.time_limit_minutes ? (
                    <span className="px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-xs font-bold flex items-center">
                      <Clock className="w-3.5 h-3.5 mr-1" />
                      {quiz.time_limit_minutes} Minutes
                    </span>
                  ) : (
                    <span className="px-3 py-1 bg-slate-200 text-slate-700 rounded-full text-xs font-bold">
                      Untimed
                    </span>
                  )}
                  <span className="px-3 py-1 bg-emerald-100 text-emerald-800 rounded-full text-xs font-bold">
                    Attempts: {attemptsUsed} / {maxAttempts}
                  </span>
                </div>

                <p className="text-slate-600 text-sm leading-relaxed">
                  {quiz.description || 'Test your knowledge on this module. Immediate scoring upon submission.'}
                </p>
              </div>

              {/* Past Attempts History */}
              {submittedAttempts.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Your Previous Attempts
                  </h4>
                  <div className="divide-y divide-slate-100 border border-slate-200/80 rounded-2xl overflow-hidden">
                    {submittedAttempts.map((att, idx) => (
                      <div key={att.id} className="p-3.5 bg-white flex items-center justify-between text-sm">
                        <div className="flex items-center space-x-2.5">
                          <span className="w-6 h-6 rounded-full bg-slate-100 text-slate-600 font-bold text-xs flex items-center justify-center">
                            #{idx + 1}
                          </span>
                          <span className="text-xs text-slate-500">
                            Completed {att.completed_at ? new Date(att.completed_at).toLocaleString() : 'N/A'}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className="font-extrabold text-indigo-600 text-base">
                            {att.score?.toFixed(1)} / {att.max_score}
                          </span>
                          <span className="text-xs text-slate-400">pts</span>
                        </div>
                      </div>
                    ))}
                  </div>

                  {bestScore !== null && (
                    <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between text-xs font-semibold text-emerald-800">
                      <span className="flex items-center">
                        <Award className="w-4 h-4 mr-1.5 text-emerald-600" />
                        Best Grade Recorded in Gradebook:
                      </span>
                      <span className="text-sm font-bold">{bestScore.toFixed(1)} pts</span>
                    </div>
                  )}
                </div>
              )}

              {/* Action Buttons */}
              <div className="pt-2 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-sm rounded-xl transition"
                >
                  Cancel
                </button>

                {hasRemainingAttempts ? (
                  <button
                    type="button"
                    onClick={() => startAttemptMutation.mutate()}
                    disabled={startAttemptMutation.isPending || totalQuestions === 0}
                    className="inline-flex items-center px-6 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold text-sm rounded-xl shadow-md transition disabled:opacity-60"
                  >
                    {startAttemptMutation.isPending ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                        Starting...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4 mr-1.5" />
                        {submittedAttempts.length > 0 ? 'Retake Quiz' : 'Begin Quiz Now'}
                      </>
                    )}
                  </button>
                ) : (
                  <div className="px-4 py-2.5 bg-slate-100 text-slate-500 text-xs font-semibold rounded-xl">
                    Maximum attempts completed
                  </div>
                )}
              </div>
            </div>
          )}

          {/* STATE 4: In-Progress Quiz Test Runner */}
          {activeAttempt && currentQuestion && (
            <div className="space-y-6">
              {/* Progress & Live Timer Bar */}
              <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/80 flex flex-wrap items-center justify-between gap-4">
                <div className="space-y-1">
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                    Question {currentQuestionIndex + 1} of {totalQuestions}
                  </span>
                  <div className="w-48 sm:w-64 h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-indigo-600 transition-all duration-300"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <span className="text-xs text-slate-500 font-medium">
                    Answered {answeredCount}/{totalQuestions}
                  </span>

                  {secondsRemaining !== null && (
                    <div
                      className={`px-3 py-1.5 rounded-xl font-mono text-xs font-bold flex items-center border ${
                        secondsRemaining < 120
                          ? 'bg-rose-100 text-rose-700 border-rose-300 animate-pulse'
                          : 'bg-white text-slate-700 border-slate-200'
                      }`}
                    >
                      <Clock className="w-3.5 h-3.5 mr-1.5" />
                      {formatTime(secondsRemaining)}
                    </div>
                  )}
                </div>
              </div>

              {/* Question Card */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-5">
                <div className="flex items-start justify-between gap-4">
                  <h3 className="text-base sm:text-lg font-bold text-slate-900 leading-snug">
                    {currentQuestion.text}
                  </h3>
                  <span className="px-2.5 py-1 bg-purple-50 text-purple-700 rounded-lg text-xs font-semibold flex-shrink-0 border border-purple-100">
                    {currentQuestion.points} {currentQuestion.points === 1 ? 'pt' : 'pts'}
                  </span>
                </div>

                {/* Options List */}
                <div className="space-y-2.5">
                  {(currentQuestion.options || []).map((opt, optIdx) => {
                    const optId = opt.id || String(optIdx);
                    const isSelected = selectedAnswers[currentQuestion.id || ''] === optId;

                    return (
                      <button
                        key={optId}
                        type="button"
                        onClick={() => handleSelectOption(currentQuestion.id || '', optId)}
                        className={`w-full text-left p-4 rounded-xl border transition-all flex items-center space-x-3 ${
                          isSelected
                            ? 'bg-purple-50/70 border-purple-500 ring-2 ring-purple-500/20 text-purple-950 font-medium shadow-sm'
                            : 'bg-slate-50/60 hover:bg-slate-100/70 border-slate-200 text-slate-700'
                        }`}
                      >
                        <div
                          className={`w-5 h-5 rounded-full border flex items-center justify-center flex-shrink-0 transition ${
                            isSelected
                              ? 'border-purple-600 bg-purple-600 text-white'
                              : 'border-slate-300 bg-white'
                          }`}
                        >
                          {isSelected && <div className="w-2 h-2 rounded-full bg-white" />}
                        </div>
                        <span className="text-sm leading-relaxed flex-1">{opt.text}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Navigation & Submit Bar */}
              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={() => setCurrentQuestionIndex((prev) => Math.max(0, prev - 1))}
                  disabled={currentQuestionIndex === 0}
                  className="inline-flex items-center px-4 py-2 bg-slate-100 hover:bg-slate-200 disabled:opacity-40 text-slate-700 font-semibold text-xs rounded-xl transition"
                >
                  <ChevronLeft className="w-4 h-4 mr-1" />
                  Previous
                </button>

                <div className="flex items-center space-x-2">
                  {currentQuestionIndex < totalQuestions - 1 ? (
                    <button
                      type="button"
                      onClick={() => setCurrentQuestionIndex((prev) => Math.min(totalQuestions - 1, prev + 1))}
                      className="inline-flex items-center px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs rounded-xl transition"
                    >
                      Next
                      <ChevronRight className="w-4 h-4 ml-1" />
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmSubmitOpen(true)}
                      className="inline-flex items-center px-5 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white font-bold text-xs rounded-xl shadow-md transition"
                    >
                      <Send className="w-3.5 h-3.5 mr-1.5" />
                      Submit Exam
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* STATE 5: Post-Submission Results Screen */}
          {submissionResult && (
            <div className="text-center py-6 space-y-6 animate-scale-up">
              <div className="w-20 h-20 bg-gradient-to-tr from-emerald-500 to-teal-400 text-white rounded-3xl mx-auto flex items-center justify-center shadow-lg shadow-emerald-500/20">
                <CheckCircle2 className="w-10 h-10" />
              </div>

              <div className="space-y-1">
                <span className="text-xs font-bold text-emerald-600 uppercase tracking-wider">
                  Exam Completed & Auto-Graded
                </span>
                <h3 className="text-2xl font-extrabold text-slate-900">
                  Great job completing the quiz!
                </h3>
                <p className="text-xs text-slate-500">
                  Your final grade has been synchronized into the course Gradebook.
                </p>
              </div>

              {/* Score Display Card */}
              <div className="max-w-sm mx-auto bg-slate-50 rounded-2xl p-6 border border-slate-200/80 shadow-sm space-y-3">
                <div className="flex items-baseline justify-center space-x-2">
                  <span className="text-5xl font-black text-indigo-600 tracking-tight">
                    {submissionResult.score?.toFixed(1)}
                  </span>
                  <span className="text-xl font-bold text-slate-400">
                    / {submissionResult.max_score} pts
                  </span>
                </div>

                <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-indigo-600 h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${Math.min(
                        100,
                        ((submissionResult.score ?? 0) / (submissionResult.max_score || 100)) * 100
                      )}%`,
                    }}
                  />
                </div>

                {submissionResult.earned_points !== undefined && (
                  <p className="text-xs text-slate-500 font-medium">
                    Points: {submissionResult.earned_points} of {submissionResult.total_possible_points} questions correct
                  </p>
                )}
              </div>

              {/* Action Buttons */}
              <div className="pt-4 flex justify-center space-x-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-6 py-2.5 bg-slate-900 hover:bg-slate-800 text-white font-bold text-sm rounded-xl shadow transition"
                >
                  Done
                </button>

                {hasRemainingAttempts && (
                  <button
                    type="button"
                    onClick={() => {
                      setSubmissionResult(null);
                      startAttemptMutation.mutate();
                    }}
                    className="inline-flex items-center px-5 py-2.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 font-semibold text-sm rounded-xl transition"
                  >
                    <RotateCcw className="w-4 h-4 mr-1.5" />
                    Try Again
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Confirmation Submit Dialog */}
      {confirmSubmitOpen && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-2xl border border-slate-200 space-y-4">
            <h4 className="text-base font-bold text-slate-900">Confirm Exam Submission?</h4>
            <p className="text-sm text-slate-600">
              You have answered {answeredCount} of {totalQuestions} questions. Once submitted, your score will be calculated and finalized.
            </p>
            <div className="flex justify-end space-x-2.5 pt-2">
              <button
                type="button"
                onClick={() => setConfirmSubmitOpen(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl"
              >
                Continue Quiz
              </button>
              <button
                type="button"
                onClick={() => submitAttemptMutation.mutate()}
                disabled={submitAttemptMutation.isPending}
                className="inline-flex items-center px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow"
              >
                {submitAttemptMutation.isPending ? 'Submitting...' : 'Yes, Submit Now'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
