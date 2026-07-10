import { useEffect, useState } from 'react';

import { fetchGenres } from '../../api.js';

function GenreSection() {
  const [genres, setGenres] = useState([]);

  useEffect(() => {
    const controller = new AbortController();

    fetchGenres(controller.signal)
      .then(setGenres)
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('장르 목록 불러오기 실패:', error);
      });

    return () => controller.abort();
  }, []);

  return (
    <section className="index-genre-section" aria-label="장르별 추천">
      <h2>장르별 추천</h2>

      <div className="index-genre-row">
        {genres.map((genre) => (
          <a
            className={`index-genre-card genre-tone--${genre.tone}`}
            href={`/recommendations?keyword=${encodeURIComponent(genre.name)}`}
            key={genre.name}
          >
            <span>더보기 ›</span>
            <strong>{genre.name}</strong>
          </a>
        ))}
      </div>
    </section>
  );
}

export default GenreSection;
