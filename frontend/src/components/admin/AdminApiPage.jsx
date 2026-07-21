import { useCallback, useEffect, useState } from 'react';
import {
  createAdminCharacter,
  createAdminMovie,
  deleteAdminMovie,
  fetchAdminStats,
  updateAdminCharacter,
  updateAdminMovie,
} from '../../api.js';
import './adminApiPage.css';

const emptyMovie = { id: '', title: '', overview: '', release_date: '', poster_path: '', genres: '' };
const emptyCharacter = { id: '', name: '', movie_id: '', description: '', prompt: '', image_url: '' };

function cleanPayload(form, excluded = ['id']) {
  return Object.fromEntries(Object.entries(form).filter(([key, value]) => !excluded.includes(key) && value !== '').map(([key, value]) => [key, key === 'genres' ? value.split(',').map((item) => item.trim()).filter(Boolean) : value]));
}

export default function AdminApiPage({ authUser }) {
  const [tab, setTab] = useState('stats'); const [stats, setStats] = useState(null); const [loadingStats, setLoadingStats] = useState(true);
  const [movie, setMovie] = useState(emptyMovie); const [character, setCharacter] = useState(emptyCharacter);
  const [busy, setBusy] = useState(false); const [notice, setNotice] = useState(null);
  const declaredRole = String(authUser?.role || authUser?.authority || '').toUpperCase();
  // 역할이 토큰/로그인 응답에 있을 때는 즉시 차단하고, 없을 때는 백엔드 401/403을 최종 판정으로 사용한다.
  const isAdmin = !declaredRole || ['ADMIN', 'SUPER_ADMIN'].includes(declaredRole);
  const loadStats = useCallback(async () => { const controller = new AbortController(); setLoadingStats(true); try { setStats(await fetchAdminStats(controller.signal)); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setLoadingStats(false); } return () => controller.abort(); }, []);
  useEffect(() => { if (isAdmin) loadStats(); else setLoadingStats(false); }, [isAdmin, loadStats]);
  const run = async (action, success) => { setBusy(true); setNotice(null); try { await action(); setNotice({ type: 'success', text: success }); await loadStats(); } catch (error) { setNotice({ type: 'error', text: error.message }); } finally { setBusy(false); } };
  if (!authUser) return <main className="be2-admin-state"><h1>관리자 로그인이 필요합니다.</h1><a href="/login">로그인으로 이동</a></main>;
  if (!isAdmin) return <main className="be2-admin-state"><h1>접근 권한이 없습니다.</h1><p>이 페이지는 ADMIN 또는 SUPER_ADMIN만 사용할 수 있습니다.</p><a href="/">홈으로 이동</a></main>;
  return <main className="be2-admin"><header><div><p>CINEVERSE OPERATIONS · BE2</p><h1>콘텐츠 관리자</h1><span>영화와 캐릭터를 관리하고 서비스 통계를 확인합니다.</span></div><a href="/">사용자 페이지</a></header><nav aria-label="관리자 기능"><button className={tab === 'stats' ? 'active' : ''} onClick={() => setTab('stats')}>서비스 통계</button><button className={tab === 'movies' ? 'active' : ''} onClick={() => setTab('movies')}>영화 관리</button><button className={tab === 'characters' ? 'active' : ''} onClick={() => setTab('characters')}>캐릭터 관리</button></nav>{notice && <div className={`be2-notice ${notice.type}`} role="status">{notice.text}</div>}{tab === 'stats' && <StatsPanel stats={stats} loading={loadingStats} onRefresh={loadStats} />}{tab === 'movies' && <MoviePanel form={movie} setForm={setMovie} busy={busy} run={run} />}{tab === 'characters' && <CharacterPanel form={character} setForm={setCharacter} busy={busy} run={run} />}</main>;
}

function StatsPanel({ stats, loading, onRefresh }) {
  const payload = stats?.data || stats || {}; const cards = [
    ['사용자 수', payload.user_count ?? payload.total_users], ['추천 수', payload.recommendation_count ?? payload.total_recommendations],
    ['인기 영화', payload.popular_movie?.title ?? payload.popular_movie ?? payload.top_movie], ['등록 영화', payload.movie_count ?? payload.total_movies],
  ];
  return <section className="be2-panel"><div className="be2-panel-title"><div><small>GET /admin/stats</small><h2>서비스 통계 조회</h2></div><button onClick={onRefresh}>새로고침</button></div>{loading ? <div className="be2-loading">통계를 불러오는 중…</div> : <><div className="be2-stat-grid">{cards.map(([label, value]) => <article key={label}><span>{label}</span><strong>{value ?? '—'}</strong></article>)}</div><details><summary>전체 API 응답 보기</summary><pre>{JSON.stringify(stats, null, 2)}</pre></details></>}</section>;
}
function MoviePanel({ form, setForm, busy, run }) { const field = (key) => ({ value: form[key], onChange: (event) => setForm({ ...form, [key]: event.target.value }) }); return <section className="be2-panel"><div className="be2-panel-title"><div><small>POST · PUT · DELETE</small><h2>영화 관리</h2></div></div><form className="be2-form" onSubmit={(event) => { event.preventDefault(); run(() => form.id ? updateAdminMovie(form.id, cleanPayload(form)) : createAdminMovie(cleanPayload(form)), form.id ? '영화를 수정했습니다.' : '영화를 등록했습니다.'); }}><label>영화 ID <input {...field('id')} placeholder="수정·삭제할 때 입력" /></label><label>영화 제목 <input {...field('title')} required placeholder="영화 제목" /></label><label>개봉일 <input {...field('release_date')} type="date" /></label><label>포스터 경로 <input {...field('poster_path')} placeholder="https:// 또는 /poster.jpg" /></label><label className="wide">장르 <input {...field('genres')} placeholder="드라마, SF (쉼표로 구분)" /></label><label className="wide">줄거리 <textarea {...field('overview')} rows="5" /></label><div className="be2-actions"><button disabled={busy} className="primary">{form.id ? '영화 수정' : '영화 등록'}</button><button type="button" onClick={() => setForm(emptyMovie)}>초기화</button><button type="button" className="danger" disabled={busy || !form.id} onClick={() => { if (window.confirm(`영화 #${form.id}을 삭제하시겠습니까?`)) run(() => deleteAdminMovie(form.id), '영화를 삭제했습니다.'); }}>영화 삭제</button></div></form></section>; }
function CharacterPanel({ form, setForm, busy, run }) { const field = (key) => ({ value: form[key], onChange: (event) => setForm({ ...form, [key]: event.target.value }) }); return <section className="be2-panel"><div className="be2-panel-title"><div><small>POST · PUT</small><h2>캐릭터 및 프롬프트 관리</h2></div></div><form className="be2-form" onSubmit={(event) => { event.preventDefault(); run(() => form.id ? updateAdminCharacter(form.id, cleanPayload(form)) : createAdminCharacter(cleanPayload(form)), form.id ? '캐릭터를 수정했습니다.' : '캐릭터를 등록했습니다.'); }}><label>캐릭터 ID <input {...field('id')} placeholder="수정할 때 입력" /></label><label>캐릭터 이름 <input {...field('name')} required /></label><label>영화 ID <input {...field('movie_id')} /></label><label>이미지 URL <input {...field('image_url')} /></label><label className="wide">설명 <textarea {...field('description')} rows="3" /></label><label className="wide">캐릭터 프롬프트 <textarea {...field('prompt')} rows="8" required /></label><div className="be2-actions"><button disabled={busy} className="primary">{form.id ? '캐릭터/프롬프트 수정' : '캐릭터 등록'}</button><button type="button" onClick={() => setForm(emptyCharacter)}>초기화</button></div></form></section>; }
