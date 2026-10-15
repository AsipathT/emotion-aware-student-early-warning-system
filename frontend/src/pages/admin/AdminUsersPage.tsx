import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  adminApi,
  AdminUserResponse,
  AdminPaginatedUsersResponse,
  AdminUserCreatePayload,
  AdminUserDetailResponse,
} from '../../api/admin';
import { UserRole } from '../../api/auth';
import { useAuth } from '../../hooks/useAuth';
import { PageHeader } from '../../components/admin/PageHeader';
import { StatusBadge } from '../../components/admin/StatusBadge';
import { ConfirmDialog } from '../../components/admin/ConfirmDialog';
import {
  Users,
  Search,
  UserPlus,
  Eye,
  Shield,
  ToggleLeft,
  ToggleRight,
  AlertCircle,
  CheckCircle2,
  X,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  BookOpen,
  Scale,
  Copy,
  Check,
} from 'lucide-react';

export const AdminUsersPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { user: currentAdmin } = useAuth();

  // Filter & Pagination state
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const sortBy = 'created_at';
  const sortOrder: 'asc' | 'desc' = 'desc';

  // UI state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [copiedPid, setCopiedPid] = useState(false);

  // Confirmation dialog state
  const [confirmState, setConfirmState] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
    variant: 'danger' | 'warning' | 'primary';
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
    variant: 'danger',
  });

  // Feedback notifications
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);

  // Form state for creating a user
  const [createForm, setCreateForm] = useState<AdminUserCreatePayload>({
    full_name: '',
    email: '',
    password: '',
    role: 'student',
    department: '',
    bio: '',
  });

  // 1. Fetch Paginated Users
  const {
    data: usersData,
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useQuery<AdminPaginatedUsersResponse>({
    queryKey: [
      'admin',
      'users',
      { page, pageSize, q: searchQuery, role: roleFilter, status: statusFilter, sortBy, sortOrder },
    ],
    queryFn: () =>
      adminApi.getAdminUsersPaginated({
        page,
        page_size: pageSize,
        q: searchQuery,
        role: roleFilter,
        status: statusFilter,
        sort_by: sortBy,
        sort_order: sortOrder,
      }),
  });

  // 2. Fetch User Detail (Drawer)
  const {
    data: userDetail,
    isLoading: isLoadingDetail,
  } = useQuery<AdminUserDetailResponse>({
    queryKey: ['admin', 'users', 'detail', selectedUserId],
    queryFn: () => adminApi.getAdminUserDetail(selectedUserId!),
    enabled: !!selectedUserId,
  });

  // 3. Mutation: Create User
  const createMutation = useMutation({
    mutationFn: (payload: AdminUserCreatePayload) => adminApi.createAdminUser(payload),
    onSuccess: (newUser) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'overview'] });
      setIsCreateModalOpen(false);
      setCreateForm({
        full_name: '',
        email: '',
        password: '',
        role: 'student',
        department: '',
        bio: '',
      });
      setFeedback({
        type: 'success',
        message: `Account for "${newUser.full_name}" (${newUser.role}) was created successfully.`,
      });
      setTimeout(() => setFeedback(null), 5000);
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail || 'Failed to create user account.';
      setFeedback({ type: 'error', message: detail });
    },
  });

  // 4. Mutation: Update Status
  const statusMutation = useMutation({
    mutationFn: ({ userId, isActive }: { userId: string; isActive: boolean }) =>
      adminApi.updateUserStatus(userId, isActive),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'overview'] });
      if (selectedUserId === updated.id) {
        queryClient.invalidateQueries({ queryKey: ['admin', 'users', 'detail', updated.id] });
      }
      setConfirmState((prev) => ({ ...prev, isOpen: false }));
      setFeedback({
        type: 'success',
        message: `Account for "${updated.full_name}" is now ${updated.is_active ? 'active' : 'suspended'}.`,
      });
      setTimeout(() => setFeedback(null), 4000);
    },
    onError: (err: any) => {
      setConfirmState((prev) => ({ ...prev, isOpen: false }));
      const detail = err.response?.data?.detail || 'Failed to update user status.';
      setFeedback({ type: 'error', message: detail });
    },
  });

  // 5. Mutation: Update Role
  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) =>
      adminApi.updateUserRole(userId, role),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'overview'] });
      if (selectedUserId === updated.id) {
        queryClient.invalidateQueries({ queryKey: ['admin', 'users', 'detail', updated.id] });
      }
      setConfirmState((prev) => ({ ...prev, isOpen: false }));
      setFeedback({
        type: 'success',
        message: `Role for "${updated.full_name}" updated to "${updated.role.toUpperCase()}".`,
      });
      setTimeout(() => setFeedback(null), 4000);
    },
    onError: (err: any) => {
      setConfirmState((prev) => ({ ...prev, isOpen: false }));
      const detail = err.response?.data?.detail || 'Failed to update user role.';
      setFeedback({ type: 'error', message: detail });
    },
  });

  // Handle status toggle confirmation
  const handleToggleStatus = (targetUser: AdminUserResponse) => {
    const isSuspending = targetUser.is_active;
    setConfirmState({
      isOpen: true,
      title: isSuspending ? 'Suspend Account' : 'Reactivate Account',
      message: isSuspending
        ? `Are you sure you want to suspend "${targetUser.full_name}"? Suspended accounts cannot log in to the LMS.`
        : `Are you sure you want to reactivate "${targetUser.full_name}"?`,
      variant: isSuspending ? 'danger' : 'primary',
      onConfirm: () =>
        statusMutation.mutate({ userId: targetUser.id, isActive: !targetUser.is_active }),
    });
  };

  // Handle role change confirmation
  const handleChangeRole = (targetUser: AdminUserResponse, newRole: UserRole) => {
    setConfirmState({
      isOpen: true,
      title: 'Update User Role',
      message: `Are you sure you want to change the role of "${targetUser.full_name}" from ${targetUser.role.toUpperCase()} to ${newRole.toUpperCase()}? This modifies their system permissions immediately.`,
      variant: 'warning',
      onConfirm: () => roleMutation.mutate({ userId: targetUser.id, role: newRole }),
    });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedPid(true);
    setTimeout(() => setCopiedPid(false), 2000);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="User Management"
        description="Provision accounts, inspect deterministic student pseudonyms, and manage roles with automated compliance auditing."
        actions={
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium shadow-sm transition"
          >
            <UserPlus className="w-4 h-4" />
            <span>Create User</span>
          </button>
        }
      />

      {/* Action Notification Alert */}
      {feedback && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between ${
            feedback.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          <div className="flex items-center space-x-2">
            {feedback.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
            )}
            <span className="text-sm font-medium">{feedback.message}</span>
          </div>
          <button
            onClick={() => setFeedback(null)}
            className="text-slate-400 hover:text-slate-600 p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Search & Filters Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search name, email, or PID..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          {/* Role Filter */}
          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-500 font-medium">Role:</span>
            <select
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value);
                setPage(1);
              }}
              className="py-1.5 px-3 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">All Roles</option>
              <option value="student">Student</option>
              <option value="lecturer">Lecturer</option>
              <option value="counsellor">Counsellor</option>
              <option value="admin">Admin</option>
              <option value="auditor">Auditor</option>
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-500 font-medium">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="py-1.5 px-3 bg-slate-50 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">All Status</option>
              <option value="active">Active Only</option>
              <option value="suspended">Suspended Only</option>
            </select>
          </div>

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            title="Refresh Table"
            className="p-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-600 hover:text-slate-900 transition"
          >
            <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin text-indigo-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs font-semibold uppercase tracking-wider">
              <tr>
                <th className="py-3.5 px-4">User / Email</th>
                <th className="py-3.5 px-4">Pseudonym PID</th>
                <th className="py-3.5 px-4">Role</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Created Date</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-slate-400">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-600" />
                    <span>Loading platform accounts...</span>
                  </td>
                </tr>
              ) : isError ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-rose-500">
                    <AlertCircle className="w-6 h-6 mx-auto mb-2" />
                    <span>Failed to retrieve users. Please try again.</span>
                  </td>
                </tr>
              ) : usersData?.items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-slate-400">
                    <Users className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                    <span>No users match the active search or filters.</span>
                  </td>
                </tr>
              ) : (
                usersData?.items.map((u) => {
                  const isSelf = String(u.id) === String(currentAdmin?.id);
                  return (
                    <tr key={u.id} className="hover:bg-slate-50/80 transition">
                      <td className="py-3.5 px-4">
                        <div className="flex flex-col">
                          <span className="font-semibold text-slate-900">{u.full_name}</span>
                          <span className="text-xs text-slate-500 font-mono">{u.email}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        {u.pid ? (
                          <span className="font-mono text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded">
                            {u.pid}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400 font-mono">None (Staff)</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        <StatusBadge role={u.role} size="sm" />
                      </td>
                      <td className="py-3.5 px-4">
                        <StatusBadge status={u.is_active} size="sm" />
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-500 whitespace-nowrap">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            onClick={() => setSelectedUserId(u.id)}
                            title="Inspect User Details"
                            className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition"
                          >
                            <Eye className="w-4 h-4" />
                          </button>

                          {/* Role Select Dropdown */}
                          <select
                            disabled={isSelf}
                            value={u.role}
                            onChange={(e) => handleChangeRole(u, e.target.value as UserRole)}
                            title={isSelf ? 'Cannot change own role' : 'Change user role'}
                            className={`py-1 px-2 border rounded text-xs font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 ${
                              isSelf
                                ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                                : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                            }`}
                          >
                            <option value="student">Student</option>
                            <option value="lecturer">Lecturer</option>
                            <option value="counsellor">Counsellor</option>
                            <option value="admin">Admin</option>
                            <option value="auditor">Auditor</option>
                          </select>

                          {/* Toggle Active/Suspend */}
                          <button
                            disabled={isSelf}
                            onClick={() => handleToggleStatus(u)}
                            title={
                              isSelf
                                ? 'Cannot suspend own admin account'
                                : u.is_active
                                ? 'Suspend account'
                                : 'Reactivate account'
                            }
                            className={`p-1.5 rounded-lg transition ${
                              isSelf
                                ? 'text-slate-300 cursor-not-allowed'
                                : u.is_active
                                ? 'text-slate-500 hover:text-rose-600 hover:bg-rose-50'
                                : 'text-slate-500 hover:text-emerald-600 hover:bg-emerald-50'
                            }`}
                          >
                            {u.is_active ? (
                              <ToggleRight className="w-5 h-5 text-emerald-600" />
                            ) : (
                              <ToggleLeft className="w-5 h-5 text-rose-500" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {usersData && usersData.total > 0 && (
          <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-600 gap-3">
            <div>
              Showing{' '}
              <span className="font-semibold text-slate-900">
                {(page - 1) * pageSize + 1}
              </span>{' '}
              to{' '}
              <span className="font-semibold text-slate-900">
                {Math.min(page * pageSize, usersData.total)}
              </span>{' '}
              of <span className="font-semibold text-slate-900">{usersData.total}</span> accounts
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-2.5 py-1.5 bg-white border border-slate-300 rounded-md font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center space-x-1"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Prev</span>
              </button>
              <span className="px-2 font-medium">
                Page {page} of {usersData.total_pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(usersData.total_pages, p + 1))}
                disabled={page >= usersData.total_pages}
                className="px-2.5 py-1.5 bg-white border border-slate-300 rounded-md font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center space-x-1"
              >
                <span>Next</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Slide-out User Detail Drawer */}
      {selectedUserId && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/50 backdrop-blur-sm flex justify-end">
          <div className="bg-white w-full max-w-lg h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="p-6 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Account Governance Details</h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">User ID: {selectedUserId}</p>
              </div>
              <button
                onClick={() => setSelectedUserId(null)}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200/60 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {isLoadingDetail ? (
                <div className="py-20 text-center">
                  <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-600 mb-2" />
                  <span className="text-sm text-slate-500">Loading user profile and history...</span>
                </div>
              ) : userDetail ? (
                <>
                  {/* Identity Header */}
                  <div className="flex items-center space-x-4 p-4 rounded-xl bg-slate-50 border border-slate-200">
                    <div className="w-12 h-12 rounded-full bg-indigo-100 text-indigo-700 font-bold text-lg flex items-center justify-center">
                      {userDetail.full_name.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="text-base font-bold text-slate-900 truncate">
                        {userDetail.full_name}
                      </h4>
                      <p className="text-xs text-slate-500 font-mono truncate">{userDetail.email}</p>
                      <div className="mt-2 flex items-center space-x-2">
                        <StatusBadge role={userDetail.role} size="sm" />
                        <StatusBadge status={userDetail.is_active} size="sm" />
                      </div>
                    </div>
                  </div>

                  {/* Feature 5: Pseudonym ID */}
                  <div className="p-4 rounded-xl bg-indigo-50/70 border border-indigo-100">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold text-indigo-900 flex items-center space-x-1">
                        <Shield className="w-4 h-4 text-indigo-600" />
                        <span>Feature 5 Pseudonym ID</span>
                      </span>
                      {userDetail.pid && (
                        <button
                          onClick={() => copyToClipboard(userDetail.pid!)}
                          className="text-[11px] font-medium text-indigo-600 hover:text-indigo-800 flex items-center space-x-1"
                        >
                          {copiedPid ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                          <span>{copiedPid ? 'Copied' : 'Copy'}</span>
                        </button>
                      )}
                    </div>
                    <p className="text-xs text-indigo-700/80 mb-2">
                      Cross-component identifier passed to ML models (C1-C4) ensuring zero student PII leakage.
                    </p>
                    <div className="font-mono text-sm font-bold text-indigo-950 bg-white p-2.5 rounded-lg border border-indigo-200">
                      {userDetail.pid || 'Not applicable (Staff account without pseudonym)'}
                    </div>
                  </div>

                  {/* Profile Attributes */}
                  <div className="space-y-3">
                    <h5 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      Profile Attributes
                    </h5>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                        <span className="text-slate-400 block mb-0.5">Department</span>
                        <span className="font-semibold text-slate-800">
                          {userDetail.profile?.department || 'Unspecified'}
                        </span>
                      </div>
                      <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                        <span className="text-slate-400 block mb-0.5">Phone</span>
                        <span className="font-semibold text-slate-800">
                          {userDetail.profile?.phone || 'Unspecified'}
                        </span>
                      </div>
                    </div>
                    {userDetail.profile?.bio && (
                      <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 text-xs">
                        <span className="text-slate-400 block mb-0.5">Bio</span>
                        <p className="text-slate-700">{userDetail.profile.bio}</p>
                      </div>
                    )}
                  </div>

                  {/* Feature 6: Ethics & Consent Status */}
                  <div className="space-y-3">
                    <h5 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-1">
                      <Scale className="w-4 h-4 text-slate-500" />
                      <span>Feature 6 Ethics & Consent Posture</span>
                    </h5>
                    <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2 text-xs">
                      <div className="flex justify-between items-center">
                        <span className="text-slate-500">Current Posture:</span>
                        <span
                          className={`font-bold px-2 py-0.5 rounded text-[11px] uppercase ${
                            userDetail.consent?.decision === 'accepted'
                              ? 'bg-emerald-100 text-emerald-800'
                              : userDetail.consent?.decision === 'withdrawn'
                              ? 'bg-rose-100 text-rose-800'
                              : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {userDetail.consent?.decision || 'Pending Review'}
                        </span>
                      </div>
                      {userDetail.consent?.notice_version && (
                        <div className="flex justify-between items-center">
                          <span className="text-slate-500">Notice Version:</span>
                          <span className="font-mono text-slate-800">
                            v{userDetail.consent.notice_version}
                          </span>
                        </div>
                      )}
                      {userDetail.consent?.decided_at && (
                        <div className="flex justify-between items-center">
                          <span className="text-slate-500">Recorded At:</span>
                          <span className="text-slate-800">
                            {new Date(userDetail.consent.decided_at).toLocaleString()}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Course Enrolments */}
                  <div className="space-y-3">
                    <h5 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-1">
                      <BookOpen className="w-4 h-4 text-slate-500" />
                      <span>Academic Enrolments ({userDetail.enrolments.length})</span>
                    </h5>
                    {userDetail.enrolments.length > 0 ? (
                      <div className="space-y-2">
                        {userDetail.enrolments.map((enr) => (
                          <div
                            key={enr.course_id}
                            className="p-3 rounded-lg border border-slate-200 bg-white flex items-center justify-between text-xs"
                          >
                            <div>
                              <span className="font-semibold text-slate-900 block">
                                {enr.course_name || enr.course_id}
                              </span>
                              {enr.course_code && (
                                <span className="font-mono text-[11px] text-slate-500">
                                  {enr.course_code}
                                </span>
                              )}
                            </div>
                            <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium capitalize">
                              {enr.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400 italic">No course enrolments recorded.</p>
                    )}
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* Create User Modal Dialog */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full overflow-hidden border border-slate-200 animate-in zoom-in-95 duration-150">
            <div className="p-6 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center space-x-2.5">
                <div className="p-2 bg-indigo-100 text-indigo-600 rounded-lg">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">Provision User Account</h3>
                  <p className="text-xs text-slate-500">Create an authenticated user account with role-based access.</p>
                </div>
              </div>
              <button
                onClick={() => setIsCreateModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                createMutation.mutate(createForm);
              }}
              className="p-6 space-y-4 text-sm"
            >
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Full Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Kasun Jayawardena"
                  value={createForm.full_name}
                  onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Email Address *
                </label>
                <input
                  type="email"
                  required
                  placeholder="e.g. kasun@sliit.lk"
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Platform Role *
                  </label>
                  <select
                    value={createForm.role}
                    onChange={(e) => setCreateForm({ ...createForm, role: e.target.value as UserRole })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm bg-white"
                  >
                    <option value="student">Student</option>
                    <option value="lecturer">Lecturer</option>
                    <option value="counsellor">Counsellor</option>
                    <option value="admin">Admin</option>
                    <option value="auditor">Auditor</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Temporary Password *
                  </label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    placeholder="Min 8 characters"
                    value={createForm.password}
                    onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Department / Faculty (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Faculty of Computing"
                  value={createForm.department || ''}
                  onChange={(e) => setCreateForm({ ...createForm, department: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                />
              </div>

              <div className="pt-3 border-t border-slate-200 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 transition text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition shadow-sm flex items-center space-x-1.5"
                >
                  {createMutation.isPending && (
                    <RefreshCw className="w-4 h-4 animate-spin text-white" />
                  )}
                  <span>Create Account</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirmation Dialog */}
      <ConfirmDialog
        isOpen={confirmState.isOpen}
        title={confirmState.title}
        message={confirmState.message}
        variant={confirmState.variant}
        isLoading={statusMutation.isPending || roleMutation.isPending}
        onConfirm={confirmState.onConfirm}
        onCancel={() => setConfirmState((prev) => ({ ...prev, isOpen: false }))}
      />
    </div>
  );
};
