const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

(async () => {
    console.log("🚀 Building Adhoc Carousel PDFs for Aug 14 and Aug 16...");

    const dates = [
        { dateStr: "2026-08-14", jsonFile: "./carousel_data_aug14.json", pdfName: "carousel-aug14.pdf", outDir: "./carousel-routine/output/2026-08-14/carousel-branded/carousel-1" },
        { dateStr: "2026-08-16", jsonFile: "./carousel_data_aug16.json", pdfName: "carousel-aug16.pdf", outDir: "./carousel-routine/output/2026-08-16/carousel-branded/carousel-1" }
    ];

    const browser = await puppeteer.launch({
        headless: 'shell',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1080, height: 1080, deviceScaleFactor: 2 });

    for (const item of dates) {
        console.log(`\n--- Generating Slides for ${item.dateStr} ---`);
        fs.mkdirSync(item.outDir, { recursive: true });
        const tempSlideDir = `./carousel-routine/temp/${item.dateStr}`;
        execSync(`python3 generate_carousel_today.py ${item.jsonFile} ${tempSlideDir}`, { cwd: __dirname });

        for (let i = 1; i <= 7; i++) {
            const slidePath = `file://${path.resolve(__dirname, `${tempSlideDir}/slide-0${i}.html`)}`;
            await page.goto(slidePath, { waitUntil: 'domcontentloaded', timeout: 15000 });
            const pngPath = `${item.outDir}/slide-0${i}.png`;
            await page.screenshot({ path: pngPath });
        }

        const pdfHtmlPath = `${item.outDir}/carousel.html`;
        let pdfHtml = `<html><body style="margin:0;padding:0;">`;
        for (let i = 1; i <= 7; i++) {
            pdfHtml += `<img src="file://${path.resolve(item.outDir + '/slide-0' + i + '.png')}" style="width:1080px;height:1080px;display:block;page-break-after:always;">`;
        }
        pdfHtml += `</body></html>`;
        fs.writeFileSync(pdfHtmlPath, pdfHtml);

        await page.goto(`file://${path.resolve(pdfHtmlPath)}`, { waitUntil: 'domcontentloaded', timeout: 15000 });
        const pdfPath = path.resolve(__dirname, `./slack_downloads/${item.pdfName}`);
        fs.mkdirSync(path.resolve(__dirname, './slack_downloads'), { recursive: true });
        await page.pdf({ 
            path: pdfPath, 
            width: 1080,
            height: 1080,
            printBackground: true 
        });
        console.log(`✓ Generated PDF for ${item.dateStr} at ${pdfPath}`);
    }

    await browser.close();
    console.log("🎉 All Adhoc Carousels generated successfully!");
})();
