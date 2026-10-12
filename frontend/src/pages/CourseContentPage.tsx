import React from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { contentApi, assessmentApi } from '../api/assessment';

export const CourseContentPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();

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
    return <div className="p-8 text-center text-gray-500">Loading content...</div>;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
        <h1 className="text-2xl font-bold text-gray-900">Course Content & Assessments</h1>
        <p className="text-gray-500 mt-1">Manage modules, assignments, and quizzes.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Modules */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">Learning Modules</h2>
          {modules.length === 0 ? (
            <p className="text-sm text-gray-500">No modules found.</p>
          ) : (
            <div className="space-y-4">
              {modules.map(mod => (
                <div key={mod.id} className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                  <h3 className="font-semibold text-gray-800">Module {mod.sequence_order}: {mod.title}</h3>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Assessments */}
        <div className="space-y-8">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Assignments</h2>
            {assignments.length === 0 ? (
              <p className="text-sm text-gray-500">No assignments found.</p>
            ) : (
              <div className="space-y-3">
                {assignments.map(a => (
                  <div key={a.id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <span className="font-medium text-sm text-gray-800">{a.title}</span>
                    <span className="text-xs text-gray-500">Max: {a.max_score}pts</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Quizzes</h2>
            {quizzes.length === 0 ? (
              <p className="text-sm text-gray-500">No quizzes found.</p>
            ) : (
              <div className="space-y-3">
                {quizzes.map(q => (
                  <div key={q.id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <span className="font-medium text-sm text-gray-800">{q.title}</span>
                    <span className="text-xs text-gray-500">Attempts: {q.max_attempts}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
