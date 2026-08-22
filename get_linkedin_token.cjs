const http = require('http');
const https = require('https');
const url = require('url');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

const CLIENT_ID = process.env.LINKEDIN_CLIENT_ID || '';
const CLIENT_SECRET = process.env.LINKEDIN_CLIENT_SECRET || '';
const REDIRECT_URI = 'http://localhost:3000/callback';
const SCOPES = ['openid', 'profile', 'email', 'w_member_social'].join('%20');
const STATE = 'antigravity_' + Math.random().toString(36).substring(7);

const authUrl = `https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=${CLIENT_ID}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&state=${STATE}&scope=${SCOPES}`;

console.log('='.repeat(60));
console.log('LINKEDIN OAUTH 2.0 AUTHORIZATION');
console.log('='.repeat(60));
console.log('\nOpening LinkedIn authorization page in your default browser...');
console.log('\nIf it does not open automatically, copy and open this URL:');
console.log(authUrl);
console.log('\n' + '='.repeat(60));

const server = http.createServer(async (req, res) => {
    const parsedUrl = url.parse(req.url, true);
    if (parsedUrl.pathname === '/callback') {
        const { code, state, error, error_description } = parsedUrl.query;

        if (error) {
            console.error(`\n[ERROR] LinkedIn Authorization Failed: ${error} - ${error_description}`);
            res.writeHead(400, { 'Content-Type': 'text/html; charset=utf-8' });
            res.end(`<h2>Authorization Failed</h2><p>${error_description}</p>`);
            server.close();
            process.exit(1);
        }

        if (!code) {
            res.writeHead(400, { 'Content-Type': 'text/html; charset=utf-8' });
            res.end(`<h2>Missing Code</h2>`);
            return;
        }

        console.log('\n[✓] Received authorization code from LinkedIn. Exchanging for Access Token...');

        try {
            const tokenData = await exchangeCodeForToken(code);
            const accessToken = tokenData.access_token;
            const expiresIn = tokenData.expires_in;

            console.log(`[✓] Access Token received! (Expires in: ${(expiresIn / 86400).toFixed(0)} days)`);
            console.log('[*] Fetching LinkedIn Profile URN...');

            const profile = await fetchUserProfile(accessToken);
            const personUrn = `urn:li:person:${profile.sub}`;

            console.log(`[✓] Connected Profile: ${profile.name} (URN: ${personUrn})`);

            // Save to credentials files
            const credentials = {
                client_id: CLIENT_ID,
                client_secret: CLIENT_SECRET,
                access_token: accessToken,
                expires_in: expiresIn,
                person_urn: personUrn,
                name: profile.name,
                email: profile.email,
                obtained_at: new Date().toISOString()
            };

            fs.writeFileSync(
                path.resolve(__dirname, 'linkedin_api_credentials.json'),
                JSON.stringify(credentials, null, 2)
            );

            // Update .env
            let envContent = '';
            const envPath = path.resolve(__dirname, '.env');
            if (fs.existsSync(envPath)) {
                envContent = fs.readFileSync(envPath, 'utf8');
            }
            
            const updates = {
                'LINKEDIN_CLIENT_ID': CLIENT_ID,
                'LINKEDIN_CLIENT_SECRET': CLIENT_SECRET,
                'LINKEDIN_ACCESS_TOKEN': accessToken,
                'LINKEDIN_PERSON_URN': personUrn
            };

            for (const [k, v] of Object.entries(updates)) {
                const regex = new RegExp(`^${k}=.*$`, 'm');
                if (regex.test(envContent)) {
                    envContent = envContent.replace(regex, `${k}="${v}"`);
                } else {
                    envContent += `\n${k}="${v}"`;
                }
            }
            fs.writeFileSync(envPath, envContent.trim() + '\n');

            console.log('[✓] Successfully saved credentials to .env and linkedin_api_credentials.json!');

            res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
            res.end(`
                <div style="font-family: -apple-system, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #10B981; font-size: 32px;">✓ LinkedIn API Connected Successfully!</h1>
                    <p style="font-size: 18px; color: #334155;">Authenticated as: <strong>${profile.name}</strong> (${profile.email})</p>
                    <p style="color: #64748B;">You can now close this tab and return to Antigravity.</p>
                </div>
            `);

            setTimeout(() => {
                server.close();
                console.log('\n[✓] Setup complete. Ready for direct API posting!');
                process.exit(0);
            }, 2000);

        } catch (err) {
            console.error('\n[ERROR]', err);
            res.writeHead(500, { 'Content-Type': 'text/html; charset=utf-8' });
            res.end(`<h2>Error exchanging token</h2><p>${err.message}</p>`);
            server.close();
            process.exit(1);
        }
    }
});

function exchangeCodeForToken(code) {
    return new Promise((resolve, reject) => {
        const postData = new URLSearchParams({
            grant_type: 'authorization_code',
            code: code,
            redirect_uri: REDIRECT_URI,
            client_id: CLIENT_ID,
            client_secret: CLIENT_SECRET
        }).toString();

        const req = https.request('https://www.linkedin.com/oauth/v2/accessToken', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Content-Length': Buffer.byteLength(postData)
            }
        }, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const json = JSON.parse(data);
                    if (res.statusCode >= 200 && res.statusCode < 300) {
                        resolve(json);
                    } else {
                        reject(new Error(json.error_description || json.error || data));
                    }
                } catch (e) {
                    reject(new Error(data));
                }
            });
        });

        req.on('error', reject);
        req.write(postData);
        req.end();
    });
}

function fetchUserProfile(accessToken) {
    return new Promise((resolve, reject) => {
        const req = https.request('https://api.linkedin.com/v2/userinfo', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        }, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    const json = JSON.parse(data);
                    if (res.statusCode >= 200 && res.statusCode < 300) {
                        resolve(json);
                    } else {
                        reject(new Error(json.message || data));
                    }
                } catch (e) {
                    reject(new Error(data));
                }
            });
        });

        req.on('error', reject);
        req.end();
    });
}

server.listen(3000, () => {
    console.log('[*] Local OAuth listener started on http://localhost:3000/callback');
    exec(`open "${authUrl}"`);
});
