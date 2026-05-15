const logoUrl = "/cpc-logo.png";

function PeopleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 11.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM3.5 19c.7-3 2.3-4.5 4.5-4.5s3.8 1.5 4.5 4.5m-.9 0c.7-2.6 2.2-3.9 4.4-3.9 2.3 0 3.8 1.3 4.5 3.9" />
    </svg>
  );
}

function SavingsIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 17h16M6 17V9m6 8V5m6 12v-6M5 8l7-4 7 6" />
    </svg>
  );
}

function ExportIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 3h7l4 4v14H7V3Zm7 0v5h5M10 13h4m-2-2v7m0 0-2-2m2 2 2-2" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M6.5 4.5v11l8-5.5-8-5.5Z" />
    </svg>
  );
}

type HomePageProps = {
  onStart: () => void;
};

export function HomePage({ onStart }: HomePageProps) {
  return (
    <section className="home-cover" aria-label="Home Page">
      <div className="home-cover-grid" aria-hidden />
      <div className="home-cover-content">
        <img src={logoUrl} alt="CPC" className="home-cover-logo" />
        <div className="home-cover-title">
          <h1>Manpower</h1>
          <p>Optimization Tool</p>
        </div>
        <div className="home-cover-actions" aria-label="Tool outcomes">
          <div>
            <PeopleIcon />
            <span>Optimize Manpower</span>
          </div>
          <div>
            <SavingsIcon />
            <span>Achieve Savings</span>
          </div>
          <div>
            <ExportIcon />
            <span>Export Data</span>
          </div>
        </div>
        <button className="home-start-btn" type="button" onClick={onStart}>
          <PlayIcon />
          <span>Start</span>
        </button>
      </div>
    </section>
  );
}
