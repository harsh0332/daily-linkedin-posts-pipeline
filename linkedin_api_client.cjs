const fs = require('fs');
const path = require('path');
const https = require('https');

// Load credentials
function getCredentials() {
    const credPath = path.resolve(__dirname, 'linkedin_api_credentials.json');
    if (!fs.existsSync(credPath)) {
        throw new Error('Missing linkedin_api_credentials.json. Run `node get_linkedin_token.cjs` first.');
    }
    return JSON.parse(fs.readFileSync(credPath, 'utf8'));
}

const LINKEDIN_API_VERSION = '202601';

/**
 * Generic HTTPS Request Helper for LinkedIn REST API
 */
function apiRequest(options, postData = null, isBinary = false) {
    return new Promise((resolve, reject) => {
        const req = https.request(options, (res) => {
            const chunks = [];
            res.on('data', chunk => chunks.push(chunk));
            res.on('end', () => {
                const rawBody = Buffer.concat(chunks).toString('utf8');
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    try {
                        const json = rawBody ? JSON.parse(rawBody) : { status: res.statusCode, headers: res.headers };
                        resolve(json);
                    } catch (e) {
                        resolve(rawBody);
                    }
                } else {
                    reject(new Error(`LinkedIn API [HTTP ${res.statusCode}]: ${rawBody}`));
                }
            });
        });

        req.on('error', reject);
        if (postData) {
            if (isBinary) {
                req.write(postData);
            } else {
                req.write(typeof postData === 'string' ? postData : JSON.stringify(postData));
            }
        }
        req.end();
    });
}

/**
 * Publish a Text Post directly via LinkedIn API
 */
async function publishTextPost(commentary) {
    const creds = getCredentials();
    console.log(`[*] Publishing text post to ${creds.name} (${creds.person_urn})...`);

    const payload = {
        author: creds.person_urn,
        commentary: commentary,
        visibility: 'PUBLIC',
        distribution: {
            feedDistribution: 'MAIN_FEED',
            targetEntities: [],
            thirdPartyDistributionChannels: []
        },
        lifecycleState: 'PUBLISHED',
        isReshareDisabledByAuthor: false
    };

    const options = {
        hostname: 'api.linkedin.com',
        path: '/rest/posts',
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${creds.access_token}`,
            'LinkedIn-Version': LINKEDIN_API_VERSION,
            'X-Restli-Protocol-Version': '2.0.0',
            'Content-Type': 'application/json'
        }
    };

    const result = await apiRequest(options, payload);
    console.log(`[✓] Text post published successfully via API!`);
    return result;
}

/**
 * Upload a PDF Document and publish a Carousel Post directly via LinkedIn API
 */
async function publishDocumentPost(pdfFilePath, title, commentary) {
    const creds = getCredentials();
    if (!fs.existsSync(pdfFilePath)) {
        throw new Error(`PDF file not found: ${pdfFilePath}`);
    }

    console.log(`[*] Step 1: Initializing document upload for: ${path.basename(pdfFilePath)}...`);
    const initOptions = {
        hostname: 'api.linkedin.com',
        path: '/rest/documents?action=initializeUpload',
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${creds.access_token}`,
            'LinkedIn-Version': LINKEDIN_API_VERSION,
            'X-Restli-Protocol-Version': '2.0.0',
            'Content-Type': 'application/json'
        }
    };

    const initPayload = {
        initializeUploadRequest: {
            owner: creds.person_urn
        }
    };

    const initRes = await apiRequest(initOptions, initPayload);
    const uploadUrl = initRes.value.uploadUrl;
    const documentUrn = initRes.value.document;
    console.log(`[✓] Document initialized (URN: ${documentUrn})`);

    console.log(`[*] Step 2: Uploading PDF binary (${(fs.statSync(pdfFilePath).size / 1024).toFixed(1)} KB)...`);
    const pdfBuffer = fs.readFileSync(pdfFilePath);
    const parsedUploadUrl = new URL(uploadUrl);

    const uploadOptions = {
        hostname: parsedUploadUrl.hostname,
        path: parsedUploadUrl.pathname + parsedUploadUrl.search,
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${creds.access_token}`,
            'Content-Type': 'application/pdf',
            'Content-Length': pdfBuffer.length
        }
    };

    await apiRequest(uploadOptions, pdfBuffer, true);
    console.log(`[✓] Document binary uploaded!`);

    console.log(`[*] Step 3: Publishing Carousel post with attached document...`);
    const postPayload = {
        author: creds.person_urn,
        commentary: commentary,
        visibility: 'PUBLIC',
        distribution: {
            feedDistribution: 'MAIN_FEED',
            targetEntities: [],
            thirdPartyDistributionChannels: []
        },
        content: {
            media: {
                title: title || 'LinkedIn Carousel',
                id: documentUrn
            }
        },
        lifecycleState: 'PUBLISHED',
        isReshareDisabledByAuthor: false
    };

    const postOptions = {
        hostname: 'api.linkedin.com',
        path: '/rest/posts',
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${creds.access_token}`,
            'LinkedIn-Version': LINKEDIN_API_VERSION,
            'X-Restli-Protocol-Version': '2.0.0',
            'Content-Type': 'application/json'
        }
    };

    const postResult = await apiRequest(postOptions, postPayload);
    console.log(`[✓] Carousel document post published successfully via API!`);
    return postResult;
}

/**
 * Upload an Image and publish an Image Post directly via LinkedIn API
 */
async function publishImagePost(imageFilePath, commentary, altText = '') {
    const creds = getCredentials();
    if (!fs.existsSync(imageFilePath)) {
        throw new Error(`Image file not found: ${imageFilePath}`);
    }

    console.log(`[*] Step 1: Initializing image upload for: ${path.basename(imageFilePath)}...`);
    const initOptions = {
        hostname: 'api.linkedin.com',
        path: '/rest/images?action=initializeUpload',
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${creds.access_token}`,
            'LinkedIn-Version': LINKEDIN_API_VERSION,
            'X-Restli-Protocol-Version': '2.0.0',
            'Content-Type': 'application/json'
        }
    };

    const initPayload = {
        initializeUploadRequest: {
            owner: creds.person_urn
        }
    };

    const initRes = await apiRequest(initOptions, initPayload);
    const uploadUrl = initRes.value.uploadUrl;
    const imageUrn = initRes.value.image;
    console.log(`[✓] Image initialized (URN: ${imageUrn})`);

    console.log(`[*] Step 2: Uploading image binary (${(fs.statSync(imageFilePath).size / 1024).toFixed(1)} KB)...`);
    const imgBuffer = fs.readFileSync(imageFilePath);
    const parsedUploadUrl = new URL(uploadUrl);

    const uploadOptions = {
        hostname: parsedUploadUrl.hostname,
        path: parsedUploadUrl.pathname + parsedUploadUrl.search,
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${creds.access_token}`,
            'Content-Type': 'image/png',
            'Content-Length': imgBuffer.length
        }
    };

    await apiRequest(uploadOptions, imgBuffer, true);
    console.log(`[✓] Image binary uploaded!`);

    console.log(`[*] Step 3: Publishing Post with attached image...`);
    const postPayload = {
        author: creds.person_urn,
        commentary: commentary,
        visibility: 'PUBLIC',
        distribution: {
            feedDistribution: 'MAIN_FEED',
            targetEntities: [],
            thirdPartyDistributionChannels: []
        },
        content: {
            media: {
                title: altText || 'Meta Ads Comment-to-DM Architecture',
                id: imageUrn
            }
        },
        lifecycleState: 'PUBLISHED',
        isReshareDisabledByAuthor: false
    };

    const postOptions = {
        hostname: 'api.linkedin.com',
        path: '/rest/posts',
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${creds.access_token}`,
            'LinkedIn-Version': LINKEDIN_API_VERSION,
            'X-Restli-Protocol-Version': '2.0.0',
            'Content-Type': 'application/json'
        }
    };

    const postResult = await apiRequest(postOptions, postPayload);
    console.log(`[✓] Image post published successfully via API!`);
    return postResult;
}

module.exports = {
    getCredentials,
    publishTextPost,
    publishImagePost,
    publishDocumentPost
};

// Quick CLI runner for test or manual publishing
if (require.main === module) {
    const creds = getCredentials();
    console.log('LinkedIn API Client initialized for:', creds.name, `(${creds.person_urn})`);
    console.log('Token expires on approx:', new Date(Date.now() + creds.expires_in * 1000).toLocaleDateString());
}
