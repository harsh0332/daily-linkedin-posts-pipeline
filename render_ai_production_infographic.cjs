const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

(async () => {
    const htmlContent = `
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=1080"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800;900&family=Instrument+Serif:ital@1&family=JetBrains+Mono:wght@600;700&display=swap" rel="stylesheet"/>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1080px;
    height: 1080px;
    background-color: #080C14;
    background-image: 
      radial-gradient(circle at 85% 10%, rgba(99, 102, 241, 0.18) 0%, transparent 50%),
      radial-gradient(circle at 15% 90%, rgba(16, 185, 129, 0.14) 0%, transparent 50%),
      radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.08) 0%, transparent 60%);
    color: #FFFFFF;
    font-family: 'Plus Jakarta Sans', sans-serif;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 50px 65px;
    overflow: hidden;
  }

  /* Header */
  .header { display: flex; justify-content: space-between; align-items: center; }
  .header-badge {
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.35);
    padding: 8px 20px;
    border-radius: 30px;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #818CF8;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .header-brand {
    font-family: 'Instrument Serif', serif;
    font-style: italic;
    font-size: 26px;
    color: #94A3B8;
  }

  /* Title Block */
  .title-block { margin-top: 10px; margin-bottom: 15px; }
  .main-title { font-size: 46px; font-weight: 900; letter-spacing: -2px; line-height: 1.1; color: #FFFFFF; }
  .main-title em { font-family: 'Instrument Serif', serif; font-style: italic; color: #818CF8; font-weight: 400; }
  .sub-title { font-size: 18px; color: #94A3B8; font-weight: 500; margin-top: 6px; }

  /* 5 Rules Container */
  .rules-container {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex: 1;
    margin-bottom: 18px;
  }

  .rule-card {
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 14px 20px;
    display: flex;
    align-items: center;
    gap: 18px;
    backdrop-filter: blur(10px);
    transition: all 0.2s ease;
  }
  .rule-card.highlight {
    border-color: rgba(99, 102, 241, 0.4);
    background: rgba(30, 27, 75, 0.4);
    box-shadow: 0 8px 25px rgba(99, 102, 241, 0.12);
  }

  .rule-number {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #818CF8;
    font-family: 'JetBrains Mono', monospace;
    font-size: 18px;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .rule-card.highlight .rule-number {
    background: #6366F1;
    color: #FFFFFF;
  }

  .rule-content { flex: 1; }
  .rule-header { display: flex; justify-content: space-between; align-items: baseline; }
  .rule-title { font-size: 19px; font-weight: 800; color: #FFFFFF; letter-spacing: -0.3px; }
  .rule-tag {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #10B981;
    background: rgba(16, 185, 129, 0.12);
    padding: 3px 10px;
    border-radius: 20px;
  }
  .rule-desc { font-size: 14px; color: #94A3B8; font-weight: 500; margin-top: 3px; line-height: 1.35; }
  .rule-desc b { color: #E2E8F0; font-weight: 700; }

  /* Metrics Bar */
  .metrics-bar {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.85), rgba(15, 23, 42, 0.95));
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 18px;
    padding: 16px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.3);
  }
  .metric-item { display: flex; flex-direction: column; gap: 2px; }
  .metric-val { font-size: 24px; font-weight: 900; color: #818CF8; letter-spacing: -1px; }
  .metric-lbl { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #94A3B8; }
  .metric-divider { width: 1px; height: 32px; background: rgba(255, 255, 255, 0.1); }
</style>
</head>
<body>
  <div class="header">
    <div class="header-badge">
      <span>⚡ Production AI Architecture</span>
    </div>
    <div class="header-brand">harsh chouksey / 2026</div>
  </div>

  <div class="title-block">
    <div class="main-title">The 5 Rules of <em>Production-Grade</em> AI</div>
    <div class="sub-title">Moving from toy prompt wrappers to robust, cost-effective enterprise AI systems.</div>
  </div>

  <div class="rules-container">
    <div class="rule-card highlight">
      <div class="rule-number">01</div>
      <div class="rule-content">
        <div class="rule-header">
          <div class="rule-title">Build Context, Not Prompts</div>
          <div class="rule-tag">Accuracy Boost</div>
        </div>
        <div class="rule-desc">If you want superior AI outputs, stop writing 2,000-word mega-prompts. <b>Dynamic context injection & precise RAG</b> outperform prompt tweaks every single time.</div>
      </div>
    </div>

    <div class="rule-card">
      <div class="rule-number">02</div>
      <div class="rule-content">
        <div class="rule-header">
          <div class="rule-title">Route Tasks by Complexity</div>
          <div class="rule-tag">-74% API Cost</div>
        </div>
        <div class="rule-desc">If you want lower AI bills, <b>tier your model routing</b>. Route simple formatting to Flash / Haiku; reserve frontier models like Claude 3.5 Sonnet only for multi-step reasoning.</div>
      </div>
    </div>

    <div class="rule-card highlight">
      <div class="rule-number">03</div>
      <div class="rule-content">
        <div class="rule-header">
          <div class="rule-title">Use an API Abstraction Layer</div>
          <div class="rule-tag">Zero Vendor Lock-In</div>
        </div>
        <div class="rule-desc">If you want freedom from API outages and price shifts, <b>deploy a unified router</b> (like OpenRouter / LiteLLM proxy) with automatic fallback failovers.</div>
      </div>
    </div>

    <div class="rule-card">
      <div class="rule-number">04</div>
      <div class="rule-content">
        <div class="rule-header">
          <div class="rule-title">Design Automated Evals</div>
          <div class="rule-tag">99.4% Reliability</div>
        </div>
        <div class="rule-desc">If you want dependable AI behavior, <b>design rigorous evaluation suites</b>. Measure schema adherence, hallucination rates, and semantic drift with automated unit tests.</div>
      </div>
    </div>

    <div class="rule-card highlight">
      <div class="rule-number">05</div>
      <div class="rule-content">
        <div class="rule-header">
          <div class="rule-title">Stress-Test Edge Cases</div>
          <div class="rule-tag">Production Defense</div>
        </div>
        <div class="rule-desc">If you want enterprise-ready AI, <b>test adversarial edge cases before shipping</b>. Validate tool timeout fallbacks, empty states, and guardrail bypass attempts.</div>
      </div>
    </div>
  </div>

  <div class="metrics-bar">
    <div class="metric-item">
      <div class="metric-val">-74%</div>
      <div class="metric-lbl">LLM Token Cost</div>
    </div>
    <div class="metric-divider"></div>
    <div class="metric-item">
      <div class="metric-val">99.4%</div>
      <div class="metric-lbl">Schema Reliability</div>
    </div>
    <div class="metric-divider"></div>
    <div class="metric-item">
      <div class="metric-val">&lt; 800ms</div>
      <div class="metric-lbl">P95 Routed Latency</div>
    </div>
  </div>
</body>
</html>
    `;

    const htmlPath = path.resolve(__dirname, 'ai_production_rules_infographic.html');
    const pngPath = path.resolve(__dirname, 'ai_production_rules_infographic.png');
    fs.writeFileSync(htmlPath, htmlContent);

    const browser = await puppeteer.launch({
        headless: 'shell',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1080, height: 1080, deviceScaleFactor: 2 });
    await page.goto(`file://${htmlPath}`, { waitUntil: 'domcontentloaded' });
    await page.screenshot({ path: pngPath });
    await browser.close();

    console.log(`[✓] Infographic rendered: ${pngPath}`);
})();
