import { useEffect, useState } from 'react';

import { fetchMovieDetail } from '../../api.js';
import './movieModal.css';

// 유튜브 watch/단축 링크를 임베드 가능한 형태로 변환
function toEmbeddableUrl(url) {
  if (!url) return '';

  const watchMatch = url.match(/youtube\.com\/watch\?v=([\w-]+)/);
  if (watchMatch) return `https://www.youtube.com/embed/${watchMatch[1]}`;

  const shortMatch = url.match(/youtu\.be\/([\w-]+)/);
  if (shortMatch) return `https://www.youtube.com/embed/${shortMatch[1]}`;

  return url;
}

function MovieModal({ movie, onClose, source = 'direct' }) {
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // 영화 상세 조회 → 로그인 상태면 조회 이력이 기록되어 "최근 본 영화"에 반영된다.
  const movieId = movie?.id ?? movie?.movie_id;
  useEffect(() => {
    setDetail(null);
    if (movieId === undefined || movieId === null) return undefined;

    const controller = new AbortController();
    fetchMovieDetail(movieId, source, controller.signal)
      .then(setDetail)
      .catch(() => {});

    return () => controller.abort();
  }, [movieId, source]);

  if (!movie) return null;

  const overview = detail?.overview || movie.overview || '';
  const genreText =
    (Array.isArray(detail?.genres) ? detail.genres.join(', ') : '') ||
    movie.genre ||
    '장르 정보 없음';
  const ratingText = detail?.vote_average ?? movie.rating ?? '-';

  const trailerUrl = toEmbeddableUrl(
    movie.trailerUrl || movie.trailer_url || movie.trailer || ''
  );

  return (
    <div
      className="movie-modal-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="movie-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`${movie.title} 상세 정보`}
      >
        <button
          className="movie-modal__close"
          type="button"
          onClick={onClose}
          aria-label="닫기"
        >
          ×
        </button>

        <div className="movie-modal__trailer">
          {trailerUrl ? (
            <iframe
              src={trailerUrl}
              title={`${movie.title} 예고편`}
              allow="autoplay; encrypted-media; picture-in-picture"
              allowFullScreen
            />
          ) : (
            <div className="movie-modal__trailer-empty">
              <span>예고편 준비 중</span>
            </div>
          )}
        </div>

        <div className="movie-modal__info">
          <h1>{movie.title}</h1>
          <h3>{genreText}</h3>
          <div className="movie-modal__rating">★ {ratingText}</div>
          {overview ? <p className="movie-modal__overview">{overview}</p> : null}
        </div>
      </div>
    </div>
  );
}

export default MovieModal;
