# -*- coding: utf-8 -*-
"""最终诊断：捕获完整验证错误 + 尝试 API 端点"""
import requests, re, sys, json
from urllib.parse import urlparse, parse_qs, unquote

output = []
def log(msg):
    output.append(str(msg))
    print(str(msg))
    sys.stdout.flush()

def main():
    try:
        session = requests.Session()
        session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        log("=" * 60)

        USERNAME = input("账号: ").strip()
        PASSWORD = input("密码: ").strip()

        # Step 1: 跟随重定向
        r = session.get(
            'https://welearn.sflep.com/user/prelogin.aspx?loginret=http%3a%2f%2fwelearn.sflep.com%2fuser%2floginredirect.aspx',
            timeout=30, allow_redirects=True)

        return_url = None
        login_url = None
        for h in r.history:
            loc = h.headers.get('Location', '')
            if 'ReturnUrl=' in loc:
                p = parse_qs(urlparse(loc).query)
                return_url = p.get('ReturnUrl', [None])[0]
            if '/Account/Login' in loc:
                login_url = f'https://sso.sflep.com{loc}' if not loc.startswith('http') else loc

        if not return_url:
            log("ERROR: 无ReturnUrl")
            return

        log(f"ReturnUrl: {return_url}")

        # GET login page to get cookies
        session.get(login_url, timeout=30)

        # Try different POST URLs
        base = 'https://sso.sflep.com/idsvr'

        tests = [
            # (URL, data_dict, extra_headers)
            (f'{base}/Account/Login', {'ReturnUrl': return_url, 'Username': USERNAME, 'Password': PASSWORD, 'RememberMe': 'false'}),
            (f'{base}/Account/Login', {'ReturnUrl': return_url, 'username': USERNAME, 'password': PASSWORD}),
            (f'{base}/Account/Login', {'ReturnUrl': return_url, 'Input.Username': USERNAME, 'Input.Password': PASSWORD}),
            (f'{base}/Account/Login', {'ReturnUrl': return_url, 'Email': USERNAME, 'Password': PASSWORD}),
            (f'{base}/api/Account/Login', {'ReturnUrl': return_url, 'Username': USERNAME, 'Password': PASSWORD}),
            (f'{base}/api/account/login', {'returnUrl': return_url, 'username': USERNAME, 'password': PASSWORD}),
            # JSON body attempts
            (f'{base}/Account/Login', None, {'Content-Type': 'application/json'},
             json.dumps({'ReturnUrl': return_url, 'Username': USERNAME, 'Password': PASSWORD})),
        ]

        for i, test in enumerate(tests):
            url = test[0]
            data = test[1]
            log(f"\n[Test {i+1}] POST {url.split('/')[-2]}/{url.split('/')[-1]}")
            log(f"  Params: {list(data.keys()) if data else 'JSON'}")

            headers = {
                'User-Agent': session.headers['User-Agent'],
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': login_url,
                'Origin': 'https://sso.sflep.com',
            }

            body = data
            if len(test) >= 3:
                headers.update(test[2])
            if len(test) >= 4:
                body = test[3]

            try:
                if isinstance(body, str):
                    r = session.post(url, data=body, headers=headers, allow_redirects=False, timeout=30)
                else:
                    r = session.post(url, data=body, headers=headers, allow_redirects=False, timeout=30)
                log(f"  Status: {r.status_code}")
                log(f"  Location: {r.headers.get('Location', 'N/A')[:200]}")
                # Show FULL error body
                if r.status_code >= 400:
                    log(f"  FULL Body: {r.text}")
                if r.status_code in (301, 302, 303):
                    log(f"  *** REDIRECT! ***")
                    redir = r.headers['Location']
                    if not redir.startswith('http'):
                        redir = f'https://sso.sflep.com{redir}'
                    r2 = session.get(redir, allow_redirects=True, timeout=30,
                                    headers={'User-Agent': session.headers['User-Agent']})
                    log(f"  Final: {r2.url}")
                    if 'welearn' in r2.url.lower() or '我的主页' in r2.text:
                        log(f"  *** SUCCESS! ***")
                        r3 = session.get(
                            'https://welearn.sflep.com/ajax/authCourse.aspx?action=gmc',
                            headers={'Referer': 'https://welearn.sflep.com/student/index.aspx',
                                    'User-Agent': session.headers['User-Agent']},
                            timeout=30)
                        log(f"  Courses: {r3.text[:300]}")
                        break
            except Exception as e:
                log(f"  ERROR: {e}")

    except Exception as e:
        import traceback
        log(traceback.format_exc())
    finally:
        with open('sso_debug3.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(output))
        print("\n结果已保存到 sso_debug3.txt")
        input("按回车键退出...")

if __name__ == '__main__':
    main()
