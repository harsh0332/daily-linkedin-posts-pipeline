const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

(async () => {
    const userDataDir = path.join(__dirname, 'chrome-session');
    console.log("Launching Chrome to inspect recent LinkedIn posts...");

    const browser = await puppeteer.launch({
        executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        headless: true,
        userDataDir: userDataDir,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-gpu',
            '--window-size=1280,1200'
        ]
    });

    try {
        const pages = await browser.pages();
        const page = pages[0] || await browser.newPage();
        await page.setViewport({ width: 1280, height: 1200 });

        console.log("Navigating to LinkedIn recent activity...");
        await page.goto('https://www.linkedin.com/in/harshchouksey/recent-activity/all/', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await new Promise(r => setTimeout(r, 6000));

        const screenshotPath = path.resolve(__dirname, 'recent_linkedin_posts_audit.png');
        await page.screenshot({ path: screenshotPath, fullPage: false });
        console.log(`[✓] Screenshot saved to: ${screenshotPath}`);

        // Extract titles / commentary of recent posts
        const postTexts = await page.evaluate(() => {
            const feedItems = Array.from(document.querySelectorAll('.feed-shared-update-v2, .feed-shared-activity, div[data-urn*="urn:li:activity"]'));
            return feedItems.slice(0, 10).map((el, i) => {
                const textEl = el.querySelector('.feed-shared-update-v2__description, .update-components-text, .feed-shared-text');
                const titleEl = el.querySelector('.update-components-article__title, .feed-shared-document-component');
                return {
                    index: i + 1,
                    text: textEl ? textEl.innerText.substring(0, 200) : 'No text',
                    hasDocument: !!el.querySelector('iframe, embed, .feed-shared-document-component, .update-components-document')
                };
            });
        });

        console.log("Extracted Posts:\n", JSON.stringify(postTexts, null, 2));

    } catch (err) {
        console.error("Error inspecting LinkedIn:", err);
    } finally {
        await browser.close();
    }
})();
