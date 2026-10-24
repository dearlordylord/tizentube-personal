'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { EventEmitter } = require('node:events');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'service/personal-manifest.json')));
const source = fs.readFileSync(path.join(root, 'service/personal-script.js'), 'utf8');
const script = fs.readFileSync(path.join(root, 'cdn/userScript-1.15.2-7a092351e0e3.js'));

function harness(options = {}) {
  const calls = [];
  const transport = { request(opts, cb) {
    calls.push(opts);
    const req = new EventEmitter();
    req.abort = () => {};
    req.end = () => {
      if (options.timeout) return;
      process.nextTick(() => {
        if (options.error) { req.emit('error', new Error('offline')); return; }
        const response = new EventEmitter();
        response.statusCode = options.status || 200;
        response.resume = () => {};
        response.destroy = () => {};
        cb(response);
        response.emit('data', options.body || script);
        response.emit('end');
      });
    };
    return req;
  } };
  const context = { module: { exports: {} }, Buffer, Promise, process: { version: options.version || 'v20.0.0' },
    setTimeout: options.timeout ? fn => { queueMicrotask(fn); return 1; } : setTimeout,
    clearTimeout: options.timeout ? () => {} : clearTimeout,
    require(name) {
      if (name === 'https' || name === './utils/https.js') return transport;
      if (name === './personal-manifest.json') return options.manifest || manifest;
      return require(name);
    }
  };
  vm.runInNewContext(source, context);
  return { loader: context.module.exports, calls, options };
}

(async () => {
  const good = harness();
  const [a,b] = await Promise.all([good.loader.load(),good.loader.load()]);
  assert.equal(a,script.toString()); assert.equal(a,b); assert.equal(good.calls.length,1);
  await good.loader.load(); assert.equal(good.calls.length,1,'cache only verified content');
  assert.equal(good.calls[0].hostname,'dearlordylord.github.io');
  assert.equal(good.calls[0].rejectUnauthorized,true);
  assert.equal(good.calls[0].headers['Accept-Encoding'],'identity');
  const oldNode = harness({ version:'v12.0.0' });
  assert.equal(await oldNode.loader.load(),script.toString(),'old TV HTTPS implementation uses the same verification');
  const tampered = harness({ body:Buffer.from('malicious replacement') });
  await assert.rejects(tampered.loader.load(),/hash mismatch/);
  tampered.options.body = script;
  assert.equal(await tampered.loader.load(),script.toString(),'a failed download can retry safely');
  await assert.rejects(harness({ status:302 }).loader.load(),/HTTP status/);
  await assert.rejects(harness({ status:404 }).loader.load(),/HTTP status/);
  await assert.rejects(harness({ body:Buffer.alloc(2*1024*1024+1) }).loader.load(),/too large/);
  await assert.rejects(harness({ error:true }).loader.load(),/offline/);
  await assert.rejects(harness({ timeout:true }).loader.load(),/timed out/);
  assert.throws(()=>harness({ manifest:{...manifest,url:'https://cdn.jsdelivr.net/untrusted.js'} }),/Invalid personal/);
  const failed = harness({ body:Buffer.from('bad') });
  const response = await new Promise(resolve => {
    const res = { writeHead(code,headers) { this.code=code; this.headers=headers; }, end(body) { resolve({code:this.code,body}); } };
    failed.loader.serve({},res);
  });
  assert.equal(response.code,503); assert.equal(response.body.includes('bad'),false);
  console.log('Verified loader: exact CDN host, SHA-256, cache, redirect refusal, size/timeout limits, failure response, old-TV HTTPS.');
})().catch(error=>{ console.error(error);process.exitCode=1; });
