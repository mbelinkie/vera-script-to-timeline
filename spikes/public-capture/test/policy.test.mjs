import assert from 'node:assert/strict';
import test from 'node:test';
import { admitUrl, admitAddresses, verifyPeer } from '../policy.mjs';

test('reject unsafe or ambiguous top-level URLs before resolution/navigation', () => {
  for (const url of [
    'file:///etc/passwd', 'data:text/html,hi', 'javascript:alert(1)',
    'ftp://public.example.org/', 'gopher://public.example.org/',
    'https://localhost/', 'https://foo.local/', 'https://metadata.google.internal/',
    'http://127.0.0.1/', 'http://2130706433/', 'http://0x7f000001/',
    'http://[::1]/', 'http://[::ffff:127.0.0.1]/', 'http://127.1/',
    'https://user:pass@public.example.org/', 'https://public.example.org:8443/',
    'https://public.example.org\\@localhost/', 'https://%65xample.org/',
    ' https://public.example.org/', 'https://public.example.org./',
    'https://public.example.org/?token=SECRET',
    'https://public.example.org/?X-Amz-Signature=SECRET',
    'https://public.example.org/?q=eyJhbGciOiJIUzI1NiJ9.abc.def',
  ]) assert.throws(() => admitUrl(url), { name: 'CaptureDenied' }, url);
});

test('benign query values remain restricted and fragments are not identity', () => {
  const admitted = admitUrl('https://capture.example.org/story?lang=en#section');
  assert.equal(admitted.exact, 'https://capture.example.org/story?lang=en');
  assert.equal(admitted.display, 'https://capture.example.org/story?lang=REDACTED');
  assert.deepEqual(admitted.queryKeys, ['lang']);
});

test('all DNS answers must be public; actual peer must belong to admitted set', () => {
  for (const address of [
    '0.0.0.0', '10.1.2.3', '100.64.0.1', '127.0.0.1', '169.254.169.254',
    '172.16.0.1', '192.0.0.9', '192.0.2.1', '192.168.1.2', '198.18.0.1',
    '198.51.100.1', '203.0.113.1', '224.0.0.1', '240.0.0.1', '255.255.255.255',
    '::', '::1', 'fc00::1', 'fe80::1', 'ff02::1', '::ffff:8.8.8.8',
    '64:ff9b::808:808', '2001::1', '2001:db8::1', '2002:808:808::1', '3fff::1',
  ]) assert.throws(() => admitAddresses(['93.184.216.34', address]), { name: 'CaptureDenied' }, address);
  const set = admitAddresses(['93.184.216.34', '2606:4700:4700::1111']);
  assert.equal(verifyPeer(set, '93.184.216.34'), '93.184.216.34');
  assert.throws(() => verifyPeer(set, '127.0.0.1'), /peer/);
  assert.throws(() => verifyPeer(set, '8.8.8.8'), /peer/);
  assert.throws(() => admitAddresses([]));
});
