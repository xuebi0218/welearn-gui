# -*- coding: utf-8 -*-
"""
SSO 登录流程诊断脚本。
运行此脚本，会将 SSO 页面关键信息保存到 sso_debug.txt。
请把 sso_debug.txt 的内容发给我，我根据真实页面结构修复密码登录。
"""
import requests
import re

session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

output = []

def log(msg):
    output.append(msg)
    print(msg)

log("=" * 60)
log("Welearn SSO 登录诊断")
log("=" * 60)

# Step 1: 主页
log("\n[Step 1] 访问主页...")
r = session.get('https://welearn.sflep.com/', timeout=15, allow_redirects=True)
log(f"  最终URL: {r.url}")
log(f"  状态码: {r.status_code}")
log(f"  Cookies数量: {len(session.cookies)}")

# Step 2: 预登录 — 不允许重定向
log("\n[Step 2] prelogin.aspx (allow_redirects=False)...")
r = session.get(
    'https://welearn.sflep.com/user/prelogin.aspx?loginret=http%3a%2f%2fwelearn.sflep.com%2fuser%2floginredirect.aspx',
    timeout=15, allow_redirects=False)
log(f"  状态码: {r.status_code}")
log(f"  Headers:")
for k, v in r.headers.items():
    log(f"    {k}: {v}")
log(f"  Body前500字符:\n{r.text[:500]}")

# Step 3: 预登录 — 允许重定向
log("\n[Step 3] prelogin.aspx (allow_redirects=True)...")
r = session.get(
    'https://welearn.sflep.com/user/prelogin.aspx?loginret=http%3a%2f%2fwelearn.sflep.com%2fuser%2floginredirect.aspx',
    timeout=15, allow_redirects=True)
log(f"  最终URL: {r.url}")
log(f"  状态码: {r.status_code}")
log(f"  重定向次数: {len(r.history)}")
for i, h in enumerate(r.history):
    log(f"    重定向{i+1}: {h.status_code} -> {h.headers.get('Location', 'N/A')}")

# Step 4: 从页面中找 SSO 登录表单
log("\n[Step 4] 解析登录表单...")
html = r.text

# 找所有 <form>
forms = re.findall(r'<form[^>]*>.*?</form>', html, re.IGNORECASE | re.DOTALL)
log(f"  找到 {len(forms)} 个 form")
for i, f in enumerate(forms):
    action_m = re.search(r'action\s*=\s*["\']([^"\']+)["\']', f, re.IGNORECASE)
    method_m = re.search(r'method\s*=\s*["\']([^"\']+)["\']', f, re.IGNORECASE)
    log(f"  Form {i+1}: action={action_m.group(1) if action_m else 'N/A'}, method={method_m.group(1) if method_m else 'GET'}")
    inputs = re.findall(r'<input[^>]*>', f, re.IGNORECASE)
    for inp in inputs:
        name_m = re.search(r'name\s*=\s*["\']([^"\']+)["\']', inp, re.IGNORECASE)
        type_m = re.search(r'type\s*=\s*["\']([^"\']+)["\']', inp, re.IGNORECASE)
        value_m = re.search(r'value\s*=\s*["\']([^"\']*)["\']', inp, re.IGNORECASE)
        log(f"    input: name={name_m.group(1) if name_m else '?'} type={type_m.group(1) if type_m else 'text'} value={value_m.group(1) if value_m else ''}")

# 找 JS 跳转
js_redirects = re.findall(r'(?:location\.href|window\.location)\s*=\s*["\']([^"\']+)["\']', html)
if js_redirects:
    log(f"\n  JS跳转目标: {js_redirects}")

# 找 SSO 相关 URL
sso_urls = re.findall(r'https?://[^"\'\s]*sso[^"\'\s]*', html, re.IGNORECASE)
if sso_urls:
    log(f"\n  SSO URL: {sso_urls}")

# Step 5: 尝试访问 SSO 登录页
log("\n[Step 5] 访问 SSO...")
if 'Location' in r.headers or r.history:
    sso_url = r.url if 'sso' in r.url.lower() else None
    if not sso_url:
        # 找 SSO URL
        sso_urls = re.findall(r'https?://sso\.[^"\'\s]+', html)
        sso_url = sso_urls[0] if sso_urls else None

    if sso_url:
        log(f"  SSO URL: {sso_url}")
        r2 = session.get(sso_url, timeout=15)
        log(f"  SSO页面标题: {re.search(r'<title>([^<]*)</title>', r2.text, re.IGNORECASE).group(1) if '<title>' in r2.text else 'N/A'}")
        # 找 SSO 页面的表单
        sso_forms = re.findall(r'<form[^>]*>.*?</form>', r2.text, re.IGNORECASE | re.DOTALL)
        log(f"  SSO页面表单数: {len(sso_forms)}")
        for i, f in enumerate(sso_forms):
            action_m = re.search(r'action\s*=\s*["\']([^"\']+)["\']', f, re.IGNORECASE)
            log(f"  SSO Form {i+1}: action={action_m.group(1) if action_m else 'N/A'}")
            inputs = re.findall(r'<input[^>]*>', f, re.IGNORECASE)
            for inp in inputs:
                name_m = re.search(r'name\s*=\s*["\']([^"\']+)["\']', inp, re.IGNORECASE)
                type_m = re.search(r'type\s*=\s*["\']([^"\']+)["\']', inp, re.IGNORECASE)
                log(f"    input: name={name_m.group(1) if name_m else '?'} type={type_m.group(1) if type_m else 'text'}")
    else:
        log("  未找到SSO URL")

# 保存
with open('sso_debug.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print("\n" + "=" * 60)
print("诊断完成！结果已保存到 sso_debug.txt")
print("请将此文件内容发给我，我根据真实页面修复密码登录。")
input("按回车键退出...")
