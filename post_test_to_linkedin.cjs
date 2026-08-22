const path = require('path');
const { publishImagePost } = require('./linkedin_api_client.cjs');

const postText = `Sending Meta Ad traffic to a 5-field landing page in 2026 is burning 40%+ of your ad budget.

Here’s what top performance marketing teams are shifting to instead:
👉 The Native "Comment-to-DM" Speed-to-Lead Architecture.

When a prospect sees your ad, the friction of:
• Clicking out of Instagram / Facebook
• Waiting for an external landing page to load
• Typing in name, email, and company details
...creates massive drop-offs before you ever capture the lead.

With Meta’s latest conversational updates and automated DM triggers, the dynamic has completely flipped:

1️⃣ The Micro-Commitment Hook:
Instead of asking for an immediate form fill, your ad creative invites a single high-intent comment:
💬 "Drop 'FLOW' below and I'll send the complete automation blueprint to your DMs."

2️⃣ Sub-3-Second Automated DM Trigger:
The second they comment, Meta’s native rule / webhook fires a private direct message instantly.
Zero friction. The prospect stays inside the app they are already scrolling.

3️⃣ 2-Step In-App Qualification:
A lightweight conversational bot asks 2 rapid qualification questions (e.g., Monthly Ad Spend & Primary Objective).
You instantly separate high-ticket buyers from casual browsers.

4️⃣ 60-Second WhatsApp & CRM Dispatch:
The moment a prospect qualifies:
• Data is pushed directly into your CRM
• An instant WhatsApp alert is dispatched to your sales team with full context
• A verified 'Lead' event is fed back via Meta Conversions API (CAPI)

The result?
⚡ +340% higher lead-to-conversation rate
📉 -38% reduction in Cost Per Qualified Acquisition
🔥 Meta's auction algorithm heavily rewards the high comment velocity with lower CPMs.

Are you still sending 100% of cold ad traffic to traditional landing pages, or testing conversational in-app funnels?

Let's discuss in the comments! 👇

#MetaAds #PerformanceMarketing #GrowthMarketing #Automation #LeadGeneration #DigitalMarketing #AI`;

const imagePath = path.resolve(__dirname, 'meta_comment_to_dm_architecture.png');

(async () => {
    try {
        console.log('Publishing live test post to LinkedIn via API...');
        const result = await publishImagePost(
            imagePath,
            postText,
            'Meta Ads Comment-to-DM Architecture Infographic'
        );
        console.log('\n============================================================');
        console.log('✓ POST PUBLISHED SUCCESSFULLY TO LINKEDIN VIA DIRECT API!');
        console.log('============================================================');
        console.log('API Result:', JSON.stringify(result, null, 2));
    } catch (err) {
        console.error('Failed to publish post:', err);
        process.exit(1);
    }
})();
