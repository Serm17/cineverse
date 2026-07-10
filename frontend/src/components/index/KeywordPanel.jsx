import { useEffect, useState } from 'react';

import { fetchUserPreferences } from '../../api.js';
import Tag from './Tag.jsx';

function KeywordPanel() {
  const [keywords, setKeywords] = useState([]);

  useEffect(() => {
    const controller = new AbortController();

    fetchUserPreferences(controller.signal)
      .then((data) => {
        const preferences = data.preferences || data || {};

        setKeywords([
          ...(preferences.genres || []),
          ...(preferences.actors || []),
          ...(preferences.directors || []),
        ]);
      })
      .catch((error) => {
        if (error.name === 'AbortError') return;
        console.error('관심 키워드 불러오기 실패:', error);
      });

    return () => controller.abort();
  }, []);

  return (
    <article className="index-info-card keyword-card">
      <div className="index-card-header">
        <h3>나의 관심 키워드</h3>
        <a href="/recommendations">더보기 ›</a>
      </div>

      <div className="index-keywords">
        {keywords.map((keyword, index) => (
          <Tag key={`${keyword}-${index}`}>{keyword}</Tag>
        ))}
      </div>
    </article>
  );
}

export default KeywordPanel;
