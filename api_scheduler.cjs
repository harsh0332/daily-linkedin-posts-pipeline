const fs = require('fs');
const path = require('path');
const { publishTextPost, publishDocumentPost } = require('./linkedin_api_client.cjs');

const QUEUE_FILE = path.resolve(__dirname, 'scheduled_posts_queue.json');
const STATE_FILE = path.resolve(__dirname, 'pipeline_state.json');
const USED_TOPICS_FILE = path.resolve(__dirname, 'used_topics.json');

/**
 * Load the existing scheduling queue
 */
function loadQueue() {
    if (fs.existsSync(QUEUE_FILE)) {
        try {
            return JSON.parse(fs.readFileSync(QUEUE_FILE, 'utf8'));
        } catch (e) {
            console.error('Error reading queue file:', e.message);
        }
    }
    return [];
}

/**
 * Save the scheduling queue
 */
function saveQueue(queue) {
    fs.writeFileSync(QUEUE_FILE, JSON.stringify(queue, null, 2));
}

/**
 * Queue a new 5-post batch from linkedin_posts_today.txt
 */
function queueCurrentBatch(startDateStr = '2026-08-31') {
    const rawContent = fs.readFileSync(path.resolve(__dirname, 'linkedin_posts_today.txt'), 'utf8');
    const postsBlocks = rawContent.split(/={10,}\n(?:\d+\.\s+)?(CAROUSEL\s+\d+|TEXT\s+\d+|POLL\s+\d+|INFOGRAPHIC\s+\d+)\n={10,}/i);

    const posts = [];
    let carouselCount = 0;

    for (let i = 1; i < postsBlocks.length; i += 2) {
        const typeHeader = (postsBlocks[i] || '').trim().toUpperCase();
        const content = (postsBlocks[i + 1] || '').trim();
        if (!content) continue;

        const isCarousel = typeHeader.includes('CAROUSEL');
        let title = '';
        let caption = content;
        let pdfPath = null;

        if (isCarousel) {
            carouselCount++;
            const hookMatch = content.match(/Hook:\s*([^\n]+)/i);
            title = hookMatch ? hookMatch[1].trim() : `Carousel ${carouselCount}`;

            const captionMatch = content.match(/CAROUSEL CAPTION:\s*([\s\S]+?)$/i);
            if (captionMatch) {
                caption = captionMatch[1].trim();
            }

            pdfPath = path.resolve(__dirname, `slack_downloads/carousel-${carouselCount}.pdf`);
            if (!fs.existsSync(pdfPath)) {
                // Check in carousel-routine output
                const outDir = path.resolve(__dirname, `carousel-routine/output/2026-08-21/carousel-branded`);
                const altPdf = path.join(outDir, `linkedin-carousel-${carouselCount}.pdf`);
                if (fs.existsSync(altPdf)) {
                    pdfPath = altPdf;
                }
            }
        } else {
            // Text post
            const firstLine = content.split('\n')[0].replace(/^#+\s*/, '').trim();
            title = firstLine.slice(0, 60);
        }

        posts.push({
            type: isCarousel ? 'carousel' : 'text',
            title: title,
            caption: caption,
            pdfPath: pdfPath
        });
    }

    // Assign Weekday Dates @ 9:30 AM IST
    const queue = loadQueue();
    const parts = startDateStr.split('-').map(Number);
    let curr = new Date(parts[0], parts[1] - 1, parts[2], 9, 30, 0); // 9:30 AM

    const newBatch = [];
    for (let i = 0; i < posts.length; i++) {
        // Skip weekends
        while (curr.getDay() === 0 || curr.getDay() === 6) {
            curr.setDate(curr.getDate() + 1);
        }

        const yyyy = curr.getFullYear();
        const mm = String(curr.getMonth() + 1).padStart(2, '0');
        const dd = String(curr.getDate()).padStart(2, '0');
        const dateFormatted = `${yyyy}-${mm}-${dd}`;

        const postEntry = {
            id: `post_${Date.now()}_${i + 1}`,
            scheduled_date: dateFormatted,
            scheduled_time: '09:30 AM IST',
            scheduled_iso: `${dateFormatted}T09:30:00+05:30`,
            type: posts[i].type,
            title: posts[i].title,
            caption: posts[i].caption,
            pdf_path: posts[i].pdfPath,
            status: 'pending',
            created_at: new Date().toISOString()
        };

        newBatch.push(postEntry);
        curr.setDate(curr.getDate() + 1);
    }

    // Merge or replace pending posts in queue
    const updatedQueue = [...queue.filter(q => q.status !== 'pending'), ...newBatch];
    saveQueue(updatedQueue);

    console.log('='.repeat(60));
    console.log(`✓ QUEUED ${newBatch.length} POSTS FOR DIRECT API SCHEDULING`);
    console.log('='.repeat(60));
    newBatch.forEach((p, idx) => {
        console.log(`[${idx + 1}] ${p.scheduled_date} @ ${p.scheduled_time} | ${p.type.toUpperCase().padEnd(8)} | ${p.title}`);
    });
    console.log('='.repeat(60));

    // Update pipeline_state.json
    const lastDate = newBatch[newBatch.length - 1].scheduled_date;
    fs.writeFileSync(STATE_FILE, JSON.stringify({
        last_scheduled_date: "2026-08-30",
        next_batch_end_date: lastDate,
        total_queued: updatedQueue.length,
        last_updated: new Date().toISOString()
    }, null, 2));

    // Update used_topics.json
    if (fs.existsSync(USED_TOPICS_FILE)) {
        try {
            const usedTopics = JSON.parse(fs.readFileSync(USED_TOPICS_FILE, 'utf8'));
            newBatch.forEach(p => {
                if (!usedTopics.includes(p.title)) {
                    usedTopics.push(p.title);
                }
            });
            fs.writeFileSync(USED_TOPICS_FILE, JSON.stringify(usedTopics, null, 2));
            console.log(`[✓] Updated used_topics.json with ${newBatch.length} new topics.`);
        } catch (e) {
            console.error('Error updating used_topics.json:', e.message);
        }
    }

    return newBatch;
}

/**
 * Check queue and publish any posts that are due now via Direct API
 */
async function processDuePosts() {
    const queue = loadQueue();
    const now = new Date();
    let publishedCount = 0;

    for (const post of queue) {
        if (post.status === 'pending') {
            const targetTime = new Date(post.scheduled_iso);
            if (targetTime <= now) {
                console.log(`\n[*] Publishing due post via API: [${post.type}] ${post.title}...`);
                try {
                    let result;
                    if (post.type === 'carousel') {
                        result = await publishDocumentPost(post.pdf_path, post.title, post.caption);
                    } else {
                        result = await publishTextPost(post.caption);
                    }

                    post.status = 'published';
                    post.published_at = new Date().toISOString();
                    post.api_result = result;
                    publishedCount++;
                    console.log(`[✓] Post published successfully via API! (URN: ${result.headers?.['x-restli-id'] || 'ok'})`);
                } catch (err) {
                    console.error(`[ERROR] Failed to publish post ${post.id}:`, err.message);
                    post.last_error = err.message;
                }
            }
        }
    }

    if (publishedCount > 0) {
        saveQueue(queue);
    }
    return publishedCount;
}

// CLI handler
if (require.main === module) {
    const action = process.argv[2] || 'queue';
    if (action === 'queue') {
        const start = process.argv[3] || '2026-08-31';
        queueCurrentBatch(start);
    } else if (action === 'process' || action === 'run') {
        processDuePosts().then(count => {
            console.log(`Processed ${count} due posts.`);
        });
    } else if (action === 'list') {
        const q = loadQueue();
        console.log(`Queue contains ${q.length} post(s):`);
        console.table(q.map(p => ({ date: p.scheduled_date, time: p.scheduled_time, type: p.type, status: p.status, title: p.title })));
    }
}

module.exports = {
    loadQueue,
    queueCurrentBatch,
    processDuePosts
};
