import React from 'react';
import { DashboardSummary } from '../../api/analytics';

interface Props {
  summary: DashboardSummary | null;
}

export const ActiveAlertsTable: React.FC<Props> = ({ summary }) => {
  if (!summary) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <div className="p-6 border-b border-gray-100">
        <h2 className="text-lg font-semibold text-gray-900">Recent Risk Assessments</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-50 text-gray-500 text-sm">
              <th className="p-4 font-medium">Student ID</th>
              <th className="p-4 font-medium">Risk Score</th>
              <th className="p-4 font-medium">Tier</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {summary.recent_risk_scores.map((risk, idx) => (
              <tr key={idx} className="hover:bg-gray-50 transition-colors">
                <td className="p-4 text-sm text-gray-900 font-medium">
                  {risk.student_id.substring(0, 8)}...
                </td>
                <td className="p-4 text-sm text-gray-600">
                  {(risk.score).toFixed(1)}
                </td>
                <td className="p-4">
                  <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                    risk.tier === 'High' ? 'bg-red-100 text-red-700' :
                    risk.tier === 'Medium' ? 'bg-orange-100 text-orange-700' :
                    'bg-green-100 text-green-700'
                  }`}>
                    {risk.tier}
                  </span>
                </td>
              </tr>
            ))}
            {summary.recent_risk_scores.length === 0 && (
              <tr>
                <td colSpan={3} className="p-4 text-center text-gray-500 text-sm">
                  No recent risk scores available.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
