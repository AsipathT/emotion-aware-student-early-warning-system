import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { TrajectoryLabel } from '../../api/analytics';

interface Props {
  data: TrajectoryLabel[];
}

export const TrajectoryChart: React.FC<Props> = ({ data }) => {
  // Format data for Recharts
  const chartData = data.map(item => ({
    name: `Week ${item.week_index}`,
    Stable: (item.p_stable || 0) * 100,
    Improving: (item.p_improving || 0) * 100,
    Declining: (item.p_declining || 0) * 100,
    Volatile: (item.p_volatile || 0) * 100,
  }));

  if (data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center bg-gray-50 rounded-lg border border-gray-100 text-gray-500">
        No trajectory data available.
      </div>
    );
  }

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={chartData}
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
          <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#6B7280', fontSize: 12}} dy={10} />
          <YAxis axisLine={false} tickLine={false} tick={{fill: '#6B7280', fontSize: 12}} dx={-10} domain={[0, 100]} />
          <Tooltip 
            contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
          />
          <Legend wrapperStyle={{ paddingTop: '20px' }} />
          <Line type="monotone" dataKey="Stable" stroke="#3B82F6" strokeWidth={2} dot={{r: 4}} activeDot={{r: 6}} />
          <Line type="monotone" dataKey="Improving" stroke="#10B981" strokeWidth={2} dot={{r: 4}} activeDot={{r: 6}} />
          <Line type="monotone" dataKey="Declining" stroke="#EF4444" strokeWidth={2} dot={{r: 4}} activeDot={{r: 6}} />
          <Line type="monotone" dataKey="Volatile" stroke="#F59E0B" strokeWidth={2} dot={{r: 4}} activeDot={{r: 6}} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};
