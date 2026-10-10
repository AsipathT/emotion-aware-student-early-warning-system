import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi, SystemStatsResponse, AdminUserResponse } from '../api/admin';
import { UserRole } from '../api/auth';
import { useAuth } from '../hooks/useAuth';
import {
  Users,
  UserCheck,
  BookOpen,
  Globe,
  Shield,
  Search,
  AlertCircle,
  CheckCircle2,
  Calendar,
  Building,
  GraduationCap,
  ToggleLeft,
  ToggleRight,
  ShieldAlert,
} from 'lucide-react';

export const AdminDashboardPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { user: currentAdmin } = useAuth();

  // Search & Role filters
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<'all' | UserRole>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'suspended'>('all');

  // Feedback notifications
  const [actionFeedback, setActionFeedback] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);

  // 1. Fetch system stats
  const {
    data: stats,
    isLoading: isLoadingStats,
  } = useQuery<SystemStatsResponse>({
    queryKey: ['adminStats'],
    queryFn: adminApi.getAdminStats,
    refetchInterval: 1000 * 30, // Poll every 30s
  });

  // 2. Fetch all users
  const {
    data: users = [],
    isLoading: isLoadingUsers,
    isError: isErrorUsers,
    error: usersError,
  } = useQuery<AdminUserResponse[]>({
    queryKey: ['adminUsers'],
    queryFn: adminApi.getAdminUsers,
  });

  // 3. Mutation: Update status
  const statusMutation = useMutation({
    mutationFn: ({ userId, isActive }: { userId: string; isActive: boolean }) =>
      adminApi.updateUserStatus(userId, isActive),
    onSuccess: (updatedUser) => {
      queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
      queryClient.invalidateQueries({ queryKey: ['adminStats'] });
      setActionFeedback({
        type: 'success',
        message: `Account for "${updatedUser.full_name}" is now ${
          updatedUser.is_active ? 'active' : 'suspended'
        }.`,
      });
      setTimeout(() => setActionFeedback(null), 4000);
    },
    onError: (err: any) => {
      const detail =
        err.response?.data?.detail || 'Failed to update user status.';
      setActionFeedback({ type: 'error', message: detail });
    },
  });

  // 4. Mutation: Update role
  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) =>
      adminApi.updateUserRole(userId, role),
    onSuccess: (updatedUser) => {
      queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
      queryClient.invalidateQueries({ queryKey: ['adminStats'] });
      setActionFeedback({
        type: 'success',
        message: `Role for "${updatedUser.full_name}" updated to "${updatedUser.role}".`,
      });
      setTimeout(() => setActionFeedback(null), 4000);
    },
    onError: (err: any) => {
      const detail =
        err.response?.data?.detail || 'Failed to update user role.';
      setActionFeedback({ type: 'error', message: detail });
    },
  });

  // Filtered users
  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      u.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (u.profile?.department &&
        u.profile.department.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (u.profile?.student_id &&
        u.profile.student_id.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!matchesSearch) return false;

    if (roleFilter !== 'all' && u.role !== roleFilter) return false;

    if (statusFilter === 'active' && !u.is_active) return false;
    if (statusFilter === 'suspended' && u.is_active) return false;

    return true;
  });

  const getRoleBadgeClass = (role: UserRole) => {
    switch (role) {
      case 'admin':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'lecturer':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'counsellor':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'student':
      default:
        return 'bg-indigo-50 text-indigo-700 border-indigo-200';
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-2 px-3 py-1 bg-purple-50 text-purple-700 rounded-full text-xs font-semibold uppercase tracking-wider mb-2 border border-purple-100">
            <Shield className="w-3.5 h-3.5" />
            <span>Platform Governance</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            System Administration Panel
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Manage system-wide accounts, authorization roles, and monitor course deployments.
          </p>
        </div>

        <div className="flex items-center space-x-2 px-3.5 py-2 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-600 font-mono">
          <ShieldAlert className="w-4 h-4 text-purple-600" />
          <span>Admin: {currentAdmin?.email}</span>
        </div>
      </div>

      {/* Action Feedback Banner */}
      {actionFeedback && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between transition-all ${
            actionFeedback.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          <div className="flex items-center space-x-2.5 text-sm font-medium">
            {actionFeedback.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            )}
            <span>{actionFeedback.message}</span>
          </div>
          <button
            onClick={() => setActionFeedback(null)}
            className="text-xs font-bold text-slate-400 hover:text-slate-600"
          >
            ✕
          </button>
        </div>
      )}

      {/* Top Section: Statistics Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Total Users */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Total Users
            </p>
            <p className="text-2xl font-black text-slate-900">
              {isLoadingStats ? '...' : stats?.total_users ?? 0}
            </p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              {stats?.total_students ?? 0} students &bull; {stats?.total_lecturers ?? 0} lecturers
            </p>
          </div>
        </div>

        {/* Active Accounts */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-emerald-50 text-emerald-600 rounded-xl">
            <UserCheck className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Active Accounts
            </p>
            <p className="text-2xl font-black text-slate-900">
              {isLoadingStats ? '...' : stats?.active_users ?? 0}
            </p>
            <p className="text-[11px] text-emerald-600 mt-0.5 font-medium">
              {stats?.total_users && stats.active_users
                ? `${Math.round((stats.active_users / stats.total_users) * 100)}% operational`
                : '100% operational'}
            </p>
          </div>
        </div>

        {/* Total Courses */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-blue-50 text-blue-600 rounded-xl">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Total Courses
            </p>
            <p className="text-2xl font-black text-slate-900">
              {isLoadingStats ? '...' : stats?.total_courses ?? 0}
            </p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Registered academic modules
            </p>
          </div>
        </div>

        {/* Published Courses */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4">
          <div className="p-3 bg-amber-50 text-amber-600 rounded-xl">
            <Globe className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Published Courses
            </p>
            <p className="text-2xl font-black text-slate-900">
              {isLoadingStats ? '...' : stats?.published_courses ?? 0}
            </p>
            <p className="text-[11px] text-amber-700 mt-0.5 font-medium">
              Live in student catalog
            </p>
          </div>
        </div>
      </div>

      {/* Main Section: User Management Table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden space-y-4">
        {/* Table Controls (Search & Filters) */}
        <div className="p-5 sm:p-6 border-b border-slate-100 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md shadow-sm">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Search className="h-4 w-4" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search user by name, email, department, or student ID..."
              className="block w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-600 transition"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Role Filter */}
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value as any)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-purple-500/20"
            >
              <option value="all">All Roles</option>
              <option value="student">Student</option>
              <option value="lecturer">Lecturer</option>
              <option value="counsellor">Counsellor</option>
              <option value="admin">Admin</option>
            </select>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-700 focus:bg-white focus:outline-none focus:ring-2 focus:ring-purple-500/20"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active Only</option>
              <option value="suspended">Suspended Only</option>
            </select>
          </div>
        </div>

        {/* Loading / Error States */}
        {isLoadingUsers && (
          <div className="py-20 flex flex-col items-center justify-center space-y-3">
            <div className="w-10 h-10 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin" />
            <p className="text-sm text-slate-500 font-medium">Loading user accounts...</p>
          </div>
        )}

        {isErrorUsers && (
          <div className="m-6 p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-sm flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">Failed to load platform users</p>
              <p className="text-xs text-rose-700 mt-0.5">
                {(usersError as any)?.response?.data?.detail ||
                  'Ensure your session has administrative privileges.'}
              </p>
            </div>
          </div>
        )}

        {/* Data Table */}
        {!isLoadingUsers && !isErrorUsers && (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/70 border-b border-slate-200/80 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3.5 px-6">User Account</th>
                  <th className="py-3.5 px-6">Role & Authorization</th>
                  <th className="py-3.5 px-6">Department & ID</th>
                  <th className="py-3.5 px-6">Account Status</th>
                  <th className="py-3.5 px-6">Registered</th>
                  <th className="py-3.5 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400 text-sm">
                      No user accounts match the selected criteria.
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map((u) => {
                    const initials = u.full_name
                      .split(' ')
                      .map((n) => n[0])
                      .slice(0, 2)
                      .join('')
                      .toUpperCase();

                    const isSelf = currentAdmin?.id === u.id;

                    return (
                      <tr
                        key={u.id}
                        className="hover:bg-slate-50/70 transition-colors group"
                      >
                        {/* User identity */}
                        <td className="py-4 px-6">
                          <div className="flex items-center space-x-3.5">
                            {u.profile?.avatar_url ? (
                              <img
                                src={u.profile.avatar_url}
                                alt={u.full_name}
                                className="w-10 h-10 rounded-xl object-cover border border-slate-200"
                              />
                            ) : (
                              <div className="w-10 h-10 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center font-bold text-xs">
                                {initials}
                              </div>
                            )}

                            <div>
                              <div className="flex items-center space-x-2">
                                <span className="font-bold text-slate-900">
                                  {u.full_name}
                                </span>
                                {isSelf && (
                                  <span className="px-1.5 py-0.5 text-[10px] font-bold uppercase bg-slate-200 text-slate-700 rounded">
                                    You
                                  </span>
                                )}
                              </div>
                              <span className="text-xs text-slate-500 block">
                                {u.email}
                              </span>
                            </div>
                          </div>
                        </td>

                        {/* Role selector dropdown */}
                        <td className="py-4 px-6">
                          <div className="flex items-center space-x-2">
                            <select
                              value={u.role}
                              disabled={isSelf || roleMutation.isPending}
                              onChange={(e) =>
                                roleMutation.mutate({
                                  userId: u.id,
                                  role: e.target.value as UserRole,
                                })
                              }
                              className={`text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-lg border focus:outline-none cursor-pointer transition ${getRoleBadgeClass(
                                u.role
                              )} ${isSelf ? 'opacity-70 cursor-not-allowed' : 'hover:border-purple-400'}`}
                            >
                              <option value="student">Student</option>
                              <option value="lecturer">Lecturer</option>
                              <option value="counsellor">Counsellor</option>
                              <option value="admin">Admin</option>
                            </select>
                          </div>
                        </td>

                        {/* Profile Info */}
                        <td className="py-4 px-6 text-xs text-slate-600">
                          {u.profile?.department ? (
                            <span className="flex items-center font-medium text-slate-700">
                              <Building className="w-3.5 h-3.5 mr-1 text-slate-400" />
                              {u.profile.department}
                            </span>
                          ) : (
                            <span className="text-slate-400 italic">No department</span>
                          )}
                          {u.profile?.student_id && (
                            <span className="flex items-center font-mono text-[11px] text-slate-500 mt-0.5">
                              <GraduationCap className="w-3.5 h-3.5 mr-1 text-slate-400" />
                              ID: {u.profile.student_id}
                            </span>
                          )}
                        </td>

                        {/* Status badge */}
                        <td className="py-4 px-6">
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                              u.is_active
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : 'bg-rose-50 text-rose-700 border border-rose-200'
                            }`}
                          >
                            <span
                              className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                                u.is_active ? 'bg-emerald-500' : 'bg-rose-500'
                              }`}
                            />
                            {u.is_active ? 'Active' : 'Suspended'}
                          </span>
                        </td>

                        {/* Created At */}
                        <td className="py-4 px-6 text-xs text-slate-500 font-mono">
                          <span className="flex items-center">
                            <Calendar className="w-3.5 h-3.5 mr-1 text-slate-400" />
                            {new Date(u.created_at).toLocaleDateString()}
                          </span>
                        </td>

                        {/* Status Toggle Action */}
                        <td className="py-4 px-6 text-right">
                          <button
                            type="button"
                            disabled={isSelf || statusMutation.isPending}
                            onClick={() =>
                              statusMutation.mutate({
                                userId: u.id,
                                isActive: !u.is_active,
                              })
                            }
                            title={
                              isSelf
                                ? 'You cannot deactivate your own account'
                                : u.is_active
                                ? 'Click to suspend user account'
                                : 'Click to activate user account'
                            }
                            className={`inline-flex items-center px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
                              isSelf
                                ? 'opacity-40 cursor-not-allowed text-slate-400 bg-slate-100'
                                : u.is_active
                                ? 'text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200'
                                : 'text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200'
                            }`}
                          >
                            {u.is_active ? (
                              <>
                                <ToggleRight className="w-4 h-4 mr-1 text-rose-500" />
                                <span>Suspend</span>
                              </>
                            ) : (
                              <>
                                <ToggleLeft className="w-4 h-4 mr-1 text-emerald-500" />
                                <span>Activate</span>
                              </>
                            )}
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
