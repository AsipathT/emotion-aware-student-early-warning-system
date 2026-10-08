import React from 'react';
import { AlertCircle, TrendingUp, Users } from 'lucide-react';
import { DashboardSummary } from '../../api/analytics';

interface Props {
  summary: DashboardSummary | null;
}

export const RiskScoreCards: React.FC<Props> = ({ summary }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex items-center">
        <div className="p-4 bg-red-50 rounded-lg text-red-600 mr-4">
          <AlertCircle size={24} />
        </div>
        <div>
          <p className="text-sm font-medium text-gray-500">Active High Risk</p>
          <p className="text-2xl font-bold text-gray-900">
            {summary?.active_alerts ?? '-'}
          </p>
        </div>
      </div>
      
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex items-center">
        <div className="p-4 bg-orange-50 rounded-lg text-orange-600 mr-4">
          <TrendingUp size={24} />
        </div>
        <div>
          <p className="text-sm font-medium text-gray-500">Recent Assessments</p>
          <p className="text-2xl font-bold text-gray-900">
            {summary?.recent_risk_scores.length ?? '-'}
          </p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 flex items-center">
        <div className="p-4 bg-blue-50 rounded-lg text-blue-600 mr-4">
          <Users size={24} />
        </div>
        <div>
          <p className="text-sm font-medium text-gray-500">Total Scored</p>
          <p className="text-2xl font-bold text-gray-900">
            {summary?.recent_risk_scores.length ?? '-'}
          </p>
        </div>
      </div>
    </div>
  );
};
