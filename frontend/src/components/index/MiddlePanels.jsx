import AiPanel from './AiPanel.jsx';
import KeywordPanel from './KeywordPanel.jsx';
import RankPanel from './RankPanel.jsx';
import RecentPanel from './RecentPanel.jsx';

function MiddlePanels() {
  return (
    <section className="index-middle-grid" aria-label="관심 정보">
      <div className="index-stack">
        <KeywordPanel />
        <RecentPanel />
      </div>
      <AiPanel />
      <RankPanel />
    </section>
  );
}

export default MiddlePanels;
