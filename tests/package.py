from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'service/personal-manifest.json').read_text())
with ZipFile(root / 'dist/TizenTube-Personal-2.1.2-unsigned.wgt') as package:
    files = {name: package.read(name) for name in package.namelist()}
assert not {'author-signature.xml', 'signature1.xml'} & files.keys()
assert hashlib.sha256((root / 'cdn/userScript-1.15.2-7a092351e0e3.js').read_bytes()).hexdigest() == manifest['sha256']
for name, content in files.items():
    if name.endswith(('.js', '.html')):
        assert b'https://cdn.jsdelivr.net/npm/@foxreis/tizentube/dist/userScript.js' not in content, name
        with tempfile.NamedTemporaryFile(suffix='.js') as temp:
            if name.endswith('.js'):
                temp.write(content); temp.flush()
                subprocess.run(['node', '--check', temp.name], check=True, capture_output=True)
for name in ['service/utils/cobaltProxyServer.js','service/dist/index.js']:
    code = files[name].decode()
    assert "proxyServer.listen(proxyPort, '127.0.0.2');" in code
    assert "proxyServer.listen(proxyPort, '0.0.0.0');" not in code
    assert 'personalScript.serve(request, response)' in code
    assert 'personalScript.load().then(function ()' in code
for name in ['service/index.js','service/dist/index.js']:
    assert 'app.get(personalScript.path, personalScript.serve)' in files[name].decode()
for name in ['service/utils/injector.js','service/dist/index.js']:
    assert ('http://127.0.0.1:8100' + manifest['path']) in files[name].decode()
config = ET.fromstring(files['config.xml'])
assert config.attrib['version'] == '2.1.2'
assert 'http://127.0.0.2:8101' in files['config.xml'].decode()
assert files['service/personal-script.js'] == (root / 'service/personal-script.js').read_bytes()
print('Package checks: all three loading paths use verified bytes, loopback bind matches Cobalt, no external TizenTube loader, JavaScript parses, signing data excluded.')
