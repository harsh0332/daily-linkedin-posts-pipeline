const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { publishTextPost, publishDocumentPost } = require('./linkedin_api_client.cjs');

// Auto-bootstrap credentials from environment secrets if needed
function bootstrapCredentials() {
    const credPath = path.resolve(__dirname, 'linkedin_api_credentials.json');
    if (!fs.existsSync(credPath)) {
        const token = process.env.LINKEDIN_ACCESS_TOKEN;
        const urn = process.env.LINKEDIN_PERSON_URN || 'urn:li:person:bx3EebOU23';
        if (!token) {
            throw new Error('LINKEDIN_ACCESS_TOKEN is missing in environment variables / GitHub Secrets!');
        }
        const creds = {
            name: 'Harsh Chouksey',
            person_urn: urn,
            access_token: token,
            expires_in: 5184000
        };
        fs.writeFileSync(credPath, JSON.stringify(creds, null, 2));
        console.log('[✓] Bootstrapped linkedin_api_credentials.json from GitHub Secrets.');
    }
}

async function runDailyPublish() {
    console.log('='.repeat(60));
    console.log('🚀 RUNNING AUTONOMOUS DAILY LINKEDIN PUBLISHING JOB');
    console.log('='.repeat(60));

    bootstrapCredentials();

    const now = new Date();
    const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const currentDay = dayNames[now.getDay()];
    console.log(`[*] Current Run Time: ${now.toISOString()} (${currentDay})`);

    // Check if weekend
    if (now.getDay() === 0 || now.getDay() === 6) {
        console.log('[*] Weekend detected. Skipping publishing as per weekdays-only policy.');
        return;
    }

    const queueFile = path.resolve(__dirname, 'scheduled_posts_queue.json');
    let queue = [];
    if (fs.existsSync(queueFile)) {
        queue = JSON.parse(fs.readFileSync(queueFile, 'utf8'));
    }

    // Find first pending post in queue
    const pendingPost = queue.find(p => p.status === 'pending');

    if (pendingPost) {
        console.log(`\n[*] Found pending post in queue: [${pendingPost.type.toUpperCase()}] ${pendingPost.title}`);
        let result;
        if (pendingPost.type === 'carousel') {
            console.log(`[*] Publishing Carousel PDF: ${pendingPost.pdf_path}`);
            result = await publishDocumentPost(pendingPost.pdf_path, pendingPost.title, pendingPost.caption);
        } else {
            console.log(`[*] Publishing Text Post...`);
            result = await publishTextPost(pendingPost.caption);
        }

        pendingPost.status = 'published';
        pendingPost.published_at = new Date().toISOString();
        pendingPost.api_result = result;
        fs.writeFileSync(queueFile, JSON.stringify(queue, null, 2));

        console.log('\n' + '='.repeat(60));
        console.log(`✓ POST PUBLISHED SUCCESSFULLY TO LINKEDIN!`);
        console.log(`  URN: ${result.headers?.['x-restli-id'] || 'urn:li:share:success'}`);
        console.log('='.repeat(60));
    } else {
        console.log('[*] No pending post in queue. Running preflight & pipeline generation...');
        // Preflight & generation path
        execSync('python3 preflight.py', { stdio: 'inherit' });
        console.log('[✓] Preflight passed. Generating daily content...');
        execSync('python3 generate_all_content.py', { stdio: 'inherit' });
        execSync('node build_carousel_today.cjs', { stdio: 'inherit' });
        
        // Queue and publish
        const { queueCurrentBatch, processDuePosts } = require('./api_scheduler.cjs');
        queueCurrentBatch();
        await processDuePosts();
    }
}

if (require.main === module) {
    runDailyPublish().catch(err => {
        console.error('\n[FATAL ERROR in daily publish]:', err);
        process.exit(1);
    });
}
