import React, { useEffect, useState } from 'react';
import {
  KeyRound,
  ShieldAlert,
  AlertTriangle,
  FileCheck2,
  Sparkles,
  RefreshCw,
  Info,
} from 'lucide-react';
import { PageHeader } from '../../components/admin/PageHeader';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import { useAuth } from '../../hooks/useAuth';
import {
  adminApi,
  AdminIdentityRevealResponse,
  AdminRevealHistoryItem,
  AdminScrubTestResponse,
} from '../../api/admin';

export const AdminPrivacyPage: React.FC = () => {
  const { user } = useAuth();
  const isAuditor = user?.role === 'auditor';

  // Break-glass form
  const [pid, setPid] = useState('');
  const [justification, setJustification] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [revealLoading, setRevealLoading] = useState(false);
  const [revealedData, setRevealedData] = useState<AdminIdentityRevealResponse | null>(null);
  const [revealError, setRevealError] = useState<string | null>(null);

  // Reveal History
  const [history, setHistory] = useState<AdminRevealHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  // Scrubber sandbox
  const [scrubInput, setScrubInput] = useState('');
  const [scrubLoading, setScrubLoading] = useState(false);
  const [scrubResult, setScrubResult] = useState<AdminScrubTestResponse | null>(null);

  const fetchHistory = async () => {
    try {
      setHistoryLoading(true);
      const res = await adminApi.getRevealHistory({ page: 1, page_size: 20 });
      setHistory(res.items || []);
    } catch (err: any) {
      console.error('Failed to load reveal history', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleRevealSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (justification.trim().length < 10) return;
    setConfirmOpen(true);
  };

  const executeReveal = async () => {
    try {
      setRevealLoading(true);
      setRevealError(null);
      const res = await adminApi.breakglassRevealIdentity({
        pid: pid.trim(),
        justification: justification.trim(),
      });
      setRevealedData(res);
      setConfirmOpen(false);
      setPid('');
      setJustification('');
      await fetchHistory();
    } catch (err: any) {
      setRevealError(err?.response?.data?.detail || 'Failed to reveal identity from vault.');
      setConfirmOpen(false);
    } finally {
      setRevealLoading(false);
    }
  };

  const handleScrubSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scrubInput.trim()) return;
    try {
      setScrubLoading(true);
      const res = await adminApi.testScrubContent({ text: scrubInput });
      setScrubResult(res);
    } catch (err: any) {
      alert('Failed to scrub text: ' + (err?.response?.data?.detail || err.message));
    } finally {
      setScrubLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        title="Privacy & Controlled Reveal"
        description="Break-glass identity re-identification, immutable reveal audit logs, and PII sanitizer tester."
      />

      {/* Break-glass reveal section */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-rose-50 text-rose-600 rounded-lg">
              <KeyRound className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Break-Glass Identity Reveal Tool</h3>
              <p className="text-xs text-slate-500">
                Reveals the real identity corresponding to a Pseudonym ID (PID) from the isolated Identity Vault.
              </p>
            </div>
          </div>
          {isAuditor && (
            <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-full font-medium">
              <ShieldAlert className="w-3.5 h-3.5" /> Auditor: Read-Only
            </span>
          )}
        </div>

        {revealError && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 text-sm">
            {revealError}
          </div>
        )}

        {revealedData && (
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-emerald-800 uppercase tracking-wider flex items-center gap-1">
                <FileCheck2 className="w-4 h-4" /> Identity Revealed (Transient View)
              </span>
              <button
                onClick={() => setRevealedData(null)}
                className="text-xs text-emerald-700 hover:text-emerald-900 font-semibold underline"
              >
                Clear View
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-2 text-sm">
              <div className="p-2 bg-white rounded border border-emerald-100">
                <span className="text-[11px] text-slate-400 block">Pseudonym ID</span>
                <span className="font-mono font-semibold text-slate-800">{revealedData.pid}</span>
              </div>
              <div className="p-2 bg-white rounded border border-emerald-100">
                <span className="text-[11px] text-slate-400 block">Student ID</span>
                <span className="font-semibold text-slate-800">{revealedData.student_id}</span>
              </div>
              <div className="p-2 bg-white rounded border border-emerald-100">
                <span className="text-[11px] text-slate-400 block">Full Name</span>
                <span className="font-semibold text-slate-800">{revealedData.name}</span>
              </div>
              <div className="p-2 bg-white rounded border border-emerald-100">
                <span className="text-[11px] text-slate-400 block">Official Email</span>
                <span className="font-semibold text-slate-800">{revealedData.email}</span>
              </div>
            </div>
            <p className="text-[11px] text-emerald-700 italic pt-1">
              Notice: This identity is transient and will not be logged in audit details or cached in storage.
            </p>
          </div>
        )}

        <form onSubmit={handleRevealSubmit} className="space-y-4 pt-1">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Pseudonym ID (PID) *
              </label>
              <input
                type="text"
                required
                disabled={isAuditor}
                placeholder="STU_1a2b3c4d"
                value={pid}
                onChange={(e) => setPid(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono disabled:bg-slate-100 disabled:text-slate-400"
              />
            </div>
            <div className="md:col-span-2">
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs font-semibold text-slate-700">
                  Justification Reason * (min 10 characters)
                </label>
                <span
                  className={`text-xs ${
                    justification.length < 10 ? 'text-amber-600 font-semibold' : 'text-slate-400'
                  }`}
                >
                  {justification.length}/10 chars min
                </span>
              </div>
              <textarea
                required
                rows={2}
                disabled={isAuditor}
                placeholder="Enter mandatory institutional reason (e.g. Critical welfare risk flag reported by counsellor)..."
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100 disabled:text-slate-400"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
              Every reveal action creates an immutable Feature 7 audit entry with caller ID, timestamp, and justification.
            </span>
            <button
              type="submit"
              disabled={isAuditor || !pid.trim() || justification.trim().length < 10 || revealLoading}
              className={`px-4 py-2 text-xs font-semibold rounded-lg text-white transition ${
                isAuditor || !pid.trim() || justification.trim().length < 10
                  ? 'bg-slate-300 cursor-not-allowed'
                  : 'bg-rose-600 hover:bg-rose-700 shadow-sm'
              }`}
            >
              Reveal Identity
            </button>
          </div>
        </form>
      </div>

      {/* Historical Reveal Audit Log Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Break-Glass Reveal Audit History</h3>
            <p className="text-xs text-slate-500">Historical records of all IDENTITY_REVEAL actions.</p>
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
                <th className="py-3 px-4">Target PID</th>
                <th className="py-3 px-4">Justification Reason</th>
                <th className="py-3 px-4">Outcome</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {historyLoading && history.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-400">
                    Loading reveal audit entries...
                  </td>
                </tr>
              ) : history.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-400">
                    No identity reveal events found in the audit log.
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
                      {item.pid}
                    </td>
                    <td className="py-2.5 px-4 text-slate-700 max-w-sm">
                      {item.reason}
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 uppercase">
                        {item.outcome}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* PII Scrubber Sandbox */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">Interactive PII Scrubber Tester</h3>
            <p className="text-xs text-slate-500">
              Verify redaction of emails, names, phone numbers, and student IDs prior to pipeline ingestion.
            </p>
          </div>
        </div>

        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-blue-800 text-xs flex items-center gap-2">
          <Info className="w-4 h-4 flex-shrink-0 text-blue-600" />
          <span>
            <strong>Sandbox Notice:</strong> Interactive testing tool only. Text submitted here is processed in-memory and is never persisted to database collections or recorded in audit details.
          </span>
        </div>

        <form onSubmit={handleScrubSubmit} className="space-y-3">
          <div>
            <textarea
              rows={3}
              placeholder="Paste sample student text here (e.g. Please contact John Doe at john@student.edu or phone 0771234567 regarding IT20261234)..."
              value={scrubInput}
              onChange={(e) => setScrubInput(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={!scrubInput.trim() || scrubLoading}
              className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition shadow-sm disabled:bg-slate-300"
            >
              {scrubLoading ? 'Scrubbing...' : 'Sanitize Free Text'}
            </button>
          </div>
        </form>

        {scrubResult && (
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3 text-xs">
            <h4 className="font-bold text-slate-800 text-xs">Sanitized Output:</h4>
            <div className="p-3 bg-white border border-slate-200 rounded font-mono text-slate-700 whitespace-pre-wrap">
              {scrubResult.clean_text}
            </div>

            <div>
              <h5 className="font-semibold text-slate-700 mb-1">Redaction Report:</h5>
              <div className="flex flex-wrap gap-2">
                {Object.entries(scrubResult.redaction_report || {}).map(([key, count]) => (
                  <span
                    key={key}
                    className="px-2.5 py-1 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-full font-medium"
                  >
                    {key}: {count}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Confirmation Dialog */}
      <ConfirmDialog
        isOpen={confirmOpen}
        title="Confirm Break-Glass Identity Reveal"
        message={`Are you sure you want to reveal the real student identity for ${pid}? This action is immutable, strictly audited with your administrator identity, and requires institutional justification.`}
        confirmLabel={revealLoading ? 'Revealing...' : 'Yes, Reveal Identity'}
        variant="danger"
        isLoading={revealLoading}
        onConfirm={executeReveal}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
};
