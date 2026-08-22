const puppeteer = require('puppeteer');
const { loadConfig } = require('./config_loader.cjs');
// Phase 1: how many of this format to build comes from pipeline_config.json.
const COUNT = loadConfig().format_mix['carousel'] || 0;
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

(async () => {
    // Phase 1: a count of 0 makes this format unused, not unavailable. Return
    // before launching Chrome — the renderer below is intact and untouched.
    if (COUNT === 0) {
        console.log('format_mix.carousel = 0 — no carousels to build. Skipping.');
        return;
    }

    const today = new Date();
    const offset = today.getTimezoneOffset();
    const localDate = new Date(today.getTime() - (offset*60*1000));
    const d = localDate.toISOString().slice(0, 10);
    const dateStr = d.replace(/-/g, '');
    const outDir = path.resolve(__dirname, `./carousel-routine/output/${d}/carousel-branded`);
    fs.mkdirSync(outDir, { recursive: true });

    console.log("Launching Chrome using puppeteer...");
    const browser = await puppeteer.launch({
        headless: 'shell',
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-gpu',
          '--disable-dev-shm-usage'
        ]
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1080, height: 1080, deviceScaleFactor: 2 });

    for (let idx = 1; idx <= COUNT; idx++) {
        const jsonFile = `./carousel_data_${idx}.json`;
        if (!fs.existsSync(jsonFile) && idx > 1) continue;

        console.log(`\n--- Building Carousel #${idx} ---`);
        const tempSlideDir = `./carousel-routine/temp/carousel-branded-${idx}`;
        execSync(`python3 generate_carousel_today.py ${jsonFile} ${tempSlideDir}`, { cwd: __dirname });

        const carouselOutDir = `${outDir}/carousel-${idx}`;
        fs.mkdirSync(carouselOutDir, { recursive: true });

        for (let i = 1; i <= 7; i++) {
            const slidePath = `file://${path.resolve(__dirname, `${tempSlideDir}/slide-0${i}.html`)}`;
            await page.goto(slidePath, { waitUntil: 'domcontentloaded', timeout: 15000 });
            const pngPath = `${carouselOutDir}/slide-0${i}.png`;
            await page.screenshot({ path: pngPath });
        }

        const pdfHtmlPath = `${carouselOutDir}/carousel.html`;
        let pdfHtml = `<html><body style="margin:0;padding:0;">`;
        for (let i = 1; i <= 7; i++) {
            pdfHtml += `<img src="file://${path.resolve(carouselOutDir + '/slide-0' + i + '.png')}" style="width:1080px;height:1080px;display:block;page-break-after:always;">`;
        }
        pdfHtml += `</body></html>`;
        fs.writeFileSync(pdfHtmlPath, pdfHtml);

        await page.goto(`file://${path.resolve(pdfHtmlPath)}`, { waitUntil: 'domcontentloaded', timeout: 15000 });
        const pdfPath = path.join(outDir, `linkedin-carousel-${idx}.pdf`);
        await page.pdf({ 
            path: pdfPath, 
            width: 1080,
            height: 1080,
            printBackground: true 
        });
        console.log(`Generated PDF #${idx} at ${pdfPath}`);

        const destDir = path.resolve(__dirname, './slack_downloads');
        fs.mkdirSync(destDir, { recursive: true });
        fs.copyFileSync(pdfPath, path.join(destDir, `carousel-${idx}.pdf`));
        if (idx === 1) {
            fs.copyFileSync(pdfPath, path.join(destDir, `carousel-${dateStr}.pdf`));
        }
    }

    await browser.close();
    console.log("All Carousels build complete!");
})();
