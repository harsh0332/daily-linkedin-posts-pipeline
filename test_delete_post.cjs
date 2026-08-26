const https = require('https');
const fs = require('fs');
const path = require('path');

const credPath = path.resolve(__dirname, 'linkedin_api_credentials.json');
const creds = JSON.parse(fs.readFileSync(credPath, 'utf8'));

const postUrn = 'urn:li:ugcPost:7498238509124644865';
const encodedUrn = encodeURIComponent(postUrn);

const options = {
    hostname: 'api.linkedin.com',
    path: `/rest/posts/${encodedUrn}`,
    method: 'DELETE',
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
        console.log('Response:', raw);
    });
});
req.end();
