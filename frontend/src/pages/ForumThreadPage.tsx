import React, { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  forumApi,
  ThreadDetail,
  PostResponse,
  PostCreatePayload,
  ThreadModerationPayload,
} from '../api/forum';
import { useAuth } from '../hooks/useAuth';
import { formatRelativeTime } from '../utils/time';
import {
  ArrowLeft,
  MessageSquare,
  Reply,
  Pin,
  PinOff,
  Lock,
  Unlock,
  AlertCircle,
  X,
  CheckCircle2,
  Send,
  CornerDownRight,
} from 'lucide-react';

// ── Build nested tree from flat posts ────────────────────────────────────────

interface PostNode extends PostResponse {
  children: PostNode[];
  depth: number;
}

function buildPostTree(posts: PostResponse[]): PostNode[] {
  const map = new Map<string, PostNode>();
  const roots: PostNode[] = [];

  // Initialise nodes
  for (const p of posts) {
    map.set(p.id, { ...p, children: [], depth: 0 });
  }

  for (const p of posts) {
    const node = map.get(p.id)!;
    if (p.parent_post_id && map.has(p.parent_post_id)) {
      const parent = map.get(p.parent_post_id)!;
      node.depth = Math.min(parent.depth + 1, 4); // visual cap at 4
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}

// ── Recursive post renderer ─────────────────────────────────────────────────

const PostCard: React.FC<{
  node: PostNode;
  onReply: (postId: string, authorName: string) => void;
  canReply: boolean;
  roleChip: (role: string) => string;
}> = ({ node, onReply, canReply, roleChip }) => {
  const indent = Math.min(node.depth, 4);

  return (
    <div style={{ marginLeft: indent > 0 ? `${indent * 24}px` : 0 }}>
      <div className="bg-white rounded-xl p-4 border border-slate-200/80 shadow-sm space-y-2">
        {/* Nesting indicator */}
        {indent > 0 && (
          <div className="flex items-center text-xs text-slate-400 space-x-1 mb-1">
            <CornerDownRight className="w-3 h-3" />
            <span>Reply</span>
          </div>
        )}

        {/* Author row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 text-xs">
            <span className="font-semibold text-slate-800">
              {node.author?.full_name || 'Unknown'}
            </span>
            <span
              className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase border ${roleChip(
                node.author?.role || 'student'
              )}`}
            >
              {node.author?.role || 'student'}
            </span>
            <span className="text-slate-400">
              {formatRelativeTime(node.created_at)}
            </span>
          </div>

          {canReply && (
            <button
              onClick={() =>
                onReply(node.id, node.author?.full_name || 'Unknown')
              }
              className="inline-flex items-center text-xs text-slate-500 hover:text-indigo-600 transition px-2 py-1 rounded-lg hover:bg-indigo-50"
            >
              <Reply className="w-3 h-3 mr-1" />
              Reply
            </button>
          )}
        </div>

        {/* Body */}
        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
          {node.body}
        </p>
      </div>

      {/* Render children */}
      {node.children.length > 0 && (
        <div className="mt-2 space-y-2">
          {node.children.map((child) => (
            <PostCard
              key={child.id}
              node={child}
              onReply={onReply}
              canReply={canReply}
              roleChip={roleChip}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// ── Main page ────────────────────────────────────────────────────────────────

export const ForumThreadPage: React.FC = () => {
  const { courseId, threadId } = useParams<{
    courseId: string;
    threadId: string;
  }>();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const canWrite =
    user?.role === 'student' || user?.role === 'lecturer' || user?.role === 'admin';
  const canModerate = user?.role === 'lecturer' || user?.role === 'admin';

  // Reply state
  const [replyBody, setReplyBody] = useState('');
  const [replyParentId, setReplyParentId] = useState<string | null>(null);
  const [replyParentLabel, setReplyParentLabel] = useState<string | null>(null);

  // Toast
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  useEffect(() => {
    if (successMessage) {
      const t = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(t);
    }
  }, [successMessage]);

  // Query
  const {
    data: thread,
    isLoading,
    isError,
    error,
  } = useQuery<ThreadDetail>({
    queryKey: ['forumThread', threadId],
    queryFn: () => forumApi.getThreadDetail(threadId!),
    enabled: !!threadId,
    refetchInterval: 30000,
  });

  const isLocked = thread?.is_locked ?? false;
  const canReply = canWrite && !isLocked;

  // Build post tree
  const postTree = useMemo(
    () => (thread?.posts ? buildPostTree(thread.posts) : []),
    [thread?.posts]
  );

  // Reply mutation
  const replyMutation = useMutation({
    mutationFn: (payload: PostCreatePayload) =>
      forumApi.createPost(threadId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['forumThread', threadId] });
      queryClient.invalidateQueries({ queryKey: ['forumThreads', courseId] });
      setReplyBody('');
      setReplyParentId(null);
      setReplyParentLabel(null);
      setSuccessMessage('Reply posted.');
    },
    onError: (err: any) => {
      setActionError(
        err.response?.data?.detail || 'Failed to post reply.'
      );
    },
  });

  // Moderation mutation
  const moderateMutation = useMutation({
    mutationFn: (payload: ThreadModerationPayload) =>
      forumApi.moderateThread(threadId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['forumThread', threadId] });
      queryClient.invalidateQueries({ queryKey: ['forumThreads', courseId] });
      setSuccessMessage('Thread updated.');
    },
    onError: (err: any) => {
      setActionError(
        err.response?.data?.detail || 'Moderation action failed.'
      );
    },
  });

  const handleReplySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);
    if (!replyBody.trim()) return;
    replyMutation.mutate({
      body: replyBody.trim(),
      parent_post_id: replyParentId,
    });
  };

  const handleSetReplyTo = (postId: string, authorName: string) => {
    setReplyParentId(postId);
    setReplyParentLabel(authorName);
    // Scroll to reply box
    document.getElementById('reply-box')?.scrollIntoView({ behavior: 'smooth' });
  };

  const roleChipClasses = (role: string) => {
    switch (role) {
      case 'lecturer':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'admin':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'counsellor':
        return 'bg-teal-50 text-teal-700 border-teal-200';
      default:
        return 'bg-indigo-50 text-indigo-700 border-indigo-200';
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-20 flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        <p className="text-sm font-medium text-slate-500">Loading thread...</p>
      </div>
    );
  }

  if (isError || !thread) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16">
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl flex items-start space-x-3 text-rose-800">
          <AlertCircle className="w-6 h-6 text-rose-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-bold text-base">Thread Not Found</h3>
            <p className="text-sm mt-1 text-rose-700">
              {(error as any)?.response?.data?.detail ||
                'This thread may have been removed or you lack permission.'}
            </p>
            <Link
              to={`/courses/${courseId}/forum`}
              className="mt-4 inline-flex items-center text-xs font-semibold text-rose-800 hover:text-rose-950 underline"
            >
              <ArrowLeft className="w-3.5 h-3.5 mr-1" />
              Back to Forum
            </Link>
          </div>
        </div>
      </div>
    );
  }

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
      {actionError && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl flex items-center justify-between text-rose-800 text-sm animate-fade-in shadow-sm">
          <div className="flex items-center space-x-2.5">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <span className="font-medium">{actionError}</span>
          </div>
          <button onClick={() => setActionError(null)} className="text-rose-600 hover:text-rose-800 p-1">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Back link */}
      <div>
        <Link
          to={`/courses/${courseId}/forum`}
          className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-indigo-600 transition group"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5 group-hover:-translate-x-1 transition" />
          Back to Forum
        </Link>
      </div>

      {/* Original post card */}
      <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200/80 shadow-sm space-y-4">
        <div className="flex items-center flex-wrap gap-2">
          {thread.is_pinned && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-50 text-amber-700 border border-amber-200">
              <Pin className="w-2.5 h-2.5 mr-0.5" />
              Pinned
            </span>
          )}
          {thread.is_locked && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-600 border border-slate-200">
              <Lock className="w-2.5 h-2.5 mr-0.5" />
              Locked
            </span>
          )}
        </div>

        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
          {thread.title}
        </h1>

        <div className="flex items-center space-x-3 text-xs text-slate-500">
          <span className="font-semibold text-slate-800">
            {thread.author?.full_name || 'Unknown'}
          </span>
          <span
            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase border ${roleChipClasses(
              thread.author?.role || 'student'
            )}`}
          >
            {thread.author?.role || 'student'}
          </span>
          <span>{formatRelativeTime(thread.created_at)}</span>
          <span className="flex items-center space-x-1">
            <MessageSquare className="w-3 h-3" />
            <span>{thread.reply_count} replies</span>
          </span>
        </div>

        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
          {thread.body}
        </p>

        {/* Moderation buttons */}
        {canModerate && (
          <div className="flex items-center gap-2 pt-2 border-t border-slate-100">
            <button
              onClick={() =>
                moderateMutation.mutate({ is_pinned: !thread.is_pinned })
              }
              disabled={moderateMutation.isPending}
              className="inline-flex items-center px-3 py-1.5 text-xs font-semibold rounded-lg border transition hover:shadow-sm disabled:opacity-60 bg-white text-slate-600 border-slate-200 hover:bg-amber-50 hover:text-amber-700 hover:border-amber-200"
            >
              {thread.is_pinned ? (
                <>
                  <PinOff className="w-3.5 h-3.5 mr-1" /> Unpin
                </>
              ) : (
                <>
                  <Pin className="w-3.5 h-3.5 mr-1" /> Pin
                </>
              )}
            </button>
            <button
              onClick={() =>
                moderateMutation.mutate({ is_locked: !thread.is_locked })
              }
              disabled={moderateMutation.isPending}
              className="inline-flex items-center px-3 py-1.5 text-xs font-semibold rounded-lg border transition hover:shadow-sm disabled:opacity-60 bg-white text-slate-600 border-slate-200 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200"
            >
              {thread.is_locked ? (
                <>
                  <Unlock className="w-3.5 h-3.5 mr-1" /> Unlock
                </>
              ) : (
                <>
                  <Lock className="w-3.5 h-3.5 mr-1" /> Lock
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Locked banner */}
      {isLocked && (
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex items-center space-x-2 text-sm text-slate-600">
          <Lock className="w-4 h-4 text-slate-500 flex-shrink-0" />
          <span>This thread is locked. No new replies can be posted.</span>
        </div>
      )}

      {/* Replies section */}
      <div className="space-y-3">
        <h2 className="text-lg font-bold text-slate-900 flex items-center">
          <MessageSquare className="w-5 h-5 mr-2 text-indigo-600" />
          Replies ({thread.reply_count})
        </h2>

        {postTree.length === 0 ? (
          <div className="text-center py-10 bg-white rounded-2xl border border-slate-200/80 shadow-sm">
            <p className="text-sm text-slate-500">No replies yet. Be the first to respond!</p>
          </div>
        ) : (
          <div className="space-y-2">
            {postTree.map((node) => (
              <PostCard
                key={node.id}
                node={node}
                onReply={handleSetReplyTo}
                canReply={canReply}
                roleChip={roleChipClasses}
              />
            ))}
          </div>
        )}
      </div>

      {/* Reply box */}
      {canReply && (
        <div
          id="reply-box"
          className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm space-y-3"
        >
          <h3 className="text-sm font-bold text-slate-900">Post a Reply</h3>

          {replyParentId && (
            <div className="flex items-center space-x-2 text-xs bg-indigo-50 text-indigo-700 px-3 py-2 rounded-lg">
              <CornerDownRight className="w-3 h-3" />
              <span>
                Replying to <strong>{replyParentLabel}</strong>
              </span>
              <button
                onClick={() => {
                  setReplyParentId(null);
                  setReplyParentLabel(null);
                }}
                className="ml-auto text-indigo-500 hover:text-indigo-800"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <form onSubmit={handleReplySubmit} className="space-y-3">
            <textarea
              rows={4}
              maxLength={5000}
              value={replyBody}
              onChange={(e) => setReplyBody(e.target.value)}
              placeholder="Write your reply..."
              className="block w-full px-3.5 py-2.5 bg-slate-50/50 border border-slate-300 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition"
            />
            <div className="flex items-center justify-between">
              <p className="text-xs text-slate-400">{replyBody.length} / 5,000</p>
              <button
                type="submit"
                disabled={replyMutation.isPending || !replyBody.trim()}
                className="inline-flex items-center px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-sm rounded-xl shadow-sm disabled:opacity-60 transition"
              >
                {replyMutation.isPending ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                    <span>Posting...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4 mr-1.5" />
                    <span>Post Reply</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
