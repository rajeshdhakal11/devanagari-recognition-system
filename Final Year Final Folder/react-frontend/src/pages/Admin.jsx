import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast, Toaster } from 'react-hot-toast';
import { ArrowLeft, ShieldCheck, RefreshCw, UserCog, LogOut } from 'lucide-react';
import { bootstrapAdmin, getAdminPredictionQualityAnalytics, getProfile, listAdminUsers, updateUserRole } from '../utils/api';

const roleBadgeStyles = {
  admin: 'bg-emerald-500/15 text-emerald-300 border-emerald-400/30',
  user: 'bg-slate-500/15 text-slate-300 border-slate-400/30'
};

const Admin = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState([]);
  const [actioningUserId, setActioningUserId] = useState(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [qualityAnalytics, setQualityAnalytics] = useState(null);
  const [bootstrapLoading, setBootstrapLoading] = useState(false);
  const [bootstrapForm, setBootstrapForm] = useState({
    identifier: '',
    bootstrap_key: ''
  });

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const profileResponse = await getProfile();
      const role = profileResponse?.data?.data?.role || 'user';
      const profileIdentifier = profileResponse?.data?.data?.email || profileResponse?.data?.data?.username || '';
      localStorage.setItem('user_role', role);
      setIsAdmin(role === 'admin');
      setBootstrapForm((prev) => ({ ...prev, identifier: prev.identifier || profileIdentifier }));

      if (role !== 'admin') {
        setUsers([]);
        return;
      }

      const response = await listAdminUsers();
      setUsers(response?.data?.data || []);

      const analyticsResponse = await getAdminPredictionQualityAnalytics();
      setQualityAnalytics(analyticsResponse?.data?.data || null);
    } catch (error) {
      const message = error?.response?.data?.message || 'Unable to load admin data';
      toast.error(message);
      setUsers([]);
      setQualityAnalytics(null);
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const adminCount = useMemo(
    () => users.filter((user) => user.role === 'admin').length,
    [users]
  );

  const handleRoleChange = async (userId, role) => {
    setActioningUserId(userId);
    try {
      await updateUserRole(userId, role);
      toast.success('Role updated');
      await fetchUsers();
    } catch (error) {
      const message = error?.response?.data?.message || 'Failed to update role';
      toast.error(message);
    } finally {
      setActioningUserId(null);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user_role');
    navigate('/auth');
  };

  const handleBootstrapChange = (event) => {
    const { name, value } = event.target;
    setBootstrapForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleBootstrapSubmit = async (event) => {
    event.preventDefault();
    if (!bootstrapForm.identifier || !bootstrapForm.bootstrap_key) {
      toast.error('Identifier and bootstrap key are required');
      return;
    }

    setBootstrapLoading(true);
    try {
      await bootstrapAdmin(bootstrapForm.identifier.trim(), bootstrapForm.bootstrap_key.trim());
      toast.success('Admin role assigned. Reloading admin panel...');
      await fetchUsers();
    } catch (error) {
      const message = error?.response?.data?.message || 'Failed to bootstrap admin';
      toast.error(message);
    } finally {
      setBootstrapLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#04060d] py-10 px-4">
      <Toaster position="top-center" />

      <div className="relative z-10 w-full max-w-5xl mx-auto">
        <div className="bg-[#0b0f1d] rounded-3xl border border-gray-800 shadow-xl overflow-hidden">
          <div className="p-6 border-b border-gray-700/50 flex flex-wrap justify-between items-center gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-gray-500">Admin Console</p>
              <h1 className="text-2xl font-bold text-white mt-1">User Role Management</h1>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => navigate('/dashboard')}
                className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 inline-flex items-center gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
              <button
                onClick={handleLogout}
                className="p-2 text-gray-400 hover:text-white transition-colors rounded-lg hover:bg-gray-700/50"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>

          <div className="p-6 grid grid-cols-1 sm:grid-cols-3 gap-3 border-b border-gray-800 bg-[#080b16]">
            <div className="rounded-2xl border border-gray-800 bg-[#0f1324] px-4 py-3">
              <p className="text-sm text-gray-400">Total Users</p>
              <p className="text-2xl text-white font-semibold">{users.length}</p>
            </div>
            <div className="rounded-2xl border border-gray-800 bg-[#0f1324] px-4 py-3">
              <p className="text-sm text-gray-400">Admins</p>
              <p className="text-2xl text-emerald-300 font-semibold">{adminCount}</p>
            </div>
            <div className="rounded-2xl border border-gray-800 bg-[#0f1324] px-4 py-3">
              <p className="text-sm text-gray-400">Standard Users</p>
              <p className="text-2xl text-slate-200 font-semibold">{users.length - adminCount}</p>
            </div>
          </div>

          {isAdmin && qualityAnalytics && (
            <div className="p-6 border-b border-gray-800 bg-[#080b16] space-y-4">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-gray-500">Quality Analytics</p>
                <h2 className="text-lg font-semibold text-white mt-1">Low-confidence Signals</h2>
                <p className="text-sm text-gray-400 mt-1">Lookback: last {qualityAnalytics.lookback_days} days, threshold: {(qualityAnalytics.threshold * 100).toFixed(0)}%</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="rounded-2xl border border-gray-800 bg-[#0f1324] px-4 py-3">
                  <p className="text-sm text-gray-400">Total Predictions</p>
                  <p className="text-2xl text-white font-semibold">{qualityAnalytics.total_predictions || 0}</p>
                </div>
                <div className="rounded-2xl border border-gray-800 bg-[#0f1324] px-4 py-3">
                  <p className="text-sm text-gray-400">Low Confidence Count</p>
                  <p className="text-2xl text-amber-300 font-semibold">{qualityAnalytics.low_confidence_count || 0}</p>
                </div>
                <div className="rounded-2xl border border-gray-800 bg-[#0f1324] px-4 py-3">
                  <p className="text-sm text-gray-400">Low Confidence Rate</p>
                  <p className="text-2xl text-rose-300 font-semibold">{qualityAnalytics.low_confidence_rate || 0}%</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-2xl border border-gray-800 bg-[#0f1324] px-4 py-3">
                  <p className="text-sm text-gray-300 font-medium">Top Risk Characters</p>
                  <div className="mt-2 space-y-1">
                    {(qualityAnalytics.low_confidence_by_character || []).length === 0 ? (
                      <p className="text-sm text-gray-500">No low-confidence signals yet.</p>
                    ) : (
                      qualityAnalytics.low_confidence_by_character.map((item) => (
                        <p key={item.character} className="text-sm text-gray-300">
                          {item.character}: {item.count}
                        </p>
                      ))
                    )}
                  </div>
                </div>

                <div className="rounded-2xl border border-gray-800 bg-[#0f1324] px-4 py-3">
                  <p className="text-sm text-gray-300 font-medium">Top Risk Users</p>
                  <div className="mt-2 space-y-1">
                    {(qualityAnalytics.user_risk_summary || []).length === 0 ? (
                      <p className="text-sm text-gray-500">No user-level risk signals yet.</p>
                    ) : (
                      qualityAnalytics.user_risk_summary.map((item) => (
                        <p key={item.user_id} className="text-sm text-gray-300">
                          {item.username}: {item.low_confidence_count}/{item.total_predictions} ({item.low_confidence_rate}%)
                        </p>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold text-white">Accounts</h2>
              {isAdmin && (
                <button
                  onClick={fetchUsers}
                  className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 inline-flex items-center gap-2"
                >
                  <RefreshCw className="w-4 h-4" />
                  Refresh
                </button>
              )}
            </div>

            {loading ? (
              <div className="flex justify-center py-12">
                <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : !isAdmin ? (
              <form
                onSubmit={handleBootstrapSubmit}
                className="border border-dashed border-gray-700 rounded-2xl p-5 bg-gray-900/40 space-y-4"
              >
                <div>
                  <p className="text-white font-semibold">No admin role on your account yet</p>
                  <p className="text-sm text-gray-400 mt-1">
                    Use the bootstrap key from backend .env to create the first admin account.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <input
                    type="text"
                    name="identifier"
                    value={bootstrapForm.identifier}
                    onChange={handleBootstrapChange}
                    placeholder="Email or username"
                    className="w-full rounded-xl bg-[#0b0f1d] border border-gray-700 px-3 py-2 text-gray-100 placeholder:text-gray-500 focus:outline-none focus:border-purple-500"
                  />
                  <input
                    type="password"
                    name="bootstrap_key"
                    value={bootstrapForm.bootstrap_key}
                    onChange={handleBootstrapChange}
                    placeholder="ADMIN_BOOTSTRAP_KEY"
                    className="w-full rounded-xl bg-[#0b0f1d] border border-gray-700 px-3 py-2 text-gray-100 placeholder:text-gray-500 focus:outline-none focus:border-purple-500"
                  />
                </div>

                <button
                  type="submit"
                  disabled={bootstrapLoading}
                  className={`px-4 py-2 rounded-lg text-sm font-medium ${
                    bootstrapLoading
                      ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                      : 'bg-purple-600 hover:bg-purple-500 text-white'
                  }`}
                >
                  {bootstrapLoading ? 'Assigning...' : 'Assign Admin Role'}
                </button>
              </form>
            ) : users.length === 0 ? (
              <div className="text-center py-12 text-gray-400 border border-dashed border-gray-700 rounded-2xl">
                No users found.
              </div>
            ) : (
              <div className="space-y-3">
                {users.map((user) => (
                  <div
                    key={user.id}
                    className="bg-gray-900/50 border border-gray-700 rounded-2xl p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-base font-semibold text-white">{user.username}</p>
                        <span
                          className={`px-2 py-1 text-xs rounded-lg border ${roleBadgeStyles[user.role] || roleBadgeStyles.user}`}
                        >
                          {user.role}
                        </span>
                      </div>
                      <p className="text-sm text-gray-400 mt-1">{user.email}</p>
                      <p className="text-xs text-gray-500 mt-1">Predictions: {user.prediction_count || 0}</p>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleRoleChange(user.id, 'user')}
                        disabled={actioningUserId === user.id || user.role === 'user'}
                        className={`px-3 py-2 rounded-lg text-sm inline-flex items-center gap-2 ${
                          user.role === 'user'
                            ? 'bg-gray-800/40 text-gray-500 cursor-not-allowed'
                            : 'bg-gray-800 hover:bg-gray-700 text-gray-200'
                        }`}
                      >
                        <UserCog className="w-4 h-4" />
                        Set User
                      </button>
                      <button
                        onClick={() => handleRoleChange(user.id, 'admin')}
                        disabled={actioningUserId === user.id || user.role === 'admin'}
                        className={`px-3 py-2 rounded-lg text-sm inline-flex items-center gap-2 ${
                          user.role === 'admin'
                            ? 'bg-emerald-600/20 text-emerald-400 cursor-not-allowed'
                            : 'bg-emerald-600/80 hover:bg-emerald-500 text-white'
                        }`}
                      >
                        <ShieldCheck className="w-4 h-4" />
                        Set Admin
                      </button>
                    </div>
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

export default Admin;
