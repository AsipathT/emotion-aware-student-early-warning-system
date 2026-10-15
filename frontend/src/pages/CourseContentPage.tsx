import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { contentApi, assessmentApi } from '../api/assessment';
import { QuizPlayerModal } from '../components/quiz/QuizPlayerModal';
import {
  ArrowLeft,
  BookOpen,
  FileText,
  HelpCircle,
  PlayCircle,
  Layers,
  Play,
} from 'lucide-react';

export const CourseContentPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const [selectedQuizId, setSelectedQuizId] = useState<string | null>(null);

  const { data: modules = [], isLoading: isLoadingModules } = useQuery({
    queryKey: ['course_modules', courseId],
    queryFn: () => contentApi.getModules(courseId!),
    enabled: !!courseId,
  });

  const { data: assignments = [], isLoading: isLoadingAssignments } = useQuery({
    queryKey: ['course_assignments', courseId],
    queryFn: () => assessmentApi.getAssignments(courseId!),
    enabled: !!courseId,
  });

  const { data: quizzes = [], isLoading: isLoadingQuizzes } = useQuery({
    queryKey: ['course_quizzes', courseId],
    queryFn: () => assessmentApi.getQuizzes(courseId!),
    enabled: !!courseId,
  });

  if (isLoadingModules || isLoadingAssignments || isLoadingQuizzes) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center">
        <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-sm font-medium text-slate-500">Loading course curriculum & content...</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
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

      {/* Header Banner */}
      <div className="bg-white p-6 sm:p-8 rounded-2xl border border-slate-200/80 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-indigo-600 uppercase tracking-wider mb-1">
            <Layers className="w-4 h-4" />
            <span>Curriculum Modules & Assessments</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Course Content Pages
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            Access weekly learning modules, interactive video lectures, and graded evaluations.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to={`/courses/${courseId}/video`}
            className="inline-flex items-center px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm rounded-xl shadow-sm transition"
          >
            <PlayCircle className="w-4 h-4 mr-2" />
            Watch Lecture Videos
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Cols: Learning Modules */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900 flex items-center">
              <BookOpen className="w-5 h-5 text-indigo-600 mr-2" />
              Syllabus Modules ({modules.length})
            </h2>
          </div>

          {modules.length === 0 ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center text-slate-500 text-sm">
              No modules published yet for this course.
            </div>
          ) : (
            <div className="space-y-4">
              {modules.map((mod: any) => (
                <div
                  key={mod.id}
                  className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm hover:border-indigo-300 transition"
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="inline-block px-2.5 py-1 bg-indigo-50 text-indigo-700 rounded-lg text-xs font-bold font-mono">
                      Module {mod.sequence_order || 1}
                    </span>
                    {mod.reading_time_minutes && (
                      <span className="text-xs text-slate-400">
                        {mod.reading_time_minutes} mins reading
                      </span>
                    )}
                  </div>
                  <h3 className="text-lg font-bold text-slate-900 mb-2">{mod.title}</h3>
                  {mod.topics && Array.isArray(mod.topics) && mod.topics.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {mod.topics.map((t: string, i: number) => (
                        <span key={i} className="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded-md">
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                  {mod.notes && (
                    <p className="text-sm text-slate-600 mt-3 pt-3 border-t border-slate-100">
                      {mod.notes}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right 1 Col: Quick Assessments Preview */}
        <div className="space-y-6">
          {/* Assignments */}
          <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-slate-900 flex items-center">
                <FileText className="w-4 h-4 text-indigo-600 mr-2" />
                Assignments ({assignments.length})
              </h2>
              <Link
                to={`/courses/${courseId}/assignments`}
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
              >
                View all &rarr;
              </Link>
            </div>

            {assignments.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-4">No assignments scheduled.</p>
            ) : (
              <div className="space-y-2.5">
                {assignments.slice(0, 4).map(a => (
                  <Link
                    key={a.id}
                    to={`/courses/${courseId}/assignments/${a.id}`}
                    className="flex justify-between items-center p-3 bg-slate-50 hover:bg-indigo-50/50 rounded-xl border border-slate-100 text-sm transition"
                  >
                    <span className="font-medium text-slate-800 truncate mr-2">{a.title}</span>
                    <span className="text-xs font-bold text-indigo-600 flex-shrink-0">
                      {a.max_score} pts
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Quizzes */}
          <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-slate-900 flex items-center">
                <HelpCircle className="w-4 h-4 text-purple-600 mr-2" />
                Quizzes ({quizzes.length})
              </h2>
              <Link
                to={`/courses/${courseId}/quizzes`}
                className="text-xs font-semibold text-purple-600 hover:text-purple-800"
              >
                View all &rarr;
              </Link>
            </div>

            {quizzes.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-4">No quizzes available.</p>
            ) : (
              <div className="space-y-2.5">
                {quizzes.slice(0, 4).map((q) => (
                  <button
                    key={q.id}
                    type="button"
                    onClick={() => setSelectedQuizId(q.id)}
                    className="w-full flex justify-between items-center p-3 bg-purple-50/40 hover:bg-purple-100/60 rounded-xl border border-purple-100/80 text-sm transition text-left group"
                  >
                    <div className="flex items-center space-x-2 mr-2 truncate">
                      <Play className="w-3.5 h-3.5 text-purple-600 flex-shrink-0 group-hover:scale-110 transition" />
                      <span className="font-medium text-slate-800 truncate">{q.title}</span>
                    </div>
                    <span className="text-xs text-purple-700 bg-purple-100 px-2 py-0.5 rounded-md font-bold flex-shrink-0">
                      {q.max_score || 100} pts
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Interactive Quiz Modal */}
      {selectedQuizId && (
        <QuizPlayerModal
          courseId={courseId!}
          quizId={selectedQuizId}
          isOpen={!!selectedQuizId}
          onClose={() => setSelectedQuizId(null)}
        />
      )}
    </div>
  );
};
