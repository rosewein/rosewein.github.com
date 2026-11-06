// 로그인 창. Supabase 주소·키가 없으면 그 칸도 함께 보여 준다(이 기기에만 저장).

import { $, setHidden } from './dom.js';
import { closeSheets, openSheet } from './sheets.js';
import { saveLocalConnection } from '../config.js';

/** @param {import('../main.js').AppContext} ctx */
export function setupLogin(ctx) {
  const { sfx } = ctx;

  function show(message = '') {
    if (ctx.api.demo) return;
    setHidden($('#setupFields'), ctx.api.isConfigured());
    $('#cfgUrl').value = ctx.cfg.supabaseUrl || '';
    $('#cfgKey').value = ctx.cfg.supabaseAnonKey || '';
    $('#email').value = ctx.api.email() || $('#email').value;
    $('#loginMsg').textContent = message;
    openSheet('loginSheet');
  }

  $('#loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    $('#loginBtn').disabled = true;
    $('#loginMsg').textContent = '';
    try {
      if (!$('#setupFields').classList.contains('hidden')) {
        saveLocalConnection($('#cfgUrl').value.trim(), $('#cfgKey').value.trim());
        ctx.reconnect();
      }
      await ctx.api.signIn($('#email').value.trim(), $('#password').value);
      $('#password').value = '';
      closeSheets();
      sfx.save();
      await ctx.refresh();
    } catch (err) {
      sfx.error();
      $('#loginMsg').textContent = /invalid/i.test(err.message) ? '이메일이나 비밀번호가 맞지 않아요' : `로그인 실패: ${err.message}`;
    } finally {
      $('#loginBtn').disabled = false;
    }
  });

  return { show };
}
