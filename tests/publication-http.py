"""Exercise publisher authentication and decision POSTs on a disposable PHP server."""
import http.cookiejar
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def request(opener, url, data=None):
    try:
        with opener.open(url, data=urllib.parse.urlencode(data).encode() if data is not None else None, timeout=10) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()

for configured, port in [(False, 8090), (True, 8091)]:
    env = dict(os.environ, NEWSROOM_EDITORIAL_USER='publisher_test' if configured else '', NEWSROOM_EDITORIAL_PASSWORD='local_test_password' if configured else '')
    process = subprocess.Popen(['php', '-S', '127.0.0.1:' + str(port), '-t', str(ROOT / 'web/public')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    url = 'http://127.0.0.1:' + str(port) + '/editorial-reviews.php?id=900001'
    try:
        for _ in range(50):
            try:
                status, page = request(opener, url)
                break
            except urllib.error.URLError:
                time.sleep(0.1)
        else:
            raise AssertionError('PHP server did not start')
        assert status == (401 if configured else 503), (status, page[:1000])
        if not configured:
            continue
        request(opener, url, {'auth_action': 'login', 'editorial_user': 'publisher_test', 'editorial_password': 'local_test_password'})
        status, page = request(opener, url)
        assert status == 200 and 'Publisher review' in page, (status, page[:1000])
        fields = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', page))
        assert {'csrf', 'story_id', 'revision_hash', 'review_version'} <= set(fields), page[:2000]
        status, _ = request(opener, url, dict(fields, csrf='', decision='approve', reason='invalid CSRF'))
        assert status == 403, status
        status, page = request(opener, url, dict(fields, decision='hold', reason='HTTP integration hold'))
        assert status == 200 and 'decision has been saved' in page, (status, page[:1200])
        # The content is unchanged, but another decision has advanced the version.
        status, page = request(opener, url, dict(fields, decision='approve', reason='stale old browser tab'))
        assert status == 409 and 'newer publisher decision' in page, (status, page[:1200])
        status, page = request(opener, url)
        fields = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', page))
        status, page = request(opener, url, dict(fields, decision='approve', reason='Reviewed current version'))
        assert status == 200 and 'decision has been saved' in page, (status, page[:1200])
    finally:
        process.terminate()
        process.wait(timeout=10)
print('Publisher HTTP checks passed: fail-closed access, authentication, CSRF, decisions and stale-tab rejection.')
