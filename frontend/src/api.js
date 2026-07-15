// refresh cookie의 host/path가 실제 API 요청과 일치하도록 기본값은 백엔드에 직접 연결한다.
// 다른 환경에서는 VITE_API_BASE_URL로 전체 API 주소를 지정한다.
const BACKEND_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8080'
).replace(/\/+$/, '');

const LOCAL_PROFILE_KEY = 'cineverse.localProfile';
const LOCAL_PREFERENCES_KEY = 'cineverse.localPreferences';
const AUTH_SESSION_KEY = 'cineverse.authSession';

// AI/캐릭터 채팅에서 추천받은 영화를 마이페이지 추천과 잇기 위해 저장하는 키.
const RECOMMENDED_MOVIES_KEY = 'cineverse.recommendedMovies';
const MAX_RECOMMENDED_MOVIES = 30;

// 로그아웃/다른 사용자 로그인 시 비워야 하는, 브라우저에 남는 대화 로그/캐시 키.
const CHAT_CACHE_KEYS = [
  'cineverse.autochat.conversations', // 매표소(CineBuddy) 대화 리스트
  'cineverse.groupchat.conversations', // 배우대기실 대화 리스트
  'cineverse.chat.rooms', // (구) 1:1 채팅방 매핑
  'cineverse.chat.partners', // (구) 대화 상대 목록
  'cineverse.chat.group.members', // (구) 그룹 멤버 목록
  RECOMMENDED_MOVIES_KEY, // 채팅에서 추천받은 영화 목록
];
const ACCOUNT_CACHE_KEYS = [LOCAL_PROFILE_KEY, LOCAL_PREFERENCES_KEY];

function clearChatCaches() {
  CHAT_CACHE_KEYS.forEach((key) => localStorage.removeItem(key));
}

function clearAccountCaches() {
  ACCOUNT_CACHE_KEYS.forEach((key) => localStorage.removeItem(key));
}

// 채팅 응답의 추천 영화들을 최근순으로 누적 저장한다(중복 제거, 최대 개수 제한).
export function addRecommendedMovies(movies) {
  if (!Array.isArray(movies) || movies.length === 0) return;

  const existing = readLocalJson(RECOMMENDED_MOVIES_KEY, []);
  const byKey = new Map();

  // 새로 추천된 영화가 앞으로 오도록 new → old 순서로 넣고, 먼저 들어온 것만 유지.
  [...movies, ...(Array.isArray(existing) ? existing : [])].forEach((movie) => {
    if (!movie) return;
    const key = String(movie.id ?? movie.movie_id ?? movie.title ?? movie.name ?? '');
    if (!key || byKey.has(key)) return;
    byKey.set(key, movie);
  });

  writeLocalJson(
    RECOMMENDED_MOVIES_KEY,
    Array.from(byKey.values()).slice(0, MAX_RECOMMENDED_MOVIES)
  );
}

export function getRecommendedMovies() {
  const stored = readLocalJson(RECOMMENDED_MOVIES_KEY, []);
  return Array.isArray(stored) ? stored : [];
}

const FALLBACK_GENRES = [
  '액션',
  '드라마',
  '로맨스',
  'SF',
  '공포',
  '코미디',
  '스릴러',
  '애니메이션',
];
const TMDB_IMAGE_BASE_URL =
  import.meta.env.VITE_TMDB_IMAGE_BASE_URL || 'https://image.tmdb.org/t/p/w500';

export function resolveMovieImage(path) {
  const value = String(path || '').trim();

  if (!value) return '';
  if (/^(https?:|data:|blob:)/i.test(value)) return value;

  return `${TMDB_IMAGE_BASE_URL}${value.startsWith('/') ? value : `/${value}`}`;
}

function readLocalJson(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    console.error('로컬 데이터 파싱 실패:', error);
    return fallback;
  }
}

function writeLocalJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function getArrayPayload(data, ...keys) {
  if (Array.isArray(data)) return data;

  for (const key of keys) {
    if (Array.isArray(data?.[key])) return data[key];
    if (Array.isArray(data?.data?.[key])) return data.data[key];
  }

  if (Array.isArray(data?.data)) return data.data;
  return [];
}

function getErrorMessage(data, fallbackMessage) {
  const validationMessage = Array.isArray(data?.detail)
    ? data.detail.map((item) => item?.msg).filter(Boolean).join(', ')
    : '';
  const detailMessage = typeof data?.detail === 'string' ? data.detail : '';

  return (
    data?.detail?.message ||
    data?.detail?.error ||
    data?.detail?.detail ||
    validationMessage ||
    detailMessage ||
    data?.message ||
    // 백엔드 응답 필드 오타(messaage/messsage) 대응 — 프론트는 message로 통일해서 읽는다.
    data?.messaage ||
    data?.messsage ||
    data?.error ||
    fallbackMessage
  );
}

// 일부 에러 응답은 state 대신 status로 오므로 둘 다 확인한다.
function getResponseState(data) {
  return data?.detail?.state ?? data?.detail?.status ?? data?.state ?? data?.status;
}

function isFailureResponse(data) {
  return ['failure', 'fail', 'error'].includes(getResponseState(data));
}

function clampNumber(value, min, max, fallback) {
  const number = Number(value);

  if (!Number.isFinite(number)) return fallback;

  return Math.min(max, Math.max(min, number));
}

let refreshPromise = null;

export async function fetchWithAuth(url, options = {}, allowRefreshRetry = true) {
  const token = localStorage.getItem('access_token');
  const headers = { ...(options.headers || {}) };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    // /auth, /chat, /user 응답은 캐시하지 않는다(백엔드 no-store 헤더와 맞춤). 호출부가 지정하면 그 값 우선.
    cache: 'no-store',
    credentials: 'include',
    ...options,
    headers,
  });

  // 명세의 ACCESS_TOKEN_EXPIRED인 401에서만 재발급 후 원 요청을 1회 재시도한다.
  if (response.status === 401 && token) {
    const errorBody = await response.clone().json().catch(() => null);
    const errorCode = errorBody?.detail?.code ?? errorBody?.code;

    if (errorCode !== 'ACCESS_TOKEN_EXPIRED' || !allowRefreshRetry) {
      if (
        [
          'INVALID_ACCESS_TOKEN',
          'INVALID_TOKEN_TYPE',
          'INVALID_TOKEN_PAYLOAD',
          'INVALID_AUTH_SCHEME',
        ].includes(errorCode)
      ) {
        clearStoredAuth();
      }
      return response;
    }

    try {
      await refreshAccessToken();
    } catch (refreshError) {
      return response;
    }

    return fetchWithAuth(url, options, false);
  }

  return response;
}

async function performAccessTokenRefresh() {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    clearStoredAuth();
    throw new Error(getErrorMessage(data, `토큰 재발급 실패 (${response.status})`));
  }

  const authData = data?.data || {};

  if (!authData.access_token) {
    clearStoredAuth();
    throw new Error('토큰 재발급 응답에 access_token이 없습니다.');
  }

  localStorage.setItem('access_token', authData.access_token);

  const storedUser = getStoredAuthUser() || {};
  const user = {
    ...storedUser,
    email: authData.email || storedUser.email || '',
    nickname:
      authData.nickname ||
      storedUser.nickname ||
      authData.email ||
      storedUser.email ||
      '',
    tokenType: authData.token_type || storedUser.tokenType || 'bearer',
  };

  localStorage.setItem('auth_user', JSON.stringify(user));

  return user;
}

// 동시에 여러 요청이 만료되어도 refresh 요청은 하나만 수행한다.
export async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = performAccessTokenRefresh().finally(() => {
      refreshPromise = null;
    });
  }

  return refreshPromise;
}

export function getStoredAuthUser() {
  try {
    const rawUser = localStorage.getItem('auth_user');

    if (!rawUser) return null;

    return JSON.parse(rawUser);
  } catch (error) {
    console.error('저장된 로그인 정보 파싱 실패:', error);
    return null;
  }
}

export function clearStoredAuth() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('auth_user');
  localStorage.removeItem(AUTH_SESSION_KEY);
  // 로그아웃 시 브라우저에 남는 대화 로그/캐시도 함께 삭제한다.
  clearChatCaches();
  clearAccountCaches();
}

function storeAuthSession({ accessToken, email, nickname, tokenType }) {
  // 다른 사용자가 로그인하면 이전 사용자의 로컬 대화 캐시를 비운다(이전 채팅 노출 방지).
  const previousUser = getStoredAuthUser();
  if (!previousUser || previousUser.email !== email) {
    clearChatCaches();
    clearAccountCaches();
  }

  const user = {
    email,
    nickname: nickname || email,
    tokenType: tokenType || 'bearer',
  };

  localStorage.setItem('access_token', accessToken);
  localStorage.setItem('auth_user', JSON.stringify(user));
  localStorage.setItem(AUTH_SESSION_KEY, crypto.randomUUID());

  return user;
}

export async function loginWithEmail({ email, password }, signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/login`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
    signal,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `로그인 실패 (${response.status})`));
  }

  const authData = data?.data || {};

  if (!authData.access_token) {
    throw new Error('로그인 응답에 access_token이 없습니다.');
  }

  return storeAuthSession({
    accessToken: authData.access_token,
    email: authData.email || email,
    nickname: authData.nickname || authData.email || email,
    tokenType: authData.token_type,
  });
}

export async function requestEmailVerification(email, signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/email-verification/request`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `인증번호 전송 실패 (${response.status})`));
  }

  return data?.data || {};
}

export async function registerWithEmail(
  { email, password, nickname, verificationCode, verification_code },
  signal
) {
  const code = verificationCode ?? verification_code;
  const response = await fetch(`${BACKEND_BASE_URL}/auth/register`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      nickname,
      verification_code: code,
    }),
    signal,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `회원가입 실패 (${response.status})`));
  }

  return data?.data || null;
}

export async function requestPasswordReset(email, signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/password-reset/request`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `비밀번호 재설정 요청 실패 (${response.status})`));
  }

  return data || {};
}

export async function confirmPasswordReset(token, newPassword, signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/password-reset/confirm`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `비밀번호 변경 실패 (${response.status})`));
  }

  return data || {};
}

export async function logoutUser(signal) {
  try {
    const response = await fetchWithAuth(`${BACKEND_BASE_URL}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
      signal,
    });

    const data = await response.json().catch(() => null);

    if (!response.ok || getResponseState(data) !== 'success') {
      throw new Error(getErrorMessage(data, `로그아웃 실패 (${response.status})`));
    }

    return data;
  } finally {
    // 서버 로그아웃 성공 여부와 무관하게 프론트 access token과 사용자 캐시는 제거한다.
    clearStoredAuth();
  }
}

export async function checkBackendHealth(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/health`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `백엔드 연결 실패 (${response.status})`));
  }

  return data;
}

export async function checkApiStatus(signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/`, {
    credentials: 'include',
    cache: 'no-store',
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `API 연결 실패 (${response.status})`));
  }

  return data;
}

export async function checkAiHealth(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/ai-health`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `AI 서버 연결 실패 (${response.status})`));
  }

  return data;
}

export async function checkDbHealth(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/db-test`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) !== 'success') {
    throw new Error(getErrorMessage(data, `DB 연결 실패 (${response.status})`));
  }

  return data;
}

function normalizeChatResponse(json, request) {
  const payload = json?.state === 'success' && json?.data ? json.data : json || {};
  const roomId = payload.room_id ?? payload.roomId ?? payload.conversationId;
  // 백엔드 응답 키가 rounds/rouds/roud 로 제각각이라 모두 확인한다(실제 응답은 roud 사용).
  const rounds = payload.rounds ?? payload.rouds ?? payload.roud ?? [];
  const movies = payload.movies ?? payload.movie ?? payload.recommended_movies ?? [];

  return {
    conversationId:
      roomId === undefined || roomId === null ? '' : String(roomId),
    answer:
      payload.answer ||
      payload.message?.content ||
      payload.content ||
      '',
    character: payload.character || request.character,
    intent: payload.intent || payload.meta?.intent || 'character_chat',
    rounds: Array.isArray(rounds) ? rounds : [],
    movies: Array.isArray(movies) ? movies : [],
    raw: json,
  };
}

export async function sendChat(request, signal, onChunk) {
  const isGroup = request.mode === 'group';
  const isAuto = !isGroup && !request.character;

  if (!isGroup && !isAuto) {
    return sendCharacterChatStream(request, signal, onChunk);
  }

  let url = `${BACKEND_BASE_URL}/chat`;
  let body = {
    message: request.message,
    character: request.character ?? null,
  };

  if (isGroup) {
    url = `${BACKEND_BASE_URL}/chat/group`;
    body = {
      characters: request.characters,
      message: request.message,
    };
  } else if (isAuto) {
    url = `${BACKEND_BASE_URL}/chat/auto`;
    body = {
      message: request.message,
    };
  }

  const response = await fetchWithAuth(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `채팅 요청 실패 (${response.status})`));
  }

  return normalizeChatResponse(data, request);
}

function getStreamText(payload) {
  if (typeof payload === 'string') return payload;

  return (
    payload?.delta ??
    payload?.token ??
    payload?.text ??
    payload?.answer ??
    payload?.content ??
    payload?.message?.content ??
    payload?.data?.delta ??
    payload?.data?.token ??
    payload?.data?.text ??
    payload?.data?.answer ??
    payload?.data?.content ??
    ''
  );
}

function parseStreamPayload(raw) {
  try {
    return JSON.parse(raw);
  } catch (error) {
    return raw;
  }
}

// POST /chat과 POST /chat/rooms/{id}/messages는 성공 시 SSE, 실패 시 JSON을 반환한다.
export async function sendCharacterChatStream(request, signal, onChunk) {
  const isExistingRoom = request.roomId !== undefined && request.roomId !== null && request.roomId !== '';
  const url = isExistingRoom
    ? `${BACKEND_BASE_URL}/chat/rooms/${request.roomId}/messages`
    : `${BACKEND_BASE_URL}/chat`;
  const body = isExistingRoom
    ? {
        content: request.message,
        character: request.character ?? null,
      }
    : {
        message: request.message,
        character: request.character,
      };
  const response = await fetchWithAuth(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream, application/json',
    },
    body: JSON.stringify(body),
    signal,
  });

  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    const data = await response.json().catch(() => null);

    if (!response.ok || isFailureResponse(data)) {
      throw new Error(getErrorMessage(data, `스트림 채팅 요청 실패 (${response.status})`));
    }

    return normalizeChatResponse(data, request);
  }

  if (!response.ok) {
    const message = await response.text().catch(() => '');
    throw new Error(message || `스트림 채팅 요청 실패 (${response.status})`);
  }

  if (!response.body) {
    throw new Error('채팅 스트림 본문이 없습니다.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let answer = '';
  let finalPayload = null;

  const consumeEvent = (rawEvent) => {
    const dataLines = rawEvent
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim());

    for (const raw of dataLines) {
      if (!raw) continue;
      if (raw === '[DONE]') return true;

      const payload = parseStreamPayload(raw);
      finalPayload = payload;
      const chunk = String(getStreamText(payload) || '');
      if (!chunk) continue;

      // AI 서버가 누적 답변을 보내는 경우와 토큰만 보내는 경우를 모두 지원한다.
      answer = chunk.startsWith(answer) ? chunk : answer + chunk;
      onChunk?.(answer, payload);
    }

    return false;
  };

  let streamDone = false;
  while (true) {
    // eslint-disable-next-line no-await-in-loop
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    const events = buffer.split(/\r?\n\r?\n/);
    buffer = events.pop() || '';

    for (const event of events) {
      if (consumeEvent(event)) {
        streamDone = true;
        break;
      }
    }

    if (streamDone || done) break;
  }

  if (!streamDone && buffer.trim()) consumeEvent(buffer);

  const normalized = normalizeChatResponse(finalPayload, request);
  let conversationId = normalized.conversationId;

  // 신규 1:1 SSE에는 room_id가 없으므로 종료 후 최신 캐릭터 방을 다시 조회한다.
  if (!isExistingRoom && !conversationId) {
    try {
      const rooms = await fetchChatRooms(signal);
      const latestRoom = rooms.find(
        (room) =>
          room?.room_type === 'character' &&
          room?.characters?.some((name) => name === request.character)
      ) || rooms.find((room) => room?.room_type === 'character');
      conversationId =
        latestRoom?.room_id === undefined || latestRoom?.room_id === null
          ? ''
          : String(latestRoom.room_id);
    } catch (error) {
      // 방 ID 보조 조회가 실패해도 이미 완료된 스트림 답변은 유지한다.
    }
  }

  return {
    ...normalized,
    conversationId,
    answer: answer || normalized.answer,
  };
}

export async function sendRoomMessage(roomId, request, signal, onChunk) {
  return sendCharacterChatStream(
    { ...request, roomId, character: request.character ?? null },
    signal,
    onChunk
  );
}

export async function fetchChatRoomMessages(roomId, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/chat/rooms/${roomId}/messages`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `채팅 메시지 목록 요청 실패 (${response.status})`));
  }

  return data?.data || [];
}

export async function fetchChatRooms(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/chat/rooms`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `대화 목록 요청 실패 (${response.status})`));
  }

  // 방이 없으면(failure) 빈 목록. 성공이면 data 배열을 그대로 사용한다.
  if (getResponseState(data) === 'failure' || getResponseState(data) === 'fail') {
    return [];
  }

  return getArrayPayload(data, 'rooms');
}

// 채팅방 삭제 (DELETE /chat/rooms/{room_id}) — 인증 필요, 본인 방만.
export async function deleteChatRoom(roomId, signal) {
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/chat/rooms/${roomId}`,
    { method: 'DELETE', signal }
  );
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'fail' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `채팅방 삭제 실패 (${response.status})`));
  }

  return data || {};
}

export async function fetchCharacters(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/chat/characters`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `캐릭터 목록 요청 실패 (${response.status})`));
  }

  return getArrayPayload(data, 'characters').map((character) => ({
    ...character,
    image:
      character.image ||
      character.image_url ||
      character.profile_image ||
      character.avatar_url ||
      '',
    image_url:
      character.image_url ||
      character.profile_image ||
      character.image ||
      character.avatar_url ||
      '',
  }));
}

// 캐릭터 단건 조회 (GET /chatcharcter/{character_name}) — 인증 없음.
// 주의: 실제 경로에 오타(chatcharcter)가 있어 그대로 사용한다. 이름/별칭은 인코딩해서 넣는다.
// 응답 data: { id, name, profile_image }
export async function fetchCharacter(characterName, signal) {
  const response = await fetch(
    `${BACKEND_BASE_URL}/chatcharcter/${encodeURIComponent(characterName)}`,
    { signal, cache: 'no-store' }
  );
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `캐릭터 정보 조회 실패 (${response.status})`));
  }

  const character = data?.data || {};
  return {
    id: character.id === undefined || character.id === null ? '' : String(character.id),
    name: character.name || characterName,
    image: character.profile_image || '',
    image_url: character.profile_image || '',
  };
}

// 배우 목록 조회 API (GET /movies/actors).
// 명세서: { state, message, data: [{ actor_id, actor_name, profile_path }] }
export async function fetchActors(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/actors`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, `배우 목록 요청 실패 (${response.status})`));
  }

  // 서버 에러(state: 'error')는 실패로 처리하고, 배우가 없는 경우(failure)는 빈 목록으로 본다.
  if (getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, '배우 조회 API 에러'));
  }

  return getArrayPayload(data, 'actors').map((actor) => {
    const path = actor?.profile_path || '';
    const image = path
      ? path.startsWith('http')
        ? path
        : resolveMovieImage(path)
      : '';

    return {
      id: String(actor?.actor_id ?? actor?.id ?? actor?.actor_name ?? ''),
      name: actor?.actor_name || actor?.name || '',
      image_url: image,
      profile_path: path,
    };
  });
}

// 선호 배우 저장 (POST /movies/actor/{actor_id}) — 인증 필요.
// 응답 data: { user_email, user_preferred_actors: [이름들] }
export async function savePreferredActor(actorId, signal) {
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/movies/actor/${actorId}`,
    { method: 'POST', signal }
  );
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `선호 배우 저장 실패 (${response.status})`));
  }

  return data?.data || {};
}

export async function fetchGenres(signal) {
  try {
    const movies = await fetchMovies(signal);
    const names = movies.flatMap((movie) => {
      if (Array.isArray(movie.genres)) return movie.genres;
      return String(movie.genres || movie.genre || '')
        .split(',')
        .map((genre) => genre.trim())
        .filter(Boolean);
    });

    // 장르 카드는 한 줄(5개)까지만 노출한다. 그 이상은 박스가 넘쳐서 잘린다.
    const uniqueNames = Array.from(new Set(names)).slice(0, 5);
    const genreNames = uniqueNames.length > 0 ? uniqueNames : FALLBACK_GENRES.slice(0, 5);

    return genreNames.map((name, index) => ({
      name,
      tone: (index % 8) + 1,
    }));
  } catch (error) {
    if (error.name === 'AbortError') throw error;

    return FALLBACK_GENRES.slice(0, 5).map((name, index) => ({
      name,
      tone: (index % 8) + 1,
    }));
  }
}

export async function getRecommendMovies(limit = 12, signal) {
  const params = new URLSearchParams({
    limit: String(clampNumber(limit, 1, 30, 12)),
  });
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/recommend?${params}`, {
    method: 'POST',
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || data?.state === 'error') {
    throw new Error(getErrorMessage(data, `추천 영화 요청 실패 (${response.status})`));
  }

  if (data?.state === 'failure') {
    return {
      ...data,
      data: [],
    };
  }

  return data || { state: 'success', message: '', data: [] };
}

export async function fetchRecommendedMovies(signal, limit = 12) {
  const data = await getRecommendMovies(limit, signal);

  return data?.state === 'success' ? getArrayPayload(data) : [];
}

export async function fetchMovies(signal, keyword = '', { page = 1, limit } = {}) {
  const searchKeyword = String(keyword ?? '').trim();

  if (!searchKeyword) {
    return fetchRecommendedMovies(signal, limit ?? 12);
  }

  const params = new URLSearchParams({
    keyword: searchKeyword,
    page: String(clampNumber(page, 1, Number.MAX_SAFE_INTEGER, 1)),
    limit: String(clampNumber(limit, 1, 50, 20)),
  });
  const response = await fetch(`${BACKEND_BASE_URL}/movies/search?${params}`, {
    method: 'GET',
    signal,
  });
  const data = await response.json().catch(() => null);

  if (getResponseState(data) === 'failure') {
    return [];
  }

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `영화 목록 요청 실패 (${response.status})`));
  }

  return getArrayPayload(data, 'movies', 'results', 'items');
}

export async function fetchMovieRanking(signal, limit = 10) {
  const params = new URLSearchParams({
    limit: String(clampNumber(limit, 1, 100, 10)),
  });
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/ranking?${params}`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `실시간 랭킹 요청 실패 (${response.status})`));
  }

  return getArrayPayload(data, 'rankings').map((movie, index) => ({
    ...movie,
    id: movie.id ?? movie.movie_id,
    rank: index + 1,
    genre: Array.isArray(movie.genres)
      ? movie.genres.join(', ')
      : movie.genre || movie.genres || '',
    rating: movie.vote_average ?? movie.rating ?? movie.ranking_score ?? '',
    change: movie.change || '',
  }));
}

// 영화 상세 조회 (GET /movies/{movie_id}?source=direct).
// 로그인 상태면 조회 이력이 저장되어 "최근 본 영화"에 반영된다. source='search'면 검색 클릭으로 기록.
export async function fetchMovieDetail(movieId, source = 'direct', signal) {
  const params = new URLSearchParams({ source: source || 'direct' });
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/movies/${movieId}?${params}`,
    { signal }
  );
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `영화 상세 조회 실패 (${response.status})`));
  }

  return data?.data || null;
}

export async function fetchMoviesByGenre(genre, signal, { page = 1, limit = 20 } = {}) {
  const params = new URLSearchParams({
    page: String(clampNumber(page, 1, Number.MAX_SAFE_INTEGER, 1)),
    limit: String(clampNumber(limit, 1, 50, 20)),
  });
  const response = await fetch(
    `${BACKEND_BASE_URL}/movies/genre/${encodeURIComponent(genre)}?${params}`,
    { credentials: 'include', cache: 'no-store', signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `장르별 영화 조회 실패 (${response.status})`));
  }

  return getArrayPayload(data, 'movies');
}

export async function requestAiMovieRecommendation(
  { userId, user_id, prompt = null, genres = [] },
  signal
) {
  const response = await fetch(`${BACKEND_BASE_URL}/movies/ai-recommend`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId ?? user_id,
      prompt,
      genres,
    }),
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `AI 영화 추천 실패 (${response.status})`));
  }

  return data?.data || {};
}


function toLikedMoviePayload(movie) {
  return {
    title: movie.title,
    genre: movie.genre || '',
    rating: movie.rating || '',
  };
}

async function requestLikedMovie(method, movie) {
  const movieId = movie?.id ?? movie?.movie_id;

  if (movieId !== undefined && movieId !== null) {
    return likeMovie(movieId);
  }

  throw new Error(`${toLikedMoviePayload(movie).title || '영화'}는 서버 movie_id가 없어 좋아요를 변경할 수 없습니다.`);
}

export function addLikedMovie(movie) {
  return requestLikedMovie('POST', movie);
}

export function removeLikedMovie(movie, signal) {
  const movieId = movie?.id ?? movie?.movie_id;

  if (movieId === undefined || movieId === null) {
    throw new Error(
      `${toLikedMoviePayload(movie).title || '영화'}는 서버 movie_id가 없어 좋아요를 삭제할 수 없습니다.`
    );
  }

  return deleteLikedMovie(movieId, signal);
}

// 좋아요 누른 영화 삭제 (DELETE /user/movie-like/{movie_id}) — 인증 필요.
// failure(이미 삭제됨)는 UI만 동기화하면 되므로 성공처럼 취급, error/네트워크 오류만 던진다.
export async function deleteLikedMovie(movieId, signal) {
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/user/movie-like/${movieId}`,
    { method: 'DELETE', signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `좋아요 삭제 실패 (${response.status})`));
  }

  return data || {};
}

// 선호값(장르/배우/키워드) 하나 삭제 (DELETE /user/preference/delete, body 사용) — 인증 필요.
// 응답 data의 preferred_* 배열을 { genres, actors, keywords } 로 정리해서 돌려준다.
export async function deletePreference(preferenceType, preferenceValue, signal) {
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/user/preference/delete`,
    {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        preference_type: preferenceType,
        preference_value: preferenceValue,
      }),
      signal,
    }
  );
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `선호값 삭제 실패 (${response.status})`));
  }

  const result = data?.data || {};
  return {
    genres: result.preferred_genres || [],
    actors: result.preferred_actors || [],
    keywords: result.preferred_keywords || [],
  };
}


export async function likeMovie(movieId, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/${movieId}/like`, {
    method: 'POST',
    signal,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `좋아요 요청 실패 (${response.status})`));
  }

  return data;
}

export async function fetchUserPreferences(signal) {
  const localPreferences = readLocalJson(LOCAL_PREFERENCES_KEY, null);
  // 실제 경로는 /user/preferences (기존 /users/me/preferences 아님)
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/user/preferences`,
    {
      signal,
    }
  );

  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(
      getErrorMessage(data, `취향 정보 요청 실패 (${response.status})`)
    );
  }

  // 명세의 explicit_preferences를 현재 UI가 쓰는 preferences 형태로 함께 노출한다.
  const serverData = data?.data || data || {};
  const explicitPreferences = serverData.explicit_preferences || {};
  const serverPreferences = {
    genres:
      explicitPreferences.genres || serverData.preferred_genres || serverData.genres || [],
    actors:
      explicitPreferences.actors || serverData.preferred_actors || serverData.actors || [],
    keywords:
      explicitPreferences.keywords || serverData.preferred_keywords || serverData.keywords || [],
    directors: serverData.preferred_directors || serverData.directors || [],
  };

  return {
    ...serverData,
    preferences: {
      ...serverPreferences,
      ...(localPreferences || {}),
    },
  };
}

export async function fetchUserProfile(signal) {
  const localProfile = readLocalJson(LOCAL_PROFILE_KEY, null);
  // 실제 경로는 /user (기존 /users/me 아님)
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user`, {
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `프로필 정보를 불러오지 못했습니다. (${response.status})`));
  }

  return {
    ...(data?.data || data || {}),
    ...(localProfile || {}),
  };
}

export async function updateUserProfile(profile, signal) {
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');

  writeLocalJson(LOCAL_PROFILE_KEY, profile);

  return profile;
}

// 프로필 이미지 수정 (PATCH /user/profile_image, multipart/form-data) — 인증 필요.
// Content-Type은 브라우저가 boundary와 함께 자동 설정하도록 직접 지정하지 않는다.
export async function updateProfileImage(file, signal) {
  const form = new FormData();
  form.append('image', file);

  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/profile_image`, {
    method: 'PATCH',
    body: form,
    signal,
  });
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `이미지 수정 실패 (${response.status})`));
  }

  return data?.data || {};
}

// 프로필 이미지 삭제 (DELETE /user/delete/profile_image) — 인증 필요.
export async function deleteProfileImage(signal) {
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/user/delete/profile_image`,
    { method: 'DELETE', signal }
  );
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    getResponseState(data) === 'failure' ||
    getResponseState(data) === 'error'
  ) {
    throw new Error(getErrorMessage(data, `이미지 삭제 실패 (${response.status})`));
  }

  return data || {};
}

export async function updateUserPreferences(preferences, signal) {
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');

  writeLocalJson(LOCAL_PREFERENCES_KEY, preferences);

  return { preferences };
}

export async function fetchLikedMovies(signal) {
  // 실제 경로는 /user/movies-like (기존 /users/me/movies-like 아님)
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/user/movies-like`, {
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `좋아요한 영화를 불러오지 못했습니다. (${response.status})`));
  }

  return getArrayPayload(data, 'movies', 'liked_movies');
}

// 최근 본 영화 조회 (GET /user/recently-viewed?limit=5) — 인증 필요.
export async function fetchRecentMovies(signal, limit = 5) {
  const params = new URLSearchParams({
    limit: String(clampNumber(limit, 1, 50, 5)),
  });
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/user/recently-viewed?${params}`,
    { signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `최근 본 영화를 불러오지 못했습니다. (${response.status})`));
  }

  // 배우가 없는 경우 등 failure는 빈 목록으로 처리
  if (getResponseState(data) === 'failure') return [];

  return getArrayPayload(data, 'movies', 'recently_viewed');
}

// 채팅 AI가 추천했던 영화 조회 (GET /user/chatai-reommended-movies?limit=10).
// 주의: 실제 경로에 오타(reommended)가 있어 그대로 사용한다.
// 응답 data: [{ tmdb_id, title, poster_url }]
export async function fetchChatRecommendedMovies(signal, limit = 10) {
  const params = new URLSearchParams({
    limit: String(clampNumber(limit, 1, 50, 10)),
  });
  const response = await fetchWithAuth(
    `${BACKEND_BASE_URL}/user/chatai-reommended-movies?${params}`,
    { signal }
  );
  const data = await response.json().catch(() => null);

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(getErrorMessage(data, `채팅 추천 영화 조회 실패 (${response.status})`));
  }

  if (getResponseState(data) === 'failure') return [];

  return getArrayPayload(data, 'movies');
}

export async function removeRecentMovie(movieId, signal) {
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');

  return { state: 'success', movieId };
}

export async function fetchAiRecommendation(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/today/recommend`, {
    signal,
  });
  const data = await response.json().catch(() => null);

  if (!response.ok || isFailureResponse(data)) {
    throw new Error(getErrorMessage(data, `AI 추천 요청 실패 (${response.status})`));
  }

  const payload = data?.data;
  const copy = Array.isArray(payload)
    ? payload[0]
    : payload?.answer || payload?.copy || payload?.recommendation || '';
  const movies = Array.isArray(payload)
    ? payload[1]
    : payload?.movies || payload?.movie || [];

  // AI 추천은 한 번에 최대 3개의 슬라이스를 받아와서 프론트에서 슬라이딩으로 보여준다.
  const movieList = (Array.isArray(movies) ? movies : [])
    .slice(0, 3)
    .map((movie) => ({
      movie: movie?.title || '',
      poster_path: movie?.poster_url || movie?.poster_path || movie?.poster || '',
      description:
        movie?.overview ||
        (Array.isArray(movie?.genres)
          ? movie.genres.join(', ')
          : movie?.genres || movie?.genre || ''),
    }));

  return {
    title: 'AI의 추천 한 줄',
    copy: copy || '',
    movies: movieList,
  };
}
