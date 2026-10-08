import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { analyticsApi, RiskScore } from '../api/analytics';
import { TrajectoryChart } from '../components/dashboard/TrajectoryChart';

export const CourseAnalyticsPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const [selectedStudentId, setSelectedStudentId] = useState<string>('');

  const { data: riskScores = [], isLoading: isLoadingRisk } = useQuery({
    queryKey: ['course_risk', courseId],
    queryFn: () => analyticsApi.getCourseRisk(courseId!),
    enabled: !!courseId,
  });

  const { data: trajectoryData = [], isLoading: isLoadingTrajectory } = useQuery({
    queryKey: ['student_trajectory', courseId, selectedStudentId],
    queryFn: () => analyticsApi.getStudentTrajectory(courseId!, selectedStudentId),
    enabled: !!courseId && !!selectedStudentId,
  });

  const handleGenerateSynthetic = async () => {
    if (courseId) {
      await analyticsApi.triggerSyntheticData(courseId);
      alert('Synthetic data generated! Please refresh.');
    }
  };

  const handleExportData = () => {
    if (courseId) {
      window.open(`http://localhost:8000/api/v1/analytics/courses/${courseId}/export`, '_blank');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <div className="flex justify-between items-center bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Course Analytics</h1>
          <p className="text-gray-500 text-sm mt-1">Monitor risk scores and student trajectories.</p>
        </div>
        <div className="space-x-4">
          <button 
            onClick={handleGenerateSynthetic}
            className="px-4 py-2 bg-indigo-50 text-indigo-700 rounded-lg text-sm font-semibold hover:bg-indigo-100 transition"
          >
            Generate Synthetic Data
          </button>
          <button 
            onClick={handleExportData}
            className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold hover:bg-emerald-700 transition shadow-sm"
          >
            Export Training CSV
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Risk Scores Table */}
        <div className="lg:col-span-1 bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col h-[600px]">
          <div className="p-4 border-b border-gray-100 bg-gray-50">
            <h2 className="font-semibold text-gray-900">Enrolled Students Risk</h2>
          </div>
          <div className="overflow-y-auto flex-1 p-2 space-y-2">
            {isLoadingRisk ? (
              <p className="text-center text-gray-500 py-4">Loading...</p>
            ) : riskScores.length === 0 ? (
              <p className="text-center text-gray-500 py-4 text-sm">No risk data. Try generating synthetic data.</p>
            ) : (
              riskScores.map((risk: RiskScore) => (
                <div 
                  key={risk.id}
                  onClick={() => setSelectedStudentId(risk.student_id)}
                  className={`p-3 rounded-lg border cursor-pointer transition ${
                    selectedStudentId === risk.student_id ? 'border-indigo-500 bg-indigo-50' : 'border-gray-100 hover:border-gray-300'
                  }`}
                >
                  <div className="flex justify-between items-center">
                    <span className="font-mono text-xs text-gray-600">{risk.student_id.substring(0, 8)}</span>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                      risk.risk_tier === 'High' ? 'bg-red-100 text-red-700' :
                      risk.risk_tier === 'Medium' ? 'bg-orange-100 text-orange-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      {risk.risk_tier} ({risk.risk_score.toFixed(0)})
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Trajectory View */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col">
          <h2 className="text-lg font-bold text-gray-900 mb-4">Student Trajectory Map</h2>
          {!selectedStudentId ? (
            <div className="flex-1 flex items-center justify-center border-2 border-dashed border-gray-200 rounded-xl bg-gray-50 text-gray-400">
              Select a student from the list to view their trajectory.
            </div>
          ) : isLoadingTrajectory ? (
            <div className="flex-1 flex items-center justify-center text-gray-500">Loading trajectory...</div>
          ) : (
            <div className="flex-1">
              <TrajectoryChart data={trajectoryData} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
