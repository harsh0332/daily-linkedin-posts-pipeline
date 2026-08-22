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
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800;900&family=Instrument+Serif:ital@1&display=swap" rel="stylesheet"/>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1080px;
    height: 1080px;
    background-color: #0B0F19;
    background-image: 
      radial-gradient(circle at 85% 15%, rgba(59, 130, 246, 0.18) 0%, transparent 50%),
      radial-gradient(circle at 15% 85%, rgba(16, 185, 129, 0.12) 0%, transparent 50%);
    color: #FFFFFF;
    font-family: 'Plus Jakarta Sans', sans-serif;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 55px 65px;
    overflow: hidden;
  }

  /* Header */
  .header { display: flex; justify-content: space-between; align-items: center; }
  .header-badge {
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.35);
    padding: 10px 22px;
    border-radius: 30px;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #60A5FA;
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
  .title-block { margin-top: 15px; margin-bottom: 20px; }
  .main-title { font-size: 50px; font-weight: 900; letter-spacing: -2px; line-height: 1.1; color: #FFFFFF; }
  .main-title em { font-family: 'Instrument Serif', serif; font-style: italic; color: #60A5FA; font-weight: 400; }
  .sub-title { font-size: 20px; color: #94A3B8; font-weight: 500; margin-top: 8px; }

  /* Flow Grid */
  .flow-container {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
    flex: 1;
    margin-bottom: 20px;
  }

  .step-card {
    background: rgba(18, 26, 43, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 20px;
    padding: 22px 24px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    backdrop-filter: blur(10px);
    position: relative;
  }
  .step-card.active-glow {
    border-color: rgba(59, 130, 246, 0.5);
    box-shadow: 0 10px 30px rgba(59, 130, 246, 0.12);
  }

  .step-header { display: flex; justify-content: space-between; align-items: center; }
  .step-pill {
    background: #1E293B;
    color: #38BDF8;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 6px 14px;
    border-radius: 12px;
  }
  .step-time { font-size: 13px; font-weight: 700; color: #10B981; }

  .step-headline { font-size: 22px; font-weight: 800; color: #FFFFFF; line-height: 1.25; margin-top: 10px; }
  .step-desc { font-size: 15px; color: #94A3B8; font-weight: 500; line-height: 1.4; margin-top: 6px; }

  .step-highlight {
    background: rgba(0, 0, 0, 0.35);
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 600;
    color: #E2E8F0;
    margin-top: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
    border-left: 3px solid #38BDF8;
  }

  /* Metrics Bar */
  .metrics-bar {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9));
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 20px;
    padding: 18px 30px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
  }
  .metric-item { display: flex; flex-direction: column; gap: 2px; }
  .metric-val { font-size: 26px; font-weight: 900; color: #38BDF8; letter-spacing: -1px; }
  .metric-lbl { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #94A3B8; }
  .metric-divider { width: 1px; height: 36px; background: rgba(255, 255, 255, 0.1); }
</style>
</head>
<body>
  <div class="header">
    <div class="header-badge">
      <span>⚡ Meta Ads 2026 Update</span>
    </div>
    <div class="header-brand">harsh chouksey / 2026</div>
  </div>

  <div class="title-block">
    <div class="main-title">The High-Converting <em>Comment-to-DM</em> Pipeline</div>
    <div class="sub-title">How conversational speed-to-lead cuts CPL and boosts Meta Ad Quality Score.</div>
  </div>

  <div class="flow-container">
    <div class="step-card">
      <div class="step-header">
        <div class="step-pill">Stage 01</div>
        <div class="step-time">Instant Trigger</div>
      </div>
      <div class="step-headline">Micro-Commitment Comment</div>
      <div class="step-desc">Ad copy invites a single keyword comment instead of forcing an external link click.</div>
      <div class="step-highlight">💬 "Comment 'FLOW' to get the full PDF blueprint"</div>
    </div>

    <div class="step-card active-glow">
      <div class="step-header">
        <div class="step-pill">Stage 02</div>
        <div class="step-time">&lt; 3s Latency</div>
      </div>
      <div class="step-headline">Automated DM Dispatch</div>
      <div class="step-desc">Meta Business Suite native webhook fires instantly, sending a private 1-on-1 direct message.</div>
      <div class="step-highlight">🚀 Zero drop-off • In-app frictionless delivery</div>
    </div>

    <div class="step-card">
      <div class="step-header">
        <div class="step-pill">Stage 03</div>
        <div class="step-time">2-Step Filter</div>
      </div>
      <div class="step-headline">Interactive Qualification</div>
      <div class="step-desc">Conversational micro-bot collects budget, timeline, and use-case inside Instagram/Messenger.</div>
      <div class="step-highlight">🎯 Filters tire-kickers before sales outreach</div>
    </div>

    <div class="step-card active-glow">
      <div class="step-header">
        <div class="step-pill">Stage 04</div>
        <div class="step-time">&lt; 60s Handoff</div>
      </div>
      <div class="step-headline">CRM & WhatsApp Dispatch</div>
      <div class="step-desc">Qualified lead syncs to CRM; WhatsApp alert sent to sales team with full context.</div>
      <div class="step-highlight">📈 CAPI Signal feedback improves Meta targeting</div>
    </div>
  </div>

  <div class="metrics-bar">
    <div class="metric-item">
      <div class="metric-val">+340%</div>
      <div class="metric-lbl">Lead-to-Call Rate</div>
    </div>
    <div class="metric-divider"></div>
    <div class="metric-item">
      <div class="metric-val">-38%</div>
      <div class="metric-lbl">Customer Acquisition Cost</div>
    </div>
    <div class="metric-divider"></div>
    <div class="metric-item">
      <div class="metric-val">&lt; 60s</div>
      <div class="metric-lbl">Lead Response Velocity</div>
    </div>
  </div>
</body>
</html>
    `;

    const htmlPath = path.resolve(__dirname, 'meta_ad_infographic.html');
    const pngPath = path.resolve(__dirname, 'meta_comment_to_dm_architecture.png');
    fs.writeFileSync(htmlPath, htmlContent);

    const browser = await puppeteer.launch({
        headless: 'shell',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1080, height: 1080, deviceScaleFactor: 2 });
    await page.goto(`file://${htmlPath}`, { waitUntil: 'domcontentloaded' });
    await page.screenshot({ path: pngPath });
    await browser.close();

    console.log(`[✓] Infographic rendered successfully: ${pngPath}`);
})();
