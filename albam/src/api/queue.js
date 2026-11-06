// 보내지 못한 기록을 쌓아 두는 곳(IndexedDB). 앱을 껐다 켜도 남는다.
// 들어간 순서(seq)대로 다시 보낸다. 같은 기록의 '추가'가 '취소'보다 먼저 가야 하기 때문.

/**
 * @typedef {Object} QueueItem
 * @property {number} [seq]                자동 번호
 * @property {'add'|'cancel'} op
 * @property {string} id                   기록 id
 * @property {Object} [payload]            op='add' 일 때 care_add_event 에 보낼 값
 * @property {number} created
 */

const DB_NAME = 'albam';
const STORE = 'queue';

function open() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'seq', autoIncrement: true });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function run(mode, action) {
  const db = await open();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const req = action(tx.objectStore(STORE));
      tx.oncomplete = () => resolve(req.result);
      tx.onerror = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

export const queue = {
  /** @returns {Promise<QueueItem[]>} 들어간 순서대로 */
  all: () => run('readonly', (s) => s.getAll()).catch(() => []),
  /** @param {QueueItem} item */
  push: (item) => run('readwrite', (s) => s.add(item)),
  remove: (seq) => run('readwrite', (s) => s.delete(seq)),
};
