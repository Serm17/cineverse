const BACKEND_BASE_URL = import.meta.env.DEV
  ? '/be'
  : import.meta.env.VITE_API_BASE_URL;

if (!BACKEND_BASE_URL) {
  throw new Error(
    'VITE_API_BASE_URL이 설정되지 않았습니다. frontend/.env에 백엔드 주소를 지정하세요.'
  );
}

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

function clearChatCaches() {
  CHAT_CACHE_KEYS.forEach((key) => localStorage.removeItem(key));
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
  return (
    data?.detail?.message ||
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
  return data?.state ?? data?.status;
}

function clampNumber(value, min, max, fallback) {
  const number = Number(value);

  if (!Number.isFinite(number)) return fallback;

  return Math.min(max, Math.max(min, number));
}

export async function fetchWithAuth(url, options = {}, allowRefreshRetry = true) {
  const token = localStorage.getItem('access_token');
  const headers = { ...(options.headers || {}) };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    // /auth, /chat, /user 응답은 캐시하지 않는다(백엔드 no-store 헤더와 맞춤). 호출부가 지정하면 그 값 우선.
    cache: 'no-store',
    ...options,
    headers,
  });

  // 액세스 토큰 만료(401)면 /auth/refresh 로 재발급 후 1회 재시도한다.
  // 로그인 상태(token 존재)에서만 시도하고, 재발급 실패 시 원래 401 응답을 그대로 돌려준다.
  if (response.status === 401 && allowRefreshRetry && token) {
    try {
      await refreshAccessToken(options.signal);
    } catch (refreshError) {
      return response;
    }

    return fetchWithAuth(url, options, false);
  }

  return response;
}

// 액세스 토큰 재발급 (POST /auth/refresh, 쿠키 기반 refresh token). 실패 시 세션을 정리한다.
export async function refreshAccessToken(signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    signal,
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
}

function storeAuthSession({ accessToken, email, nickname, tokenType }) {
  // 다른 사용자가 로그인하면 이전 사용자의 로컬 대화 캐시를 비운다(이전 채팅 노출 방지).
  const previousUser = getStoredAuthUser();
  if (!previousUser || previousUser.email !== email) {
    clearChatCaches();
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

  if (!response.ok || data?.state !== 'success') {
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

export async function registerWithEmail({ email, password, nickname }, signal) {
  const response = await fetch(`${BACKEND_BASE_URL}/auth/register`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, nickname }),
    signal,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok || data?.status !== 'success') {
    throw new Error(getErrorMessage(data, `회원가입 실패 (${response.status})`));
  }

  return data?.data || null;
}

export async function logoutUser(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
    signal,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok || data?.state !== 'success') {
    throw new Error(getErrorMessage(data, `로그아웃 실패 (${response.status})`));
  }

  clearStoredAuth();

  return data;
}

export async function checkBackendHealth(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/health`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, `백엔드 연결 실패 (${response.status})`));
  }

  return data;
}

export async function checkAiHealth(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/ai-health`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || data?.state !== 'success') {
    throw new Error(getErrorMessage(data, `AI 서버 연결 실패 (${response.status})`));
  }

  return data;
}

export async function checkDbHealth(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/db-test`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok || data?.status !== 'success') {
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

export async function sendChat(request, signal) {
  const isGroup = request.mode === 'group';
  const isAuto = !isGroup && !request.character;

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

  if (
    !response.ok ||
    data?.state === 'failure' ||
    data?.state === 'fail' ||
    data?.state === 'error'
  ) {
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

// 캐릭터 1:1 대화 전용 스트림 API. SSE, NDJSON, 일반 텍스트 스트림을 모두 읽는다.
export async function sendCharacterChatStream(request, signal, onChunk) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream, application/x-ndjson, application/json',
    },
    body: JSON.stringify({
      message: request.message,
      character: request.character,
      ...(request.roomId ? { room_id: request.roomId } : {}),
    }),
    signal,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(getErrorMessage(data, `스트림 채팅 요청 실패 (${response.status})`));
  }

  if (!response.body) {
    const data = await response.json().catch(() => null);
    return normalizeChatResponse(data, request);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let answer = '';
  let finalPayload = null;

  const consumeLine = (rawLine) => {
    const line = rawLine.trim();
    if (!line || line.startsWith(':') || line.startsWith('event:')) return;

    const value = line.startsWith('data:') ? line.slice(5).trim() : line;
    if (!value || value === '[DONE]') return;

    let payload = value;
    try {
      payload = JSON.parse(value);
      finalPayload = payload;
    } catch (error) {
      // JSON이 아닌 서버는 받은 문자열 자체를 토큰으로 취급한다.
    }

    const chunk = String(getStreamText(payload) || '');
    if (!chunk) return;

    // 일부 서버는 누적 본문을, 일부 서버는 새 토큰만 보낸다.
    answer = chunk.startsWith(answer) ? chunk : answer + chunk;
    onChunk?.(answer, payload);
  };

  while (true) {
    // eslint-disable-next-line no-await-in-loop
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    const lines = buffer.split(/\r?\n/);
    buffer = done ? '' : lines.pop() || '';
    lines.forEach(consumeLine);

    if (done) {
      if (buffer.trim()) consumeLine(buffer);
      break;
    }
  }

  const normalized = normalizeChatResponse(finalPayload, request);
  return {
    ...normalized,
    answer: answer || normalized.answer,
  };
}

export async function sendRoomMessage(roomId, request, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/chat/rooms/${roomId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: request.message }),
    signal,
  });

  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    data?.state === 'failure' ||
    data?.state === 'fail' ||
    data?.state === 'error'
  ) {
    throw new Error(getErrorMessage(data, `이어 말하기 요청 실패 (${response.status})`));
  }

  return normalizeChatResponse(data, request);
}

export async function fetchChatRoomMessages(roomId, signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/chat/rooms/${roomId}/messages`, { signal });
  const data = await response.json().catch(() => null);

  if (
    !response.ok ||
    data?.state === 'failure' ||
    data?.state === 'fail' ||
    data?.state === 'error'
  ) {
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

  if (!response.ok) {
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

const ACTOR_PROFILE_BASE_URL =
  import.meta.env.VITE_TMDB_IMAGE_BASE_URL || 'https://image.tmdb.org/t/p/w500';

// 배우 목록 조회 API (GET /actors) — 백엔드는 만들지 않고 프론트에서 연결만 한다.
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
        : `${ACTOR_PROFILE_BASE_URL}${path}`
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
  const response = await fetch(`${BACKEND_BASE_URL}/movies/recommend?${params}`, {
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

  if (data?.state === 'failure') {
    return [];
  }

  if (!response.ok) {
    throw new Error(getErrorMessage(data, `영화 목록 요청 실패 (${response.status})`));
  }

  return getArrayPayload(data, 'movies', 'results', 'items');
}

export async function fetchMovieRanking(signal) {
  const response = await fetchWithAuth(`${BACKEND_BASE_URL}/movies/ranking`, { signal });
  const data = await response.json().catch(() => null);

  if (!response.ok) {
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

  if (!response.ok) {
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

  if (!response.ok || getResponseState(data) === 'error') {
    throw new Error(
      getErrorMessage(data, `취향 정보 요청 실패 (${response.status})`)
    );
  }

  // 서버 응답: { preferred_genres, preferred_actors, preferred_keywords }
  // → 프론트에서 쓰는 { preferences: { genres, actors, directors, keywords } } 형태로 매핑.
  const serverData = data?.data || data || {};
  const serverPreferences = {
    genres: serverData.preferred_genres || serverData.genres || [],
    actors: serverData.preferred_actors || serverData.actors || [],
    keywords: serverData.preferred_keywords || serverData.keywords || [],
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

  if (!response.ok || getResponseState(data) === 'error') {
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

  if (!response.ok) {
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
