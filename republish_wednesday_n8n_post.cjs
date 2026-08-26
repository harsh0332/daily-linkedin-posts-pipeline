const path = require('path');
const { publishDocumentPost } = require('./linkedin_api_client.cjs');

const title = "Sync Offline Revenue to Meta via n8n PIPELINE";
const caption = `The biggest blindspot in high-ticket Meta Ad campaigns:
Meta optimizes in the dark.

If your sales team closes deals on calls, on WhatsApp, or inside CRM pipelines, Meta's auction engine has zero idea which leads generated revenue.

Here is how we automate the feedback loop using n8n and Meta Conversions API (CAPI):
⚡ 1. Deal marked 'Closed-Won' in Sheets / CRM
⚡ 2. Real-time n8n webhook triggers
⚡ 3. SHA-256 encrypted hashing of customer data (9.0+ EMQ score)
⚡ 4. Transaction value fed back to Meta Ads Manager

Within 14 days, Advantage+ recalculates bidding toward high-value buyers.

Swipe through the complete architecture above! 👆

#n8n #Automation #MetaAds #ConversionsAPI #GrowthEngineering #B2BSales #DataPipeline`;

const pdfPath = path.resolve(__dirname, 'linkedin-carousel-2.pdf');

(async () => {
    try {
        console.log(`[*] Publishing correct n8n CAPI Carousel post to LinkedIn...`);
        console.log(`[*] PDF Path: ${pdfPath}`);
        const result = await publishDocumentPost(pdfPath, title, caption);
        console.log('\n' + '='.repeat(60));
        console.log('✓ N8N CAPI CAROUSEL POST PUBLISHED SUCCESSFULLY!');
        console.log('============================================================');
        console.log('Result:', JSON.stringify(result, null, 2));
    } catch (e) {
        console.error('Failed to publish post:', e);
        process.exit(1);
    }
})();
