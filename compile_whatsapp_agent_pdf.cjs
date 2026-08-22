const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

(async () => {
    console.log("Launching Puppeteer to build WhatsApp Agent Carousel PDF...");
    const browser = await puppeteer.launch({
        executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        headless: true,
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-gpu',
          '--disable-dev-shm-usage',
          '--use-mock-keychain',
          '--password-store=basic',
          '--disable-extensions'
        ]
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1080, height: 1080, deviceScaleFactor: 2 });

    const outDir = path.resolve(__dirname, './user_uploads/whatsapp_agent_output');
    fs.mkdirSync(outDir, { recursive: true });

    for (let i = 1; i <= 7; i++) {
        const slidePath = `file://${path.resolve(__dirname, `./carousel-routine/temp/whatsapp-agent-branded/slide-0${i}.html`)}`;
        await page.goto(slidePath, { waitUntil: 'domcontentloaded', timeout: 15000 });
        const pngPath = `${outDir}/slide-0${i}.png`;
        await page.screenshot({ path: pngPath });
        console.log(`Generated ${pngPath}`);
    }

    const pdfHtmlPath = `${outDir}/carousel.html`;
    let pdfHtml = `<html><body style="margin:0;padding:0;">`;
    for (let i = 1; i <= 7; i++) {
        pdfHtml += `<img src="file://${path.resolve(outDir + '/slide-0' + i + '.png')}" style="width:1080px;height:1080px;display:block;page-break-after:always;">`;
    }
    pdfHtml += `</body></html>`;
    fs.writeFileSync(pdfHtmlPath, pdfHtml);

    await page.goto(`file://${path.resolve(pdfHtmlPath)}`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    const pdfPath = path.resolve(__dirname, `whatsapp_agent_carousel.pdf`);
    await page.pdf({ 
        path: pdfPath, 
        width: 1080,
        height: 1080,
        printBackground: true 
    });
    console.log(`Generated PDF at ${pdfPath}`);

    await browser.close();
    console.log("Carousel PDF compilation complete!");
})();
