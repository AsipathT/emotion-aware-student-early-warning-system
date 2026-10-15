import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  chatApi,
  ConversationListItem,
  ChatUserSummary,
  MessageResponse,
} from '../api/chat';
import { useAuth } from '../hooks/useAuth';
import { formatRelativeTime } from '../utils/time';
import {
  MessageCircle,
  Search,
  Send,
  Plus,
  ArrowLeft,
  X,
  AlertCircle,
  CheckCircle2,
  User as UserIcon,
} from 'lucide-react';

// ── Role chip helper ─────────────────────────────────────────────────────────

const roleChipClasses = (role: string) => {
  switch (role) {
    case 'lecturer':
      return 'bg-purple-50 text-purple-700 border-purple-200';
    case 'counsellor':
      return 'bg-teal-50 text-teal-700 border-teal-200';
    default:
      return 'bg-indigo-50 text-indigo-700 border-indigo-200';
  }
};

// ── Main ChatPage ────────────────────────────────────────────────────────────

export const ChatPage: React.FC = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const uid = user?.id || '';

  // Selected conversation
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  // Mobile: show thread vs list
  const [showThread, setShowThread] = useState(false);

  // New-chat modal
  const [isNewChatOpen, setIsNewChatOpen] = useState(false);
  const [userSearch, setUserSearch] = useState('');
  const [debouncedUserSearch, setDebouncedUserSearch] = useState('');

  // Composer
  const [messageBody, setMessageBody] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Toast
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  useEffect(() => {
    if (successMessage) {
      const t = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(t);
    }
  }, [successMessage]);

  // Debounce user search
  useEffect(() => {
    const t = setTimeout(() => setDebouncedUserSearch(userSearch), 400);
    return () => clearTimeout(t);
  }, [userSearch]);

  // ── Queries ────────────────────────────────────────────────────────────────

  const {
    data: conversations = [],
    isLoading: convsLoading,
    isError: convsError,
    error: convsErrorObj,
  } = useQuery<ConversationListItem[]>({
    queryKey: ['chatConversations'],
    queryFn: chatApi.getConversations,
    refetchInterval: 15000,
  });

  const {
    data: messages = [],
    isLoading: msgsLoading,
  } = useQuery<MessageResponse[]>({
    queryKey: ['chatMessages', activeConvId],
    queryFn: () => chatApi.getMessages(activeConvId!, { limit: 200 }),
    enabled: !!activeConvId,
    refetchInterval: 5000,
  });

  const { data: searchResults = [] } = useQuery<ChatUserSummary[]>({
    queryKey: ['chatUserSearch', debouncedUserSearch],
    queryFn: () =>
      chatApi.searchChatUsers({
        search: debouncedUserSearch || undefined,
        limit: 20,
      }),
    enabled: isNewChatOpen,
  });

  // ── Mark read on open / new messages ───────────────────────────────────────

  const markReadMutation = useMutation({
    mutationFn: (convId: string) => chatApi.markConversationRead(convId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatConversations'] });
    },
  });

  // Mark read when opening a conversation or when new messages arrive
  const prevMsgCountRef = useRef(0);
  useEffect(() => {
    if (activeConvId && messages.length > 0) {
      const hasUnread = messages.some(
        (m) => m.recipient_id === uid && !m.read_at
      );
      if (hasUnread || messages.length !== prevMsgCountRef.current) {
        markReadMutation.mutate(activeConvId);
      }
      prevMsgCountRef.current = messages.length;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConvId, messages.length]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Mutations ──────────────────────────────────────────────────────────────

  const sendMutation = useMutation({
    mutationFn: ({ convId, body }: { convId: string; body: string }) =>
      chatApi.sendMessage(convId, body),
    onSuccess: () => {
      setMessageBody('');
      queryClient.invalidateQueries({ queryKey: ['chatMessages', activeConvId] });
      queryClient.invalidateQueries({ queryKey: ['chatConversations'] });
    },
    onError: (err: any) => {
      setErrorMessage(
        err.response?.data?.detail || 'Failed to send message.'
      );
    },
  });

  const createConvMutation = useMutation({
    mutationFn: (recipientId: string) => chatApi.createConversation(recipientId),
    onSuccess: (conv) => {
      queryClient.invalidateQueries({ queryKey: ['chatConversations'] });
      setActiveConvId(conv.id);
      setShowThread(true);
      setIsNewChatOpen(false);
      setUserSearch('');
    },
    onError: (err: any) => {
      setErrorMessage(
        err.response?.data?.detail || 'Failed to start conversation.'
      );
    },
  });

  // ── Handlers ───────────────────────────────────────────────────────────────

  const handleSend = useCallback(() => {
    if (!activeConvId || !messageBody.trim() || sendMutation.isPending) return;
    sendMutation.mutate({ convId: activeConvId, body: messageBody.trim() });
  }, [activeConvId, messageBody, sendMutation]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const openConversation = (convId: string) => {
    setActiveConvId(convId);
    setShowThread(true);
    prevMsgCountRef.current = 0;
  };

  const activeConv = conversations.find((c) => c.id === activeConvId);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Toasts */}
      {successMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center justify-between text-emerald-800 text-sm animate-fade-in shadow-sm">
          <div className="flex items-center space-x-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <span className="font-medium">{successMessage}</span>
          </div>
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-600 hover:text-emerald-800 p-1">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {errorMessage && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl flex items-center justify-between text-rose-800 text-sm animate-fade-in shadow-sm">
          <div className="flex items-center space-x-2.5">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <span className="font-medium">{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-rose-600 hover:text-rose-800 p-1">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Header banner */}
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <span className="inline-flex items-center px-2.5 py-0.5 bg-indigo-50 text-indigo-700 rounded-full text-xs font-semibold uppercase tracking-wider">
              <MessageCircle className="w-3 h-3 mr-1" />
              Messages
            </span>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              Direct Messages
            </h1>
          </div>
          <button
            onClick={() => {
              setUserSearch('');
              setIsNewChatOpen(true);
            }}
            className="inline-flex items-center px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm rounded-xl shadow-sm hover:shadow transition"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            New Chat
          </button>
        </div>
      </div>

      {/* Two-pane chat layout */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden flex" style={{ height: 'calc(100vh - 340px)', minHeight: '400px' }}>
        {/* Left pane: conversation list */}
        <div
          className={`w-full md:w-80 lg:w-96 flex-shrink-0 border-r border-slate-200 flex flex-col ${
            showThread ? 'hidden md:flex' : 'flex'
          }`}
        >
          <div className="p-3 border-b border-slate-100">
            <h2 className="text-sm font-bold text-slate-700">Conversations</h2>
          </div>

          <div className="flex-1 overflow-y-auto">
            {convsLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
              </div>
            ) : convsError ? (
              <div className="p-4 text-xs text-rose-700">
                {(convsErrorObj as any)?.response?.data?.detail || 'Failed to load conversations.'}
              </div>
            ) : conversations.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
                <div className="inline-flex p-3 bg-indigo-50 text-indigo-600 rounded-2xl mb-3">
                  <MessageCircle className="w-7 h-7" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm">No conversations yet</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Start a new chat to begin messaging.
                </p>
              </div>
            ) : (
              conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => openConversation(conv.id)}
                  className={`w-full text-left px-4 py-3 border-b border-slate-100 hover:bg-slate-50 transition flex items-start space-x-3 ${
                    activeConvId === conv.id ? 'bg-indigo-50/60' : ''
                  }`}
                >
                  <div className="w-9 h-9 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center flex-shrink-0 mt-0.5">
                    {(conv.other_participant?.full_name || 'U')
                      .split(' ')
                      .map((n) => n[0])
                      .join('')
                      .toUpperCase()
                      .slice(0, 2)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-slate-900 truncate">
                        {conv.other_participant?.full_name || 'Unknown'}
                      </span>
                      <span className="text-[10px] text-slate-400 flex-shrink-0 ml-2">
                        {formatRelativeTime(conv.last_message_at)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between mt-0.5">
                      <div className="flex items-center space-x-1.5 min-w-0">
                        <span
                          className={`inline-flex items-center px-1 py-0 rounded text-[9px] font-bold uppercase border flex-shrink-0 ${roleChipClasses(
                            conv.other_participant?.role || 'student'
                          )}`}
                        >
                          {conv.other_participant?.role || 'student'}
                        </span>
                        <span className="text-xs text-slate-500 truncate">
                          {conv.last_message_preview || 'No messages yet'}
                        </span>
                      </div>
                      {conv.unread_count > 0 && (
                        <span className="flex-shrink-0 ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-indigo-600 text-white text-[10px] font-bold">
                          {conv.unread_count > 9 ? '9+' : conv.unread_count}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Right pane: message thread */}
        <div
          className={`flex-1 flex flex-col ${
            showThread ? 'flex' : 'hidden md:flex'
          }`}
        >
          {!activeConvId ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
              <div className="inline-flex p-4 bg-slate-100 text-slate-400 rounded-2xl mb-4">
                <MessageCircle className="w-10 h-10" />
              </div>
              <h3 className="font-bold text-slate-700 text-base">Select a conversation</h3>
              <p className="text-xs text-slate-500 mt-1">
                Choose an existing conversation or start a new chat.
              </p>
            </div>
          ) : (
            <>
              {/* Thread header */}
              <div className="px-4 py-3 border-b border-slate-200 flex items-center space-x-3">
                <button
                  onClick={() => setShowThread(false)}
                  className="md:hidden p-1 text-slate-500 hover:text-indigo-600 rounded-lg hover:bg-slate-100 transition"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
                <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center flex-shrink-0">
                  {(activeConv?.other_participant?.full_name || 'U')
                    .split(' ')
                    .map((n) => n[0])
                    .join('')
                    .toUpperCase()
                    .slice(0, 2)}
                </div>
                <div>
                  <div className="text-sm font-bold text-slate-900">
                    {activeConv?.other_participant?.full_name || 'Unknown'}
                  </div>
                  <span
                    className={`inline-flex items-center px-1.5 py-0 rounded text-[10px] font-bold uppercase border ${roleChipClasses(
                      activeConv?.other_participant?.role || 'student'
                    )}`}
                  >
                    {activeConv?.other_participant?.role || 'student'}
                  </span>
                </div>
              </div>

              {/* Messages area */}
              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
                {msgsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
                  </div>
                ) : messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <p className="text-sm text-slate-500">
                      No messages yet. Say hello!
                    </p>
                  </div>
                ) : (
                  messages.map((msg) => {
                    const isMine = msg.sender_id === uid;
                    return (
                      <div
                        key={msg.id}
                        className={`flex ${isMine ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
                            isMine
                              ? 'bg-indigo-600 text-white rounded-br-md'
                              : 'bg-slate-100 text-slate-800 rounded-bl-md'
                          }`}
                        >
                          <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                            {msg.body}
                          </p>
                          <p
                            className={`text-[10px] mt-1 ${
                              isMine ? 'text-indigo-200' : 'text-slate-400'
                            }`}
                          >
                            {formatRelativeTime(msg.created_at)}
                          </p>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Composer */}
              <div className="border-t border-slate-200 px-4 py-3">
                <div className="flex items-end space-x-2">
                  <textarea
                    ref={textareaRef}
                    rows={1}
                    maxLength={2000}
                    value={messageBody}
                    onChange={(e) => setMessageBody(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type a message..."
                    className="flex-1 resize-none px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                  />
                  <button
                    onClick={handleSend}
                    disabled={sendMutation.isPending || !messageBody.trim()}
                    className="p-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white rounded-xl disabled:opacity-60 transition flex-shrink-0"
                  >
                    {sendMutation.isPending ? (
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      <Send className="w-5 h-5" />
                    )}
                  </button>
                </div>
                <p className="text-[10px] text-slate-400 mt-1 text-right">
                  {messageBody.length} / 2,000 · Enter to send, Shift+Enter for newline
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {/* New Chat Modal */}
      {isNewChatOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white w-full max-w-md rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <MessageCircle className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-base">New Chat</h3>
              </div>
              <button
                onClick={() => setIsNewChatOpen(false)}
                className="text-slate-400 hover:text-slate-600 rounded-lg p-1 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 space-y-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search users by name..."
                  value={userSearch}
                  onChange={(e) => setUserSearch(e.target.value)}
                  className="w-full pl-9 pr-4 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
                  autoFocus
                />
              </div>

              <div className="max-h-64 overflow-y-auto space-y-1">
                {searchResults.length === 0 ? (
                  <div className="py-8 text-center">
                    <UserIcon className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="text-xs text-slate-500">
                      {debouncedUserSearch
                        ? 'No users found matching your search.'
                        : 'Type a name to search for users.'}
                    </p>
                  </div>
                ) : (
                  searchResults.map((u) => (
                    <button
                      key={u.id}
                      onClick={() => createConvMutation.mutate(u.id)}
                      disabled={createConvMutation.isPending}
                      className="w-full text-left px-3 py-2.5 rounded-xl hover:bg-indigo-50 transition flex items-center space-x-3 disabled:opacity-60"
                    >
                      <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 font-bold text-xs flex items-center justify-center flex-shrink-0">
                        {u.full_name
                          .split(' ')
                          .map((n) => n[0])
                          .join('')
                          .toUpperCase()
                          .slice(0, 2)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold text-slate-900 truncate">
                          {u.full_name}
                        </div>
                        <span
                          className={`inline-flex items-center px-1.5 py-0 rounded text-[10px] font-bold uppercase border ${roleChipClasses(
                            u.role
                          )}`}
                        >
                          {u.role}
                        </span>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
