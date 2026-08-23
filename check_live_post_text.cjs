const { apiRequest, getCredentials } = require('./linkedin_api_client.cjs');
const https = require('https');
const fs = require('fs');
const path = require('path');

const credPath = path.resolve(__dirname, 'linkedin_api_credentials.json');
const creds = JSON.parse(fs.readFileSync(credPath, 'utf8'));

const options = {
    hostname: 'api.linkedin.com',
    path: '/rest/posts/urn%3Ali%3Ashare%3A7497285323979132928',
    method: 'GET',
    headers: {
        'Authorization': `Bearer ${creds.access_token}`,
        'LinkedIn-Version': '202601',
        'X-Restli-Protocol-Version': '2.0.0'
    }
};

const req = https.request(options, (res) => {
    let raw = '';
    res.on('data', c => raw += c);
    res.on('end', () => {
        console.log('HTTP Status:', res.statusCode);
        try {
            const data = JSON.parse(raw);
            console.log('COMMENTARY STORED ON LINKEDIN:\n', data.commentary);
            console.log('\nLength of commentary:', data.commentary ? data.commentary.length : 0);
        } catch (e) {
            console.log(raw);
        }
    });
});
req.end();
