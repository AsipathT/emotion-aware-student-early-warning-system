import React from 'react';
import { useParams } from 'react-router-dom';

export const GradebookPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();

  // Mock gradebook data
  const grades = [
    { student: 'Alice Tan', id: 'STU001', asg1: 85, asg2: 90, quiz1: 88, total: 87.6 },
    { student: 'Bob Smith', id: 'STU002', asg1: 45, asg2: 50, quiz1: 40, total: 45.0 },
    { student: 'Charlie Davis', id: 'STU003', asg1: 95, asg2: 100, quiz1: 90, total: 95.0 },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Course Gradebook</h1>
          <p className="text-gray-500 mt-1">Feature 12: Consolidated grades for all assignments and quizzes.</p>
        </div>
        <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 transition">
          Export Grades
        </button>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 text-gray-500 text-sm">
                <th className="p-4 font-medium border-b border-gray-200">Student ID</th>
                <th className="p-4 font-medium border-b border-gray-200">Name</th>
                <th className="p-4 font-medium text-right border-b border-gray-200">Assignment 1</th>
                <th className="p-4 font-medium text-right border-b border-gray-200">Assignment 2</th>
                <th className="p-4 font-medium text-right border-b border-gray-200">Midterm Quiz</th>
                <th className="p-4 font-medium text-right border-b border-gray-200 text-indigo-700">Total Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {grades.map((row, idx) => (
                <tr key={idx} className="hover:bg-gray-50 transition-colors">
                  <td className="p-4 text-sm text-gray-600 font-mono">{row.id}</td>
                  <td className="p-4 text-sm text-gray-900 font-medium">{row.student}</td>
                  <td className="p-4 text-sm text-gray-700 text-right">{row.asg1} / 100</td>
                  <td className="p-4 text-sm text-gray-700 text-right">{row.asg2} / 100</td>
                  <td className="p-4 text-sm text-gray-700 text-right">{row.quiz1} / 100</td>
                  <td className="p-4 text-sm font-bold text-gray-900 text-right">{row.total}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
