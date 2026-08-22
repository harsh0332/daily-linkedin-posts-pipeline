const puppeteer = require('puppeteer');
const { loadConfig } = require('./config_loader.cjs');
// Phase 1: how many of this format to build comes from pipeline_config.json.
const COUNT = loadConfig().format_mix['infographic'] || 0;
const http = require('http');
const fs = require('fs');
const path = require('path');

(async () => {
  console.log('Starting infographic screenshot compilation...');

  // Phase 1: a count of 0 makes this format unused, not unavailable. Return
  // before launching Chrome — the renderer below is intact and untouched.
  if (COUNT === 0) {
    console.log('format_mix.infographic = 0 — no infographics to build. Skipping.');
    return;
  }

  const templatePath = path.join(__dirname, 'linkedin-infographic-template.html');
  if (!fs.existsSync(templatePath)) {
    console.error("Error: linkedin-infographic-template.html not found!");
    process.exit(1);
  }
  const template = fs.readFileSync(templatePath, 'utf8');

  const browser = await puppeteer.launch({
    headless: 'shell',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1080, height: 1080, deviceScaleFactor: 1 });

  const today = new Date();
  const offset = today.getTimezoneOffset();
  const localDate = new Date(today.getTime() - (offset*60*1000));
  const d = localDate.toISOString().slice(0, 10).replace(/-/g, '');

  for (let idx = 1; idx <= COUNT; idx++) {
    const jsonPath = path.join(__dirname, `infographic_data_${idx}.json`);
    if (!fs.existsSync(jsonPath) && idx > 1) continue;
    const actualJsonPath = fs.existsSync(jsonPath) ? jsonPath : path.join(__dirname, 'infographic_data.json');
    if (!fs.existsSync(actualJsonPath)) continue;

    const data = JSON.parse(fs.readFileSync(actualJsonPath, 'utf8'));

    const barRowsHtml = (data.bars || []).map(bar => {
      return `    <div class="bar-row">
        <div class="bar-info">
          <span class="bar-label">${bar.label}</span>
          <span class="bar-value">${bar.value}</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill" style="width: ${bar.value}; background-color: ${bar.color || '#5E6AD2'};"></div>
        </div>
      </div>`;
    }).join('\n');
    
    let htmlContent = template
      .replace("{{BADGE}}", data.badge || "📊 Insights")
      .replace("{{DATE_LABEL}}", data.date_label || "")
      .replace("{{TITLE_MAIN}}", data.title_main || "")
      .replace("{{TITLE_SPAN}}", data.title_span || "")
      .replace("{{SUBTITLE}}", data.subtitle || "")
      .replace("{{BAR_ROWS}}", barRowsHtml)
      .replace("{{TAKEAWAY_NUM}}", data.takeaway_num || "")
      .replace("{{TAKEAWAY_TEXT}}", data.takeaway_text || "")
      .replace("{{SOURCE}}", data.source || "");

    const htmlFileName = `linkedin-infographic-${idx}.html`;
    fs.writeFileSync(path.join(__dirname, htmlFileName), htmlContent, 'utf8');

    const server = http.createServer((req, res) => {
      res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'});
      res.end(fs.readFileSync(path.join(__dirname, htmlFileName)));
    });
    
    const port = 8760 + idx;
    await new Promise(r => server.listen(port, r));

    await page.goto(`http://localhost:${port}`, { waitUntil: 'domcontentloaded' });
    await page.evaluate(() => document.fonts.ready);
    
    const outputPath = path.join(__dirname, `linkedin-infographic-${idx}.png`);
    await page.screenshot({ path: outputPath, clip: { x:0, y:0, width:1080, height:1080 } });
    console.log(`✓ Infographic #${idx} screenshot saved to ${outputPath}`);
    
    if (idx === 1) {
      fs.copyFileSync(outputPath, path.join(__dirname, `linkedin-infographic-${d}.png`));
    }
    server.close();
  }

  await browser.close();
  console.log('All Infographics compilation complete!');
})();
