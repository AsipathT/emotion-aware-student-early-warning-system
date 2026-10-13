import React, { useEffect, useState } from 'react';
import {
  Download,
  FileSpreadsheet,
  FileText,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react';
import { PageHeader } from '../../components/admin/PageHeader';
import {
  adminApi,
  AdminExportHistoryItem,
} from '../../api/admin';

export const AdminExportsPage: React.FC = () => {
  const [selectedDataset, setSelectedDataset] = useState('c2_behavior');
  const [selectedFormat, setSelectedFormat] = useState<'csv' | 'json'>('csv');
  const [courseId, setCourseId] = useState('');
  const [weekIndex, setWeekIndex] = useState<string>('');
  const [downloading, setDownloading] = useState(false);
  const [downloadSuccess, setDownloadSuccess] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // History
  const [history, setHistory] = useState<AdminExportHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  const fetchHistory = async () => {
    try {
      setHistoryLoading(true);
      const res = await adminApi.getExportHistory({ page: 1, page_size: 20 });
      setHistory(res.items || []);
    } catch (err: any) {
      console.error('Failed to load export history', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleDownload = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setDownloading(true);
      setDownloadError(null);
      setDownloadSuccess(null);

      const weekNum = weekIndex !== '' ? parseInt(weekIndex, 10) : undefined;
      const blob = await adminApi.downloadAdminExport(
        selectedDataset,
        selectedFormat,
        courseId.trim() || undefined,
        weekNum
      );

      // Trigger browser download
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = selectedFormat === 'csv' ? 'csv' : 'json';
      a.download = `export_${selectedDataset}_${Date.now()}.${ext}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setDownloadSuccess(`Successfully generated and downloaded ${selectedDataset} export.`);
      await fetchHistory();
    } catch (err: any) {
      setDownloadError(err?.response?.data?.detail || 'Failed to download dataset.');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Data Exports"
        description="Export pseudonymized datasets adhering to ethics consent rules, formula sanitization, and audit tracking."
      />

      {/* Export Generator Card */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
            <Download className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">Generate Dataset Export</h3>
            <p className="text-xs text-slate-500">
              Select dataset collection, filters, and output format. Excludes withdrawn students automatically.
            </p>
          </div>
        </div>

        {downloadSuccess && (
          <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-xs">
            {downloadSuccess}
          </div>
        )}
        {downloadError && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 text-xs">
            {downloadError}
          </div>
        )}

        <form onSubmit={handleDownload} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Dataset *</label>
              <select
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="c1_messages">C1 Text Messages</option>
                <option value="c2_behavior">C2 Behavior Weekly Analytics</option>
                <option value="c3_academic">C3 Academic Records</option>
                <option value="c3_affective">C3 Affective Weekly Vectors</option>
                <option value="c3_trajectories">C3 Engagement Trajectories</option>
                <option value="c4_risk">C4 Multimodal Risk Assessments</option>
                <option value="c4_recommendations">C4 Intervention Recommendations</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Course ID (Optional)</label>
              <input
                type="text"
                placeholder="e.g. CS101"
                value={courseId}
                onChange={(e) => setCourseId(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Week Index (Optional)</label>
              <input
                type="number"
                min="0"
                placeholder="e.g. 1"
                value={weekIndex}
                onChange={(e) => setWeekIndex(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Format *</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedFormat('csv')}
                  className={`flex items-center justify-center gap-1.5 py-2 text-xs font-medium rounded-lg border transition ${
                    selectedFormat === 'csv'
                      ? 'bg-indigo-50 border-indigo-500 text-indigo-700'
                      : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <FileSpreadsheet className="w-4 h-4" /> CSV
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedFormat('json')}
                  className={`flex items-center justify-center gap-1.5 py-2 text-xs font-medium rounded-lg border transition ${
                    selectedFormat === 'json'
                      ? 'bg-indigo-50 border-indigo-500 text-indigo-700'
                      : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <FileText className="w-4 h-4" /> JSON
                </button>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-slate-100">
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              Ethics Safeguard: Withdrawn students are excluded automatically. CSV output enforces formula injection sanitization.
            </span>
            <button
              type="submit"
              disabled={downloading}
              className="flex items-center gap-1.5 px-5 py-2 text-xs font-semibold rounded-lg text-white bg-indigo-600 hover:bg-indigo-700 transition shadow-sm disabled:bg-slate-300"
            >
              <Download className="w-4 h-4" />
              {downloading ? 'Generating...' : 'Download Export'}
            </button>
          </div>
        </form>
      </div>

      {/* Export History Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Export Audit History</h3>
            <p className="text-xs text-slate-500">Historical records of all EXPORT_GENERATED audit events.</p>
          </div>
          <button
            onClick={fetchHistory}
            className="p-1.5 text-slate-500 hover:text-slate-800 rounded transition border border-slate-200"
            title="Refresh history"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${historyLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 text-xs uppercase tracking-wider font-semibold">
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Caller / Role</th>
                <th className="py-3 px-4">Dataset</th>
                <th className="py-3 px-4">Format</th>
                <th className="py-3 px-4">Rows Exported</th>
                <th className="py-3 px-4">Filters Applied</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {historyLoading && history.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-400">
                    Loading export history...
                  </td>
                </tr>
              ) : history.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-400">
                    No data export events recorded yet.
                  </td>
                </tr>
              ) : (
                history.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50">
                    <td className="py-2.5 px-4 text-slate-500">
                      {new Date(item.timestamp).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-4 font-medium text-slate-800">
                      <div>{item.actor_id}</div>
                      <div className="text-[11px] text-slate-400 capitalize">{item.actor_role}</div>
                    </td>
                    <td className="py-2.5 px-4 font-mono font-semibold text-indigo-700">
                      {item.dataset}
                    </td>
                    <td className="py-2.5 px-4 uppercase font-semibold text-slate-600">
                      {item.format}
                    </td>
                    <td className="py-2.5 px-4 font-semibold text-slate-800">
                      {item.row_count?.toLocaleString()}
                    </td>
                    <td className="py-2.5 px-4 text-slate-500">
                      {Object.keys(item.filters || {}).length > 0 ? (
                        <div className="flex gap-1 flex-wrap">
                          {Object.entries(item.filters).map(([k, v]) => (
                            <span key={k} className="px-1.5 py-0.5 bg-slate-100 rounded text-[10px]">
                              {k}: {String(v)}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span>None</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
