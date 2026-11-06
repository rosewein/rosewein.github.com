// DOM 도움 함수

/** @returns {HTMLElement} */
export const $ = (selector, root = document) => root.querySelector(selector);
/** @returns {HTMLElement[]} */
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

/** 보이기/숨기기 (.hidden) */
export const setHidden = (el, hidden) => el.classList.toggle('hidden', hidden);

/**
 * 요소 만들기. el('button', { className: 'px', onClick }, '저장')
 * @param {string} tag
 * @param {Object} [props]  onXxx 는 이벤트, 나머지는 속성
 * @param {...(Node|string)} children
 */
export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'style' && typeof value === 'object') Object.assign(node.style, value);
    else node[key] = value;
  }
  node.append(...children);
  return node;
}
