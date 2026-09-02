import { BlockList, isIP } from 'node:net';
import { PROFILE, hash, requireSafe } from './profile.mjs';

const denied = new BlockList();
for (const [base, prefix] of [
  ['0.0.0.0', 8], ['10.0.0.0', 8], ['100.64.0.0', 10], ['127.0.0.0', 8],
  ['169.254.0.0', 16], ['172.16.0.0', 12], ['192.0.0.0', 24], ['192.0.2.0', 24],
  ['192.88.99.0', 24], ['192.168.0.0', 16], ['198.18.0.0', 15],
  ['198.51.100.0', 24], ['203.0.113.0', 24], ['224.0.0.0', 4], ['240.0.0.0', 4],
]) denied.addSubnet(base, prefix, 'ipv4');
const publicV6 = new BlockList();
publicV6.addSubnet('2000::', 3, 'ipv6');
for (const [base, prefix] of [['2001::', 23], ['2001:db8::', 32], ['2002::', 16], ['3fff::', 20]]) {
  denied.addSubnet(base, prefix, 'ipv6');
}

export function admitUrl(raw) {
  requireSafe(typeof raw === 'string' && raw.length <= PROFILE.limits.url, 'url_length_denied');
  requireSafe(!/[\s\\\u0000-\u001f\u007f]/u.test(raw), 'ambiguous_url_denied');
  let url;
  try { url = new URL(raw); } catch { requireSafe(false, 'invalid_url'); }
  requireSafe(PROFILE.schemes.includes(url.protocol), 'scheme_denied');
  const authority = raw.match(/^https?:\/\/([^/?#]+)/i)?.[1];
  requireSafe(authority && !/[%@]/.test(authority), 'ambiguous_authority_denied');
  requireSafe(!url.username && !url.password, 'credentials_denied');
  requireSafe(!url.port || PROFILE.ports.includes(Number(url.port)), 'port_denied');
  const host = url.hostname;
  requireSafe(!isIP(host) && !host.startsWith('['), 'ip_literal_denied');
  requireSafe(host.includes('.') && !host.endsWith('.') && host.length <= 253 &&
    host.split('.').every((label) => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)), 'host_denied');
  requireSafe(!/(^|\.)(localhost|local|internal|lan|home|test|invalid|onion)$/.test(host) &&
    !/(^|[.-])(metadata|instance-data)([.-]|$)/.test(host), 'private_host_denied');
  const queryKeys = [...new Set(url.searchParams.keys())].sort();
  // A deliberately narrow fixture-only query policy rejects unknown keys as
  // suspected credentials rather than attempting universal secret detection.
  for (const [key, value] of url.searchParams) {
    requireSafe(['lang', 'page', 'view'].includes(key) && /^[a-zA-Z0-9_-]{1,16}$/.test(value), 'query_secret_or_unknown_key_denied');
  }
  requireSafe(!/eyJ[A-Za-z0-9_-]+\.|(?:bearer|token|secret|signature|password)[=:]/i.test(decodeURI(url.pathname)), 'path_secret_denied');
  url.hash = '';
  const display = new URL(url);
  for (const key of queryKeys) display.searchParams.set(key, 'REDACTED');
  return { exact: url.href, display: display.href, digest: hash(url.href), queryKeys, host };
}

export function admitAddresses(answers) {
  requireSafe(Array.isArray(answers) && answers.length > 0 && answers.length <= PROFILE.limits.dnsAnswers, 'dns_answers_denied');
  return answers.map((address) => {
    const version = isIP(address);
    requireSafe(version && !address.includes('%'), 'address_denied');
    const family = version === 4 ? 'ipv4' : 'ipv6';
    requireSafe(!denied.check(address, family) && (version === 4 || publicV6.check(address, family)), 'nonpublic_address_denied');
    return version === 4 ? address : new URL(`http://[${address}]/`).hostname.slice(1, -1);
  });
}

export function verifyPeer(admitted, peer) {
  let canonical;
  try { [canonical] = admitAddresses([peer]); } catch { requireSafe(false, 'peer_denied'); }
  requireSafe(admitted.includes(canonical), 'peer_not_admitted');
  return canonical;
}
