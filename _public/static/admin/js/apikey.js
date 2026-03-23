let adminKey = '';
let allKeys = [];
let editingKey = '';

const byId = (id) => document.getElementById(id);

function toggleCreateExpire(cb) {
  byId('create-expire').disabled = cb.checked;
  if (cb.checked) byId('create-expire').value = '';
}

function toggleEditExpire(cb) {
  byId('edit-expire').disabled = cb.checked;
  if (cb.checked) byId('edit-expire').value = '';
}

function openCreateModal() {
  byId('create-note').value = '';
  byId('create-expire').value = '';
  byId('create-ips').value = '';
  byId('create-never-expire').checked = true;
  byId('create-expire').disabled = true;
  byId('create-modal').classList.remove('hidden');
}

function closeCreateModal() {
  byId('create-modal').classList.add('hidden');
}

function openEditModal(key) {
  const info = allKeys.find(k => k.key === key);
  if (!info) return;
  editingKey = key;
  byId('edit-key').value = key;
  byId('edit-note').value = info.note || '';
  byId('edit-status').value = info.status || 'active';
  if (info.expire_time) {
    byId('edit-never-expire').checked = false;
    byId('edit-expire').disabled = false;
    byId('edit-expire').value = new Date(info.expire_time).toISOString().slice(0, 16);
  } else {
    byId('edit-never-expire').checked = true;
    byId('edit-expire').disabled = true;
    byId('edit-expire').value = '';
  }
  byId('edit-ips').value = (info.ip_whitelist || []).join('\n');
  byId('edit-modal').classList.remove('hidden');
}

function closeEditModal() {
  byId('edit-modal').classList.add('hidden');
}

async function request(url, options = {}) {
  const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${adminKey}`, ...(options.headers || {}) };
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) { window.location.href = '/admin/login'; return null; }
  return res;
}

async function loadStats() {
  const res = await request('/v1/admin/apikeys/stats');
  if (!res) return;
  const d = await res.json();
  if (d.success) {
    byId('stat-total').textContent = d.data.total ?? '-';
    byId('stat-active').textContent = d.data.active ?? '-';
    byId('stat-disabled').textContent = d.data.disabled ?? '-';
    byId('stat-expired').textContent = d.data.expired ?? '-';
  }
}

async function loadKeys() {
  const res = await request('/v1/admin/apikeys');
  if (!res) return;
  const d = await res.json();
  if (!d.success) { showToast('加载失败', 'error'); return; }
  allKeys = d.data;
  renderKeys();
  await loadStats();
}

const STATUS_STYLE = {
  active: 'bg-green-50 text-green-700 border-green-200',
  disabled: 'bg-orange-50 text-orange-700 border-orange-200',
  expired: 'bg-red-50 text-red-700 border-red-200',
};
const STATUS_TEXT = { active: '活跃', disabled: '禁用', expired: '过期' };

function fmtTime(ts) {
  if (!ts) return '-';
  return new Date(ts).toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' });
}

function maskKey(key) {
  return key.slice(0, 10) + '...' + key.slice(-6);
}

function renderKeys() {
  const tbody = byId('apikey-tbody');
  const empty = byId('apikey-empty');
  if (!allKeys.length) {
    tbody.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');
  tbody.innerHTML = allKeys.map(k => `
    <tr class="hover:bg-[var(--accents-1)] transition-colors">
      <td class="px-4 py-2.5 align-middle">
        <div class="flex items-center gap-2">
          <code class="text-xs font-mono">${maskKey(k.key)}</code>
          <button onclick="copyKey('${k.key}')" title="复制" class="text-[var(--accents-4)] hover:text-[var(--fg)] transition-colors">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          </button>
        </div>
      </td>
      <td class="px-4 py-2.5 align-middle text-xs text-[var(--accents-4)]">${k.note || '-'}</td>
      <td class="px-4 py-2.5 align-middle">
        <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium border ${STATUS_STYLE[k.status] || ''}">
          ${STATUS_TEXT[k.status] || k.status}
        </span>
      </td>
      <td class="px-4 py-2.5 align-middle text-xs">${k.expire_time ? fmtTime(k.expire_time) : '永不过期'}</td>
      <td class="px-4 py-2.5 align-middle text-xs">${k.ip_whitelist?.length ? k.ip_whitelist.join(', ') : '无限制'}</td>
      <td class="px-4 py-2.5 align-middle text-xs text-[var(--accents-4)]">${fmtTime(k.created_time)}</td>
      <td class="px-4 py-2.5 align-middle text-xs text-[var(--accents-4)]">${fmtTime(k.last_used_time)}</td>
      <td class="px-4 py-2.5 align-middle text-right">
        <div class="flex items-center justify-end gap-1">
          <button onclick="openEditModal('${k.key}')" title="编辑" class="inline-flex items-center justify-center h-7 w-7 rounded-md hover:bg-[var(--accents-2)] transition-colors">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
          </button>
          <button onclick="deleteKey('${k.key}')" title="删除" class="inline-flex items-center justify-center h-7 w-7 rounded-md hover:bg-red-50 hover:text-red-600 transition-colors">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      </td>
    </tr>
  `).join('');
}

function copyKey(key) {
  navigator.clipboard.writeText(key).then(() => showToast('已复制', 'success'));
}

async function submitCreate() {
  const note = byId('create-note').value.trim();
  const neverExpire = byId('create-never-expire').checked;
  const expireInput = byId('create-expire').value;
  const ipsText = byId('create-ips').value;
  const expire_time = (!neverExpire && expireInput) ? new Date(expireInput).getTime() : null;
  const ip_whitelist = ipsText.split('\n').map(s => s.trim()).filter(Boolean);
  const res = await request('/v1/admin/apikeys', {
    method: 'POST',
    body: JSON.stringify({ note, expire_time, ip_whitelist }),
  });
  if (!res) return;
  const d = await res.json();
  if (d.success) {
    showToast('创建成功', 'success');
    closeCreateModal();
    await loadKeys();
  } else {
    showToast(d.detail || '创建失败', 'error');
  }
}

async function submitEdit() {
  const note = byId('edit-note').value.trim();
  const status = byId('edit-status').value;
  const neverExpire = byId('edit-never-expire').checked;
  const expireInput = byId('edit-expire').value;
  const ipsText = byId('edit-ips').value;
  const expire_time = (!neverExpire && expireInput) ? new Date(expireInput).getTime() : null;
  const ip_whitelist = ipsText.split('\n').map(s => s.trim()).filter(Boolean);
  const res = await request('/v1/admin/apikeys', {
    method: 'PUT',
    body: JSON.stringify({ key: editingKey, note, status, expire_time, ip_whitelist }),
  });
  if (!res) return;
  const d = await res.json();
  if (d.success) {
    showToast('更新成功', 'success');
    closeEditModal();
    await loadKeys();
  } else {
    showToast(d.detail || '更新失败', 'error');
  }
}

async function deleteKey(key) {
  if (!confirm(`确定删除此 API Key？\n${key.slice(0, 20)}...`)) return;
  const res = await request('/v1/admin/apikeys', {
    method: 'DELETE',
    body: JSON.stringify({ key }),
  });
  if (!res) return;
  const d = await res.json();
  if (d.success) {
    showToast('删除成功', 'success');
    await loadKeys();
  } else {
    showToast(d.detail || '删除失败', 'error');
  }
}

async function init() {
  adminKey = await ensureAdminKey();
  if (!adminKey) return;
  await loadKeys();
}

document.addEventListener('DOMContentLoaded', init);
