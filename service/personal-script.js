/* Personal TizenTube loader, 2026-10-24. GPL-3.0-only. */
'use strict';
var crypto = require('crypto');
var url = require('url');
var manifest = require('./personal-manifest.json');
var https = parseInt(process.version.slice(1), 10) < 13 ? require('./utils/https.js') : require('https');
var cached = null;
var pending = null;
var maxBytes = 2 * 1024 * 1024;
var target = url.parse(manifest.url);
if (target.protocol !== 'https:' || target.hostname !== 'dearlordylord.github.io' || target.auth || target.port ||
    target.pathname.indexOf('/tizentube-personal/cdn/') !== 0 || !/^[a-f0-9]{64}$/.test(manifest.sha256)) {
    throw new Error('Invalid personal script manifest');
}

function load() {
    if (cached !== null) return Promise.resolve(cached);
    if (pending) return pending;
    pending = new Promise(function (resolve, reject) {
        var request;
        var timer;
        var settled = false;
        function fail(error) {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            reject(error);
            if (request && request.abort) request.abort();
        }
        timer = setTimeout(function () { fail(new Error('Personal script request timed out')); }, 15000);
        try {
            request = https.request({
                hostname: target.hostname, port: 443, path: target.path, method: 'GET',
                headers: { 'Accept-Encoding': 'identity', 'User-Agent': 'TizenTube-Personal' },
                rejectUnauthorized: true
            }, function (response) {
                if (response.statusCode !== 200) { fail(new Error('Personal script HTTP status')); response.resume(); return; }
                var chunks = [];
                var length = 0;
                response.on('error', fail);
                response.on('data', function (chunk) {
                    if (settled) return;
                    length += chunk.length;
                    if (length > maxBytes) { fail(new Error('Personal script too large')); response.destroy(); return; }
                    chunks.push(chunk);
                });
                response.on('end', function () {
                    if (settled) return;
                    var body = Buffer.concat(chunks);
                    if (crypto.createHash('sha256').update(body).digest('hex') !== manifest.sha256) {
                        fail(new Error('Personal script hash mismatch')); return;
                    }
                    settled = true;
                    clearTimeout(timer);
                    cached = body.toString('utf8');
                    resolve(cached);
                });
            });
            request.on('error', fail);
            request.end();
        } catch (error) { fail(error); }
    });
    pending = pending.catch(function (error) { pending = null; throw error; });
    return pending;
}

function serve(request, response) {
    load().then(function (script) {
        response.writeHead(200, {
            'Content-Type': 'application/javascript; charset=utf-8',
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'
        });
        response.end(script);
    }, function () {
        response.writeHead(503, { 'Content-Type': 'text/plain', 'Cache-Control': 'no-store' });
        response.end('Verified personal TizenTube script unavailable');
    });
}

function status(request, response) {
    response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    response.end(JSON.stringify({ version: manifest.version, loaded: cached !== null, sha256: manifest.sha256, source: manifest.url }));
}

module.exports = { path: manifest.path, load: load, serve: serve, status: status };
