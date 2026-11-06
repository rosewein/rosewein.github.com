// 서비스 워커 캐시 목록이 실제 파일과 맞는지. 파일을 더하고 sw.js 에 안 넣는 실수를 막는다.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const sw = readFileSync(join(root, 'sw.js'), 'utf8');
const listed = [...sw.matchAll(/'\.\/([^']*)'/g)].map((m) => m[1]).filter(Boolean);

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? walk(p) : [relative(root, p)];
  });
}

test('sw.js 의 파일이 모두 있다', () => {
  for (const f of listed) assert.ok(existsSync(join(root, f)), `없는 파일: ${f}`);
});

test('src·styles 의 파일이 모두 sw.js 에 있다', () => {
  const needed = [...walk(join(root, 'src')), ...walk(join(root, 'styles'))];
  for (const f of needed) assert.ok(listed.includes(f), `sw.js FILES 에 빠짐: ${f}`);
});
