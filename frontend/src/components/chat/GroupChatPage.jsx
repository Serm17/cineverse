import { useEffect, useRef, useState } from 'react';

import {
  addRecommendedMovies,
  deleteChatRoom,
  fetchChatRoomMessages,
  fetchCharacters,
  sendChat,
  sendRoomMessage,
} from '../../api.js';

import './chat.css';

// 배우대기실(menu2). /chat 과 /chat/group 을 한 페이지에서 다룬다.
// "멤버 추가하기" + 로 캐릭터를 고르고 — 1명이면 1:1(/chat), 2명 이상이면 그룹(/chat/group).
// 페이지 이동(새로고침) 없이 컴포넌트 상태로만 전환한다.
// 사이드바 아래 대화 내역은 대화한 캐릭터들의 이름을 제목으로 보여준다.
const STORAGE_KEY = 'cineverse.groupchat.conversations';
const AUTH_SESSION_KEY = 'cineverse.authSession';

const POSTER_BASE_URL =
  import.meta.env.VITE_TMDB_IMAGE_BASE_URL || 'https://image.tmdb.org/t/p/w500';

const QUICK_TABS = [
  ['오늘의 기분', null],
  ['장르 추천', null],
  ['자동추천', '내 취향대로 아무거나 골라줘'],
];

const MOOD_OPTIONS = [
  { emoji: '😊', label: '좋아요', prompt: '오늘 기분이 좋아! 신나는 영화 추천해줘' },
  { emoji: '😒', label: '시큰둥', prompt: '오늘 좀 시큰둥해... 그냥 볼만한 영화 없을까' },
  { emoji: '😔', label: '힘들다', prompt: '힘들다... 위로가 되는 영화 볼래' },
  { emoji: '🤔', label: '고민중', prompt: '뭘 볼지 고민되는데 추천해줘' },
  { emoji: '🤨', label: '의심반', prompt: '그냥 아무거나 재밌는 거 추천해줘' },
  { emoji: '😫', label: '지쳤어', prompt: '너무 지쳤어... 가볍게 볼 수 있는 영화 추천해줘' },
  { emoji: '😡', label: '화나요', prompt: '열받아 죽겠어! 스트레스 풀리는 영화 추천해줘' },
];

const GENRE_TAGS = ['액션', '드라마', '로맨스', 'SF', '공포', '코미디', '스릴러', '애니메이션'];

const MAX_COMPOSER_HEIGHT = 168;

const formatTime = (value) =>
  new Intl.DateTimeFormat('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false }).format(
    new Date(value)
  );

function readJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    return fallback;
  }
}

function readSessionConversations() {
  const stored = readJson(STORAGE_KEY, null);
  const sessionId = window.localStorage.getItem(AUTH_SESSION_KEY);

  if (!sessionId || stored?.sessionId !== sessionId) return [];
  return Array.isArray(stored.conversations) ? stored.conversations : [];
}

function orbGradient(seed) {
  const text = String(seed || 'AI');
  let hue = 0;
  for (let i = 0; i < text.length; i += 1) {
    hue = (hue * 31 + text.charCodeAt(i)) % 360;
  }
  return `radial-gradient(circle at 34% 28%, hsl(${hue} 70% 78%) 0%, hsl(${hue} 55% 48%) 24%, hsl(${hue} 60% 28%) 52%, hsl(${hue} 65% 12%) 100%)`;
}

function toPosterUrl(value) {
  const path = String(value || '').trim();
  if (!path) return '';
  if (/^(https?:|data:|blob:)/i.test(path)) return path;
  return `${POSTER_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

function getMoviePoster(movie) {
  return toPosterUrl(
    movie?.posterUrl ||
      movie?.poster_url ||
      movie?.poster_path ||
      movie?.poster ||
      movie?.image_url ||
      movie?.image ||
      ''
  );
}

function normalizeName(value) {
  return String(value || '').trim();
}

function getCharacterFromList(name, characters) {
  const normalized = normalizeName(name);
  return characters.find((character) => normalizeName(character.name) === normalized) || null;
}

function createMember(name, characters = []) {
  const normalized = normalizeName(name);
  const character = getCharacterFromList(normalized, characters);

  return {
    id: character?.id || normalized,
    name: normalized,
    image: character?.image || '',
  };
}

function hydrateMembers(members, characters) {
  return (members || [])
    .map((member) => createMember(member?.name || member, characters))
    .filter((member) => member.name);
}

function getMessageMovies(message) {
  const movies = message?.recommended_movies ?? message?.movies ?? message?.movie ?? [];
  return Array.isArray(movies) ? movies : [];
}

// 서버 방(room) 메시지를 이 페이지의 메시지 형태로 변환한다.
function mapRoomMessages(roomId, roomMessages) {
  return (roomMessages || []).map((message, index) => ({
    id: `room-${roomId}-${index}`,
    role: message.role === 'assistant' ? 'assistant' : 'user',
    content: message.content || message.answer || '',
    character: message.role === 'assistant' ? message.character || 'AI' : '',
    createdAt: message.created_at || message.createdAt || new Date().toISOString(),
    movies: getMessageMovies(message),
  }));
}

function normalizeCharacter(rawCharacter, index) {
  const name = String(rawCharacter?.name || rawCharacter?.character || '').trim();
  if (!name) return null;

  return {
    id: String(rawCharacter?.id ?? rawCharacter?.character_id ?? name ?? index),
    name,
    image: rawCharacter?.image || rawCharacter?.image_url || rawCharacter?.avatar_url || '',
  };
}

function GroupChatPage() {
  const [characters, setCharacters] = useState([]);
  const [characterLoadError, setCharacterLoadError] = useState('');

  // 대화 내역: 각 대화는 멤버(캐릭터들)를 갖고, 제목은 멤버 이름들이다.
  const [conversations, setConversations] = useState(readSessionConversations);
  const [activeId, setActiveId] = useState('');

  const [isPickerOpen, setPickerOpen] = useState(false);
  const [pickedIds, setPickedIds] = useState([]);

  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('');
  const [activePicker, setActivePicker] = useState(null);

  const messagesRef = useRef(null);
  const textareaRef = useRef(null);
  const quickPickerRef = useRef(null);
  const composingRef = useRef(false);
  const abortRef = useRef(null);
  const stickToBottomRef = useRef(true);
  const loadedRoomIdsRef = useRef(new Set());

  useEffect(() => {
    const controller = new AbortController();

    fetchCharacters(controller.signal)
      .then((data) => {
        const list = Array.isArray(data)
          ? data
          : Array.isArray(data?.data)
            ? data.data
            : Array.isArray(data?.characters)
              ? data.characters
              : [];

        const dbCharacters = list.map(normalizeCharacter).filter(Boolean);
        setCharacters(dbCharacters);
        setCharacterLoadError(dbCharacters.length === 0 ? 'DB에 캐릭터 데이터가 없습니다.' : '');
      })
      .catch((fetchError) => {
        if (fetchError.name === 'AbortError') return;
        setCharacterLoadError(fetchError.message);
        setCharacters([]);
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    const sessionId = window.localStorage.getItem(AUTH_SESSION_KEY);
    if (!sessionId) return;

    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ sessionId, conversations })
    );
  }, [conversations]);

  useEffect(() => {
    if (characters.length === 0) return;

    setConversations((current) =>
      current.map((conversation) => ({
        ...conversation,
        members: hydrateMembers(conversation.members, characters),
      }))
    );
  }, [characters]);

  // 마이페이지 등에서 ?room=<id>&members=<이름들> 로 들어오면 그 방 대화를 이어서 연다.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const roomParam = params.get('room');

    // room 파라미터가 없으면, 저장된 대화가 있을 때 첫 대화를 자동 선택한다(재방문 시 빈 화면 방지).
    if (!roomParam) {
      const stored = readSessionConversations();
      if (stored.length > 0) {
        setActiveId((current) => current || stored[0].id);
      }
      return;
    }

    const memberNames = (params.get('members') || '')
      .split(',')
      .map((name) => name.trim())
      .filter(Boolean);

    const stored = readSessionConversations();
    const existing = stored.find((c) => String(c.roomId) === String(roomParam));

    if (existing) {
      setActiveId(existing.id);
    } else {
      const conversation = {
        id: crypto.randomUUID(),
        title: memberNames.join(', ') || '그룹 대화',
        members: memberNames.map((name) => createMember(name, characters)),
        roomId: String(roomParam),
        createdAt: new Date().toISOString(),
        messages: [],
      };
      setConversations((current) => [conversation, ...current]);
      setActiveId(conversation.id);
    }
  }, []);

  const activeConversation = conversations.find((c) => c.id === activeId) || null;
  const messages = activeConversation?.messages || [];
  const members = activeConversation?.members || [];
  const canChat = Boolean(activeConversation);

  const activeName = members.map((m) => m.name).join(', ') || '멤버를 추가해보세요';
  const activeSubText =
    members.length > 1
      ? `${members.length}명 그룹 대화 · AI 대화`
      : members.length === 1
        ? '영화 속 캐릭터 · AI 대화'
        : '멤버를 추가하면 대화가 시작됩니다';

  // 이름으로 캐릭터 이미지를 찾아 아바타에 쓴다(없으면 색상 그라디언트).
  const findImage = (name, fallbackMembers = members) =>
    getCharacterFromList(name, characters)?.image ||
    hydrateMembers(fallbackMembers, characters).find(
      (member) => normalizeName(member.name) === normalizeName(name)
    )?.image ||
    '';

  useEffect(() => {
    const roomId = activeConversation?.roomId;
    if (!roomId || loadedRoomIdsRef.current.has(String(roomId))) return;

    loadedRoomIdsRef.current.add(String(roomId));
    const controller = new AbortController();

    fetchChatRoomMessages(roomId, controller.signal)
      .then((roomMessages) => {
        if (controller.signal.aborted) return;

        updateConversation(activeConversation.id, (conversation) => ({
          ...conversation,
          messages: mapRoomMessages(roomId, roomMessages),
        }));
      })
      .catch((fetchError) => {
        if (fetchError.name === 'AbortError') return;
        loadedRoomIdsRef.current.delete(String(roomId));
        setError(fetchError.message);
      });

    return () => controller.abort();
  }, [activeConversation?.id, activeConversation?.roomId]);

  const resizeTextarea = (textarea) => {
    if (!textarea) return;
    textarea.style.height = 'auto';
    const nextHeight = Math.min(textarea.scrollHeight, MAX_COMPOSER_HEIGHT);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > MAX_COMPOSER_HEIGHT ? 'auto' : 'hidden';
  };

  useEffect(() => {
    const el = messagesRef.current;
    if (!el) return undefined;
    const handleScroll = () => {
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickToBottomRef.current = distanceFromBottom < 80;
    };
    el.addEventListener('scroll', handleScroll);
    return () => el.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    const el = messagesRef.current;
    if (!el || !stickToBottomRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, activeId]);

  useEffect(() => {
    resizeTextarea(textareaRef.current);
  }, [input]);

  useEffect(() => {
    if (!activePicker) return;
    const picker = quickPickerRef.current;
    if (!picker) return;
    picker.style.display = 'none';
    void picker.offsetHeight;
    picker.style.display = '';
  }, [activePicker]);

  const updateConversation = (id, updater) => {
    setConversations((current) => current.map((c) => (c.id === id ? updater(c) : c)));
  };

  const togglePicker = () => {
    setPickerOpen((current) => !current);
    setPickedIds([]);
  };

  // 대화 삭제: 서버 방이 있으면 삭제(DELETE /chat/rooms/{id})하고 로컬 리스트에서도 제거.
  const handleDeleteConversation = async (conversation) => {
    if (conversation.roomId) {
      try {
        await deleteChatRoom(conversation.roomId);
      } catch (deleteError) {
        setError(deleteError.message);
        return;
      }
    }

    setConversations((current) => current.filter((c) => c.id !== conversation.id));
    setActiveId((current) => {
      if (current !== conversation.id) return current;
      const remaining = conversations.filter((c) => c.id !== conversation.id);
      return remaining[0]?.id || '';
    });
  };

  const togglePick = (id) => {
    setPickedIds((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id]
    );
  };

  // 완료: 고른 멤버들로 새 대화를 만든다(1명=1:1, 2명 이상=그룹). 제목은 멤버 이름들.
  const confirmPicker = () => {
    const pickedMembers = pickedIds
      .map((id) => characters.find((c) => c.id === id))
      .filter(Boolean)
      .map((c) => ({ id: c.id, name: c.name, image: c.image }));

    if (pickedMembers.length === 0) return;

    const conversation = {
      id: crypto.randomUUID(),
      title: pickedMembers.map((m) => m.name).join(', '),
      members: pickedMembers,
      roomId: '',
      createdAt: new Date().toISOString(),
      messages: [],
    };

    setConversations((current) => [conversation, ...current]);
    setActiveId(conversation.id);
    setPickerOpen(false);
    setPickedIds([]);
    setInput('');
    setError('');
    stickToBottomRef.current = true;
  };

  const updateMessage = (conversationId, messageId, updater) => {
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      messages: conversation.messages.map((m) => (m.id === messageId ? updater(m) : m)),
    }));
  };

  const sendMessage = async () => {
    const content = input.trim();
    if (!content || busy || !activeConversation) return;

    const conversationId = activeConversation.id;
    const roomId = activeConversation.roomId;
    const memberNames = members.map((m) => m.name);
    const isGroup = members.length > 1;
    const pendingId = `pending-${crypto.randomUUID()}`;
    const createdAt = new Date().toISOString();

    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      messages: [
        ...conversation.messages,
        { id: crypto.randomUUID(), role: 'user', content, createdAt },
        {
          id: pendingId,
          role: 'assistant',
          content: '',
          character: isGroup ? memberNames.join(', ') : memberNames[0],
          createdAt,
          pending: true,
        },
      ],
    }));

    setInput('');
    setError('');
    setBusy(true);
    stickToBottomRef.current = true;

    const controller = new AbortController();
    abortRef.current = controller;

    const handleStreamChunk = (partialAnswer, payload) => {
      updateMessage(conversationId, pendingId, (message) => ({
        ...message,
        content: partialAnswer,
        character:
          normalizeName(payload?.character || payload?.data?.character) ||
          message.character,
        pending: false,
      }));
    };

    try {
      // 이어 대화는 방 기준, 새 대화는 멤버 수에 따라 1:1(/chat) vs 그룹(/chat/group).
      const response = isGroup
        ? await sendChat(
            { mode: 'group', characters: memberNames, message: content },
            controller.signal
          )
        : roomId
          ? await sendRoomMessage(
              roomId,
              { message: content, character: memberNames[0] },
              controller.signal,
              handleStreamChunk
            )
          : await sendChat(
              { message: content, character: memberNames[0] },
              controller.signal,
              handleStreamChunk
            );

      if (response?.conversationId) {
        loadedRoomIdsRef.current.add(String(response.conversationId));
        updateConversation(conversationId, (conversation) => ({
          ...conversation,
          roomId: response.conversationId,
        }));
      }

      // 그룹 응답은 라운드별 여러 캐릭터 답변 → 각 답변을 개별 말풍선으로 펼친다.
      // 백엔드가 rounds 대신 rouds를 내려도 api.js에서 response.rounds로 맞춰준다.
      const rounds = Array.isArray(response?.rounds) ? response.rounds : [];
      const replyMessages = [];

      rounds.forEach((round) => {
        const responses = Array.isArray(round?.responses) ? round.responses : [];
        const roundLabel =
          round?.label ||
          (round?.round ? `round ${round.round}` : response?.intent || '');

        responses.forEach((reply) => {
          const character =
            normalizeName(reply?.character || reply?.name) ||
            memberNames[replyMessages.length % memberNames.length] ||
            'AI';

          replyMessages.push({
            id: crypto.randomUUID(),
            role: 'assistant',
            character,
            content: reply?.answer || reply?.content || reply?.message || '',
            createdAt,
            intent: roundLabel,
            movies: [],
          });
        });
      });

      if (replyMessages.length === 0) {
        replyMessages.push({
          id: crypto.randomUUID(),
          role: 'assistant',
          character: isGroup ? 'AI' : memberNames[0] || response?.character || 'AI',
          content: response?.answer || '응답 내용이 없습니다.',
          intent: response?.intent,
          createdAt,
          movies: response?.movies || [],
        });
      } else if (response?.movies?.length) {
        replyMessages[replyMessages.length - 1].movies = response.movies;
      }

      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        messages: [
          ...conversation.messages.filter((m) => m.id !== pendingId),
          ...replyMessages,
        ],
      }));

      // 추천받은 영화를 마이페이지 추천과 잇기 위해 저장한다.
      addRecommendedMovies(response?.movies || []);
    } catch (requestError) {
      const aborted = requestError.name === 'AbortError';
      const errorMessage = aborted ? '응답을 중단했습니다.' : requestError.message;
      setError(aborted ? '' : errorMessage);

      updateMessage(conversationId, pendingId, (message) => ({
        ...message,
        content: message.content || errorMessage,
        pending: false,
        error: !aborted,
      }));
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  };

  const clearMessages = () => {
    if (!activeConversation) return;
    abortRef.current?.abort();
    updateConversation(activeConversation.id, (conversation) => ({
      ...conversation,
      roomId: '',
      messages: [],
    }));
    setInput('');
    setError('');
    setBusy(false);
  };

  const canSend = Boolean(input.trim() && canChat && !busy);
  const statusText = busy ? 'AI가 답변 중입니다.' : error || characterLoadError || '';

  const micIcon = (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 15a3.5 3.5 0 0 0 3.5-3.5v-5a3.5 3.5 0 0 0-7 0v5A3.5 3.5 0 0 0 12 15Z" />
      <path d="M18.5 11.5a6.5 6.5 0 0 1-13 0M12 18v3M9 21h6" />
    </svg>
  );

  const stopIcon = (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="7" y="7" width="10" height="10" rx="2" />
    </svg>
  );

  const topbarAvatarImage = members[0] ? findImage(members[0].name) : '';

  return (
    <main className="chat-page" aria-label="배우대기실">
      <div className="chat-layout">
        {/* 좌측: 멤버 추가하기 + 대화 내역 */}
        <aside className="chat-sidebar">
          <div className="chat-sidebar__head">
            <span>멤버 추가하기</span>
            <button
              type="button"
              className={`chat-sidebar__new ${isPickerOpen ? 'chat-sidebar__new--active' : ''}`}
              onClick={togglePicker}
              title="멤버 선택 (1명=1:1, 2명 이상=그룹)"
              aria-label="멤버 추가"
              aria-expanded={isPickerOpen}
            >
              +
            </button>
          </div>

          <div className="chat-charlist">
            {isPickerOpen ? (
              <div className="chat-partner-picker chat-partner-picker--open">
                <div className="chat-partner-picker__inner">
                  <p className="chat-partner-picker__label">
                    멤버 선택 · 1명이면 1:1, 2명 이상이면 그룹 대화
                  </p>

                  {characters.map((character) => (
                    <button
                      type="button"
                      key={character.id}
                      className={`chat-charitem ${
                        pickedIds.includes(character.id) ? 'chat-charitem--active' : ''
                      }`}
                      onClick={() => togglePick(character.id)}
                    >
                      <span
                        className="chat-charitem__avatar"
                        style={character.image ? undefined : { background: orbGradient(character.name) }}
                      >
                        {character.image ? <img src={character.image} alt="" /> : null}
                      </span>
                      <span className="chat-charitem__body">
                        <span className="chat-charitem__name">{character.name}</span>
                        <span className="chat-charitem__desc">
                          {pickedIds.includes(character.id) ? '선택됨' : '영화 속 캐릭터'}
                        </span>
                      </span>
                    </button>
                  ))}

                  <button
                    type="button"
                    className="chat-picker-done"
                    onClick={confirmPicker}
                    disabled={pickedIds.length === 0}
                  >
                    완료 ({pickedIds.length}명 선택
                    {pickedIds.length >= 2 ? ' · 그룹' : pickedIds.length === 1 ? ' · 1:1' : ''})
                  </button>
                </div>
              </div>
            ) : conversations.length > 0 ? (
              conversations.map((conversation) => {
                const firstMember = conversation.members?.[0];
                const conversationImage = firstMember
                  ? findImage(firstMember.name, conversation.members)
                  : '';

                return (
                  <div className="chat-conv-row" key={conversation.id}>
                    <button
                      type="button"
                      className={`chat-charitem ${
                        conversation.id === activeId ? 'chat-charitem--active' : ''
                      }`}
                      onClick={() => setActiveId(conversation.id)}
                      disabled={busy}
                    >
                      <span
                        className="chat-charitem__avatar"
                        style={
                          conversationImage
                            ? undefined
                            : { background: orbGradient(conversation.title) }
                        }
                      >
                        {conversationImage ? <img src={conversationImage} alt="" /> : null}
                      </span>
                      <span className="chat-charitem__body">
                        <span className="chat-charitem__name">{conversation.title}</span>
                        <span className="chat-charitem__desc">
                          {conversation.members.length > 1 ? '그룹 대화' : '1:1 대화'}
                        </span>
                      </span>
                    </button>

                    <button
                      type="button"
                      className="chat-conv-del"
                      onClick={() => handleDeleteConversation(conversation)}
                      title="대화 삭제"
                      aria-label="대화 삭제"
                    >
                      ✕
                    </button>
                  </div>
                );
              })
            ) : (
              <p className="chat-charlist__empty">
                {characterLoadError || '+ 버튼으로 멤버를 추가해 대화를 시작해보세요'}
              </p>
            )}
          </div>
        </aside>

        {/* 우측: 대화 패널 */}
        <section className="chat-panel">
          <header className="chat-topbar">
            <span
              className="chat-topbar__avatar"
              style={topbarAvatarImage ? undefined : { background: orbGradient(activeName) }}
            >
              {topbarAvatarImage ? <img src={topbarAvatarImage} alt="" /> : null}
            </span>
            <div className="chat-topbar__info">
              <div className="chat-topbar__nameline">
                <strong>{activeName}</strong>
                {canChat ? (
                  <>
                    <span className="chat-topbar__dot" />
                    <span className="chat-topbar__status">온라인</span>
                  </>
                ) : null}
              </div>
              <div className="chat-topbar__sub">{activeSubText}</div>
            </div>
            <div className="chat-topbar__actions">
              <button type="button" className="chat-chip chat-chip--danger" onClick={clearMessages}>
                대화 초기화
              </button>
            </div>
          </header>

          <section className="chat-messages" ref={messagesRef} aria-live="polite">
            {messages.length === 0 ? (
              <div className="chat-empty">
                <p>
                  {canChat
                    ? `${activeName}와(과) 대화를 시작해보세요`
                    : '+ 버튼으로 멤버를 추가해보세요'}
                </p>
              </div>
            ) : (
              <>
                <div className="chat-divider">
                  <span>오늘</span>
                </div>

                {messages.map((message) => {
                  const isUser = message.role === 'user';
                  const avatarImage = !isUser ? findImage(message.character) : '';

                  return (
                    <article
                      key={message.id}
                      className={`chat-msg chat-msg--${message.role} ${
                        message.error ? 'chat-msg--error' : ''
                      }`}
                    >
                      {!isUser ? (
                        <span
                          className="chat-msg__avatar"
                          style={
                            avatarImage
                              ? undefined
                              : { background: orbGradient(message.character || activeName) }
                          }
                        >
                          {avatarImage ? <img src={avatarImage} alt="" /> : null}
                        </span>
                      ) : null}

                      <div className="chat-msg__col">
                        <div className="chat-msg__meta">
                          <strong>{isUser ? '나' : message.character || 'AI'}</strong>
                          {message.intent ? (
                            <span className="chat-msg__intent">{message.intent}</span>
                          ) : null}
                          <time>{formatTime(message.createdAt)}</time>
                        </div>

                        {message.pending ? (
                          <div className="chat-typing">
                            <span />
                            <span />
                            <span />
                          </div>
                        ) : (
                          <>
                            <div className="chat-msg__bubble">
                              {message.content || '답변을 기다리는 중...'}
                            </div>

                            {message.movies?.length > 0 ? (
                              <div className="chat-movies-row">
                                {message.movies.map((movie, index) => {
                                  const title = movie.title || movie.name || '추천작';
                                  const meta = [movie.year, movie.genre].filter(Boolean).join(' · ');
                                  const rating = movie.rating ?? movie.score;
                                  const poster = getMoviePoster(movie);

                                  return (
                                    <div className="chat-movie" key={movie.id || movie.title || index}>
                                      <div
                                        className="chat-movie__poster"
                                        style={poster ? { backgroundImage: `url(${poster})` } : undefined}
                                      >
                                      </div>
                                      <div className="chat-movie__body">
                                        <div className="chat-movie__title">{title}</div>
                                        {meta ? <div className="chat-movie__meta">{meta}</div> : null}
                                        {rating != null ? (
                                          <div className="chat-movie__rating">
                                            <span>★</span>
                                            {rating}
                                          </div>
                                        ) : null}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            ) : null}
                          </>
                        )}
                      </div>
                    </article>
                  );
                })}
              </>
            )}
          </section>

          <div className="chat-composer-wrap">
            <div className="chat-tabs">
              {QUICK_TABS.map(([label, prompt]) => (
                <button
                  key={label}
                  type="button"
                  className={`chat-tab ${activeTab === label ? 'chat-tab--active' : ''}`}
                  onClick={() => {
                    setActiveTab(label);
                    if (label === '오늘의 기분') {
                      setActivePicker((current) => (current === 'mood' ? null : 'mood'));
                      return;
                    }
                    if (label === '장르 추천') {
                      setActivePicker((current) => (current === 'genre' ? null : 'genre'));
                      return;
                    }
                    setActivePicker(null);
                    setInput(prompt);
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            <div
              ref={quickPickerRef}
              className={`chat-picker ${activePicker ? 'chat-picker--open' : ''}`}
            >
              <div className="chat-picker__inner">
                {activePicker === 'mood' ? (
                  <div className="chat-mood-grid">
                    {MOOD_OPTIONS.map((mood) => (
                      <button
                        key={mood.emoji}
                        type="button"
                        className="chat-mood-btn"
                        onClick={() => {
                          setInput(mood.prompt);
                          setActivePicker(null);
                        }}
                      >
                        <span className="chat-mood-btn__emoji">{mood.emoji}</span>
                        <span className="chat-mood-btn__label">{mood.label}</span>
                      </button>
                    ))}
                  </div>
                ) : null}

                {activePicker === 'genre' ? (
                  <div className="chat-genre-grid">
                    {GENRE_TAGS.map((genre) => (
                      <button
                        key={genre}
                        type="button"
                        className="chat-genre-tag"
                        onClick={() => {
                          setInput(`#${genre} 영화 추천해줘`);
                          setActivePicker(null);
                        }}
                      >
                        #{genre}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>

            <form
              className="chat-composer"
              onSubmit={(event) => {
                event.preventDefault();
                sendMessage();
              }}
            >
              <div className="chat-inputbox">
                <button type="button" className="chat-attach" title="파일 첨부" aria-label="파일 첨부">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <rect x="3" y="4" width="18" height="16" rx="3" />
                    <circle cx="8.5" cy="9.5" r="1.6" />
                    <path d="M5 18l5-5 4 4 3-3 2 2" />
                  </svg>
                </button>

                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(event) => {
                    setInput(event.target.value);
                    resizeTextarea(event.target);
                  }}
                  onCompositionStart={() => {
                    composingRef.current = true;
                  }}
                  onCompositionEnd={(event) => {
                    composingRef.current = false;
                    setInput(event.currentTarget.value);
                    resizeTextarea(event.currentTarget);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      if (
                        event.nativeEvent.isComposing ||
                        composingRef.current ||
                        event.keyCode === 229
                      ) {
                        return;
                      }
                      event.preventDefault();
                      sendMessage();
                    }
                  }}
                  rows={1}
                  maxLength={1000}
                  placeholder={canChat ? `${activeName}에게 메시지 보내기` : '+ 버튼으로 멤버를 추가해보세요'}
                  aria-label="메시지"
                  disabled={busy || !canChat}
                />

                <button
                  className="chat-enter"
                  type="button"
                  onClick={() => (busy ? abortRef.current?.abort() : sendMessage())}
                  disabled={!busy && !canSend}
                  title={busy ? '응답 중단' : '메시지 보내기 (Enter)'}
                  aria-label={busy ? '응답 중단' : '메시지 보내기'}
                >
                  {busy ? (
                    stopIcon
                  ) : (
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M20 6v5a3 3 0 0 1-3 3H5" />
                      <path d="M9 10l-4 4 4 4" />
                    </svg>
                  )}
                </button>
              </div>

              <button className="chat-send" type="button" aria-label="음성으로 입력">
                {micIcon}
              </button>
            </form>

            {statusText ? <p className="chat-status">{statusText}</p> : null}

            <p className="chat-disclaimer">AI가 생성한 응답으로, 실제 정보와 다를 수 있어요.</p>
          </div>
        </section>
      </div>
    </main>
  );
}

export default GroupChatPage;
