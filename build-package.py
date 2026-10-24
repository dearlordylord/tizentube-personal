#!/usr/bin/env python3
"""Patch the frozen public WGT; never fetch dependencies or execute upstream code."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import difflib
import hashlib
import json
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
ORIGINAL_SHA256 = 'd5ebcf5b61e907912d5200b033f0d366717cb952c9f543a6332d36bef771b3b5'
UPSTREAM = 'https://github.com/reisxd/TizenTube/releases/download/v2.1.1/TizenTubeCobalt.wgt'
OLD_SCRIPT = 'https://cdn.jsdelivr.net/npm/@foxreis/tizentube/dist/userScript.js'
MANIFEST = json.loads((ROOT / 'service/personal-manifest.json').read_text())
SCRIPT_PATH = MANIFEST['path']
ORIGINAL_TAG = '<script src="' + OLD_SCRIPT + '?ver=${Date.now()}"></script>'
PERSONAL_TAG = '<script src="' + SCRIPT_PATH + '"></script>'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Upstream patch anchor changed: ' + old[:90])
    return text.replace(old, new, 1)


def patch_cobalt(text, compiled=False):
    declaration = 'var proxyPort = 8101;' if compiled else 'const proxyPort = 8101;'
    text = replace_once(text, declaration, declaration + "\nvar personalScript = require('../personal-script.js');")
    callback = 'var isTvPath =' if compiled else 'const isTvPath ='
    text = replace_once(text, callback,
                        "if (request.url === personalScript.path) { personalScript.serve(request, response); return; }\n        " + callback)
    text = replace_once(text, ORIGINAL_TAG, PERSONAL_TAG)
    text = replace_once(text, "proxyServer.listen(proxyPort, '0.0.0.0');", "proxyServer.listen(proxyPort, '127.0.0.2');")
    # A missing/unverified script must not silently serve unmodified YouTube.
    pattern = r'response\.writeHead\(\s*targetResponse\.statusCode,\s*headers\s*\);\s*response\.end\(body\);'
    replacement = '''personalScript.load().then(function () {
                response.writeHead(targetResponse.statusCode, headers);
                response.end(body);
            }, function () {
                response.writeHead(503, { 'Content-Type': 'text/plain', 'Cache-Control': 'no-store' });
                response.end('Verified personal TizenTube script unavailable');
            });'''
    text, count = re.subn(pattern, lambda _: replacement, text)
    if count != 1:
        raise ValueError('Cobalt response anchor changed')
    return text


def patch_index(text, compiled=False):
    declaration = 'var PORT = 8100;' if compiled else 'const PORT = 8100;'
    dependency = '../personal-script.js' if compiled else './personal-script.js'
    text = replace_once(text, declaration, declaration + "\nvar personalScript = require('" + dependency + "');")
    text = replace_once(text, "app.all('*',", "app.get(personalScript.path, personalScript.serve);\napp.get('/tizentube-personal/status', personalScript.status);\napp.all('*',")
    return replace_once(text, ORIGINAL_TAG, PERSONAL_TAG)


def patch_injector(text):
    return replace_once(text, OLD_SCRIPT, 'http://127.0.0.1:8100' + SCRIPT_PATH)


def patch_bundle_module(text, marker, transform):
    position = text.index(marker)
    start = text.rfind('\n/***/', 0, position)
    end = text.index('\n/***/', position)
    if start < 0 or end <= start:
        raise ValueError('Bundled module boundary changed')
    return text[:start] + transform(text[start:end], True) + text[end:]


def build(original):
    if hashlib.sha256(original).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('Not the frozen upstream release; refusing to patch')
    source = ROOT / '.cache/upstream-2.1.1.wgt'
    source.parent.mkdir(exist_ok=True)
    source.write_bytes(original)
    with ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    patches = []
    for name, transform in [
        ('service/index.js', patch_index),
        ('service/utils/cobaltProxyServer.js', patch_cobalt),
        ('service/utils/injector.js', patch_injector),
    ]:
        before = files[name].decode()
        after = transform(before)
        files[name] = after.encode()
        patches.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                          fromfile='upstream/' + name, tofile='personal/' + name))
    bundled = files['service/dist/index.js'].decode()
    bundled = patch_bundle_module(bundled, 'var PORT = 8100;', patch_index)
    bundled = patch_bundle_module(bundled, 'var proxyPort = 8101;', patch_cobalt)
    bundled = patch_injector(bundled)
    files['service/dist/index.js'] = bundled.encode()
    config = files['config.xml'].decode()
    config = replace_once(config, 'version="2.1.1"', 'version="2.1.2"')
    config = replace_once(config, '<name>TizenTube</name>', '<name>TizenTube Personal</name>')
    files['config.xml'] = config.encode()
    for name in ['personal-script.js', 'personal-manifest.json']:
        files['service/' + name] = (ROOT / 'service' / name).read_bytes()
    files['LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    files['PERSONAL-NOTICE.txt'] = (ROOT / 'NOTICE.txt').read_bytes()
    for name in ['author-signature.xml', 'signature1.xml']:
        files.pop(name, None)
    for name, data in files.items():
        if name.endswith(('.js', '.html')) and OLD_SCRIPT.encode() in data:
            raise ValueError('Unpinned external script remained: ' + name)
    out = ROOT / 'dist/TizenTube-Personal-2.1.2-unsigned.wgt'
    out.parent.mkdir(exist_ok=True)
    with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    (ROOT / 'patches').mkdir(exist_ok=True)
    (ROOT / 'patches/upstream.diff').write_text(''.join(patches))
    print('Built', out.name, 'SHA256', hashlib.sha256(out.read_bytes()).hexdigest())
    return out


if __name__ == '__main__':
    local = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / '.cache/upstream-2.1.1.wgt'
    data = local.read_bytes() if local.exists() else urllib.request.urlopen(UPSTREAM, timeout=30).read()
    build(data)
