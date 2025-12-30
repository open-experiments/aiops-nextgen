import { useEffect, useRef, useState } from 'react';
import {
  PaperAirplaneIcon,
  PlusIcon,
  ChatBubbleLeftRightIcon,
  UserIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline';
import { Card } from '../../components/common/Card';
import { Spinner } from '../../components/common/Spinner';
import { useChatStore } from '../../store/chatStore';
import type { ChatMessage, ChatSession, Persona } from '../../types/chat';

export function Chat() {
  const {
    sessions,
    currentSession,
    messages,
    personas,
    selectedPersona,
    streaming,
    loading,
    fetchSessions,
    fetchPersonas,
    createSession,
    selectSession,
    sendMessage,
    setPersona,
  } = useChatStore();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchSessions();
    fetchPersonas();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || streaming) return;

    const message = input.trim();
    setInput('');
    await sendMessage(message);
  };

  const handleNewChat = async () => {
    await createSession();
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Sidebar with sessions */}
      <div className="hidden w-64 flex-shrink-0 flex-col lg:flex">
        <Card className="flex-1 overflow-hidden">
          <div className="flex h-full flex-col">
            <button
              onClick={handleNewChat}
              className="btn-primary mb-4 w-full"
            >
              <PlusIcon className="mr-2 h-4 w-4" />
              New Chat
            </button>

            <div className="flex-1 overflow-y-auto">
              <p className="mb-2 text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                Recent Sessions
              </p>
              <div className="space-y-1">
                {sessions.map((session) => (
                  <SessionItem
                    key={session.id}
                    session={session}
                    isActive={currentSession?.id === session.id}
                    onSelect={() => selectSession(session.id)}
                  />
                ))}
                {sessions.length === 0 && (
                  <p className="text-sm text-gray-400 dark:text-gray-500">
                    No chat sessions yet
                  </p>
                )}
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Main chat area */}
      <div className="flex flex-1 flex-col">
        {/* Persona selector */}
        {!currentSession && personas.length > 0 && (
          <div className="mb-4">
            <p className="mb-2 text-sm font-medium text-gray-700 dark:text-gray-300">
              Select an AI Assistant
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {personas.map((persona) => (
                <PersonaCard
                  key={persona.id}
                  persona={persona}
                  isSelected={selectedPersona?.id === persona.id}
                  onSelect={() => setPersona(persona)}
                />
              ))}
            </div>
          </div>
        )}

        {/* Messages area */}
        <Card className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4">
            {loading ? (
              <div className="flex h-full items-center justify-center">
                <Spinner size="lg" />
              </div>
            ) : messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <ChatBubbleLeftRightIcon className="mb-4 h-16 w-16 text-gray-300 dark:text-gray-600" />
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                  Start a conversation
                </h3>
                <p className="mt-1 max-w-sm text-sm text-gray-500 dark:text-gray-400">
                  Ask questions about your clusters, get help with troubleshooting,
                  or analyze GPU performance.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {messages.map((message) => (
                  <MessageBubble key={message.id} message={message} />
                ))}
                {streaming && (
                  <div className="flex items-center gap-2 text-gray-500">
                    <Spinner size="sm" />
                    <span className="text-sm">Thinking...</span>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Input area */}
          <div className="border-t border-gray-200 p-4 dark:border-gray-700">
            <form onSubmit={handleSubmit} className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question about your clusters..."
                className="input flex-1"
                disabled={streaming}
              />
              <button
                type="submit"
                disabled={!input.trim() || streaming}
                className="btn-primary px-4"
              >
                <PaperAirplaneIcon className="h-5 w-5" />
              </button>
            </form>
            {selectedPersona && (
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                Chatting with {selectedPersona.name}
              </p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function SessionItem({
  session,
  isActive,
  onSelect,
}: {
  session: ChatSession;
  isActive: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full rounded-lg p-2 text-left transition-colors ${
        isActive
          ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
          : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
      }`}
    >
      <p className="truncate text-sm font-medium">{session.title}</p>
      <p className="text-xs text-gray-500 dark:text-gray-400">
        {session.message_count} messages
      </p>
    </button>
  );
}

function PersonaCard({
  persona,
  isSelected,
  onSelect,
}: {
  persona: Persona;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`rounded-lg border p-4 text-left transition-all ${
        isSelected
          ? 'border-primary-500 bg-primary-50 dark:border-primary-400 dark:bg-primary-900/20'
          : 'border-gray-200 hover:border-gray-300 dark:border-gray-700 dark:hover:border-gray-600'
      }`}
    >
      <div className="mb-2 flex items-center gap-2">
        <span className="text-2xl">{persona.icon}</span>
        <h4 className="font-medium text-gray-900 dark:text-white">
          {persona.name}
        </h4>
      </div>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        {persona.description}
      </p>
      <div className="mt-2 flex flex-wrap gap-1">
        {persona.capabilities.slice(0, 3).map((cap) => (
          <span
            key={cap}
            className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-300"
          >
            {cap}
          </span>
        ))}
      </div>
    </button>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'USER';

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full ${
          isUser
            ? 'bg-primary-100 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400'
            : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
        }`}
      >
        {isUser ? (
          <UserIcon className="h-4 w-4" />
        ) : (
          <CpuChipIcon className="h-4 w-4" />
        )}
      </div>
      <div
        className={`max-w-[75%] rounded-lg px-4 py-2 ${
          isUser
            ? 'bg-primary-600 text-white'
            : 'bg-gray-100 text-gray-900 dark:bg-gray-700 dark:text-white'
        }`}
      >
        <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        {message.tokens_used && (
          <p
            className={`mt-1 text-xs ${
              isUser ? 'text-primary-200' : 'text-gray-500 dark:text-gray-400'
            }`}
          >
            {message.tokens_used} tokens · {message.latency_ms}ms
          </p>
        )}
      </div>
    </div>
  );
}
