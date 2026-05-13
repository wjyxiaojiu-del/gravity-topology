const http = require('http');
const https = require('https');
const crypto = require('crypto');

const PORT = 17993;
const DEFAULT_REDIRECT_URI = `http://localhost:${PORT}/callback`;
const DEFAULT_HOST = 'openapi.zhihu.com';

const stateStore = new Map();
const tokenStore = new Map();

function logCurl(method, path, headers, query, body) {
  const safeHeaders = { ...headers };
  if (safeHeaders['authorization']) safeHeaders['authorization'] = safeHeaders['authorization'].replace(/(Bearer\s+)\S+/, '$1***');
  const qs = Object.keys(query).length ? '?' + new URLSearchParams(query).toString() : '';
  const url = `http://localhost:${PORT}${path}${qs}`;
  const headerStr = Object.entries(safeHeaders).map(([k, v]) => `-H '${k}: ${v}'`).join(' \\\n  ');
  let bodyStr = '';
  if (body && Object.keys(body).length) {
    const safe = { ...body };
    if (safe.app_key) safe.app_key = '***';
    bodyStr = ` \\\n  -d '${JSON.stringify(safe)}'`;
  }
  console.log(`[CURL] curl -X ${method} '${url}' \\\n  ${headerStr}${bodyStr}`);
}

function parseBody(req) {
  return new Promise(resolve => {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => { try { resolve(JSON.parse(body)); } catch { resolve({}); } });
  });
}

function parseQuery(str) {
  return Object.fromEntries(new URLSearchParams(str));
}

function send(res, status, body, type = 'application/json') {
  res.writeHead(status, { 'Content-Type': type });
  res.end(typeof body === 'string' ? body : JSON.stringify(body));
}

function zhihuRequest(host, options, postData) {
  const url = `https://${host}${options.path}`;
  const headerStr = Object.entries(options.headers || {}).map(([k, v]) => `-H '${k}: ${v}'`).join(' \\\n  ');
  const bodyStr = postData ? ` \\\n  -d '${postData}'` : '';
  console.log(`[CURL] curl -X ${options.method} '${url}' \\\n  ${headerStr}${bodyStr}`);
  return new Promise((resolve, reject) => {
    const opts = { ...options, hostname: host };
    const req = https.request(opts, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        let parsed;
        try { parsed = JSON.parse(data); } catch { parsed = data; }
        console.log(`[RES] ${options.method} ${url}\n `, JSON.stringify(parsed).slice(0, 300));
        resolve(parsed);
      });
    });
    req.on('error', reject);
    if (postData) req.write(postData);
    req.end();
  });
}

function homePage() {
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>知乎 OAuth Demo</title>
<style>body{font-family:sans-serif;max-width:500px;margin:60px auto;padding:0 20px}
input{width:100%;padding:8px;margin:4px 0 12px;box-sizing:border-box;border:1px solid #ccc;border-radius:4px}
button{padding:10px 24px;background:#0084ff;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:15px}
.tip{color:#888;font-size:13px;margin-top:8px}</style></head>
<body>
<h2>知乎 OAuth 2.0 演示服务</h2>
<label>API Host</label>
<input id="host" placeholder="openapi.zhihu.com" value="openapi.zhihu.com">
<label>APP_ID</label>
<input id="app_id" placeholder="输入 APP_ID" value="303">
<label>APP_KEY</label>
<input id="app_key" type="password" placeholder="输入 APP_KEY" value="fff438e54654409392d2e7c4a3aff673">
<label>回调地址 (redirect_uri)</label>
<input id="redirect_uri" placeholder="${DEFAULT_REDIRECT_URI}" value="${DEFAULT_REDIRECT_URI}">
<button onclick="login()">使用知乎账号登录</button>
<p class="tip">点击后将跳转到真实的知乎授权页面</p>
<script>
document.getElementById('app_id').value = localStorage.getItem('app_id') || '303';
document.getElementById('host').value = localStorage.getItem('zhihu_host') || 'openapi.zhihu.com';
document.getElementById('redirect_uri').value = localStorage.getItem('redirect_uri') || '${DEFAULT_REDIRECT_URI}';
async function login() {
  const host = document.getElementById('host').value.trim() || 'openapi.zhihu.com';
  const app_id = document.getElementById('app_id').value.trim();
  const app_key = document.getElementById('app_key').value.trim();
  const redirect_uri = document.getElementById('redirect_uri').value.trim() || '${DEFAULT_REDIRECT_URI}';
  if (!app_id || !app_key) { alert('请填写 APP_ID 和 APP_KEY'); return; }
  localStorage.setItem('zhihu_host', host);
  localStorage.setItem('app_id', app_id);
  localStorage.setItem('app_key', app_key);
  localStorage.setItem('redirect_uri', redirect_uri);
  const r = await fetch('/api/auth/zhihu/url?app_id=' + encodeURIComponent(app_id) + '&host=' + encodeURIComponent(host) + '&redirect_uri=' + encodeURIComponent(redirect_uri));
  const {authorize_url, state} = await r.json();
  localStorage.setItem('oauth_state', state);
  window.location.href = authorize_url;
}
</script></body></html>`;
}

function profilePage(token) {
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>个人详情</title>
<style>
body{font-family:sans-serif;max-width:700px;margin:40px auto;padding:0 20px}
img{border-radius:50%;width:80px;height:80px}
table{width:100%;border-collapse:collapse;margin-top:12px}
td{padding:10px;border-bottom:1px solid #eee}td:first-child{color:#888;width:130px}
.section{margin-top:28px}
h3{border-bottom:2px solid #0084ff;padding-bottom:6px}
.user-card{display:flex;align-items:center;gap:16px;padding:16px;background:#f5f5f5;border-radius:8px}
.loading{color:#888;font-style:italic}
pre{background:#f5f5f5;padding:12px;border-radius:4px;overflow:auto;font-size:13px;margin:0}
.error{color:#c00}
</style></head>
<body>
<h2>授权成功 - 个人详情</h2>
<div id="user-card" class="loading">加载用户信息...</div>

<script>
const token = '${token}';

function renderUser(u) {
  return \`<div class="user-card">
    <img src="\${u.avatar_path||''}" onerror="this.style.display='none'">
    <div><h3 style="margin:0;border:none">\${u.fullname}</h3>
    <p style="margin:4px 0;color:#888">\${u.headline||''}</p></div>
  </div>
  <table>
    <tr><td>UID</td><td>\${u.uid}</td></tr>
    <tr><td>昵称</td><td>\${u.fullname}</td></tr>
    <tr><td>性别</td><td>\${u.gender||'-'}</td></tr>
    <tr><td>简介</td><td>\${u.headline||'-'}</td></tr>
    <tr><td>描述</td><td>\${u.description||'-'}</td></tr>
    <tr><td>邮箱</td><td>\${u.email||'-'}</td></tr>
    <tr><td>手机号</td><td>\${u.phone_no||'-'}</td></tr>
  </table>\`;
}

async function load() {
  const headers = { Authorization: 'Bearer ' + token };

  try {
    const r = await fetch('/api/user', { headers });
    const u = await r.json();
    document.getElementById('user-card').innerHTML = u.code === 401
      ? '<p class="error">' + u.data + '</p>' : renderUser(u);
  } catch(e) {
    document.getElementById('user-card').innerHTML = '<p class="error">加载失败: ' + e.message + '</p>';
  }
}

load();
</script></body></html>`;
}

const server = http.createServer(async (req, res) => {
  const parsed = new URL(req.url, `http://localhost:${PORT}`);
  const path = parsed.pathname;
  const query = parseQuery(parsed.search.slice(1));

  if (path === '/' && req.method === 'GET') {
    return send(res, 200, homePage(), 'text/html; charset=utf-8');
  }

  // 生成知乎授权 URL
  if (path === '/api/auth/zhihu/url' && req.method === 'GET') {
    const { app_id, host = DEFAULT_HOST, redirect_uri = DEFAULT_REDIRECT_URI } = query;
    if (!app_id) return send(res, 400, { error: 'Missing app_id' });
    const state = crypto.randomUUID();
    stateStore.set(state, { host, redirect_uri });
    const authorize_url = `https://${host}/authorize?` +
      `redirect_uri=${encodeURIComponent(redirect_uri)}` +
      `&app_id=${encodeURIComponent(app_id)}` +
      `&response_type=code` +
      `&state=${state}`;
    console.log(`[AUTH] 生成授权 URL: ${authorize_url}`);
    return send(res, 200, { authorize_url, state });
  }

  // 知乎回调页
  if (path === '/callback' && req.method === 'GET') {
    if (query.error) {
      return send(res, 200,
        `<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><h2>授权被拒绝</h2><p>${query.error}</p><a href="/">返回首页</a></body></html>`,
        'text/html; charset=utf-8');
    }
    return send(res, 200, `<!DOCTYPE html><html><head><meta charset="utf-8"><title>处理中</title></head>
<body><p>正在处理授权...</p>
<script>
(async () => {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code') || params.get('authorization_code');
  const state = params.get('state');
  const savedState = localStorage.getItem('oauth_state');
  if (state && savedState && state !== savedState) {
    document.body.innerHTML = '<h2>state 不匹配，可能存在 CSRF 攻击</h2><a href="/">返回</a>';
    return;
  }
  localStorage.removeItem('oauth_state');
  const app_id = localStorage.getItem('app_id') || '';
  const app_key = localStorage.getItem('app_key') || '';
  const host = localStorage.getItem('zhihu_host') || 'openapi.zhihu.com';
  const redirect_uri = localStorage.getItem('redirect_uri') || '${DEFAULT_REDIRECT_URI}';
  localStorage.removeItem('app_key');
  if (!code) {
    document.body.innerHTML = '<h2>未获取到授权码</h2><pre>' + location.search + '</pre><a href="/">返回</a>';
    return;
  }
  const r = await fetch('/api/auth/zhihu/callback', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ code, state, app_id, app_key, host, redirect_uri })
  });
  const data = await r.json();
  if (data.token) {
    window.location.href = '/profile?token=' + data.token;
  } else {
    document.body.innerHTML = '<h2>授权失败</h2><pre>' + JSON.stringify(data, null, 2) + '</pre><a href="/">返回</a>';
  }
})();
</script></body></html>`, 'text/html; charset=utf-8');
  }

  // 后端换 token
  if (path === '/api/auth/zhihu/callback' && req.method === 'POST') {
    const body = await parseBody(req);
    const { code, state, app_id, app_key, host = DEFAULT_HOST, redirect_uri } = body;
    logCurl('POST', path, req.headers, {}, body);

    if (state && stateStore.size > 0 && !stateStore.has(state)) {
      return send(res, 400, { error: 'Invalid state' });
    }
    const stateData = stateStore.get(state) || {};
    if (state) stateStore.delete(state);

    const effectiveHost = stateData.host || host || DEFAULT_HOST;
    const effectiveRedirectUri = redirect_uri || stateData.redirect_uri || DEFAULT_REDIRECT_URI;

    if (!app_id || !app_key) return send(res, 400, { error: 'Missing app_id or app_key' });
    if (!code) return send(res, 400, { error: 'Missing code' });

    const postData = new URLSearchParams({
      app_id, app_key,
      grant_type: 'authorization_code',
      redirect_uri: effectiveRedirectUri,
      code
    }).toString();

    let tokenData;
    try {
      tokenData = await zhihuRequest(effectiveHost, {
        path: '/access_token',
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Content-Length': Buffer.byteLength(postData)
        }
      }, postData);
    } catch (e) {
      return send(res, 500, { error: 'Token 请求失败', detail: e.message });
    }

    if (!tokenData.access_token) {
      return send(res, 400, { error: '获取 token 失败', detail: tokenData });
    }

    const localToken = crypto.randomBytes(16).toString('hex');
    tokenStore.set(localToken, { access_token: tokenData.access_token, host: effectiveHost });

    return send(res, 200, { token: localToken, expires_in: tokenData.expires_in });
  }

  // 个人详情页
  if (path === '/profile' && req.method === 'GET') {
    if (!tokenStore.has(query.token)) {
      return send(res, 200, `<h2>Token 无效或已过期</h2><a href="/">返回首页</a>`, 'text/html; charset=utf-8');
    }
    return send(res, 200, profilePage(query.token), 'text/html; charset=utf-8');
  }

  // 代理用户信息接口
  if (path === '/api/user' && req.method === 'GET') {
    const entry = tokenStore.get((req.headers['authorization'] || '').replace('Bearer ', ''));
    if (!entry) return send(res, 200, { code: 401, data: 'Access token is not valid' });
    try {
      const data = await zhihuRequest(entry.host, {
        path: '/user', method: 'GET',
        headers: { 'Authorization': `Bearer ${entry.access_token}` }
      });
      return send(res, 200, data);
    } catch (e) {
      return send(res, 500, { error: e.message });
    }
  }

  send(res, 404, { error: 'Not found' });
});

server.listen(PORT, () => {
  console.log(`OAuth 演示服务已启动: http://localhost:${PORT}`);
});
