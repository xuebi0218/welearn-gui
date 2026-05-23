# -*- coding: utf-8 -*-
import requests, re, sys, traceback
from urllib.parse import urlparse, parse_qs, unquote

# ── 全局异常捕获 ──
output = []
def log(msg):
    output.append(str(msg))
    print(str(msg))
    sys.stdout.flush()

def save_and_exit():
    with open('sso_debug2.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))
    print("\n结果已保存到 sso_debug2.txt")
    input("按回车键退出...")

def main():
    try:
        session = requests.Session()
        session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

        log("=" * 60)
        log("Welearn SSO 诊断 v2")
        log("=" * 60)

        USERNAME = input("请输入账号: ").strip()
        PASSWORD = input("请输入密码: ").strip()

        # Step 1: prelogin -> follow redirects
        log("\n[Step 1] 跟随重定向链...")
        try:
            r = session.get(
                'https://welearn.sflep.com/user/prelogin.aspx?loginret=http%3a%2f%2fwelearn.sflep.com%2fuser%2floginredirect.aspx',
                timeout=30, allow_redirects=True)
            log(f"  最终URL: {r.url}")
        except Exception as e:
            log(f"  ERROR: {e}")
            return

        # 从重定向链中提取 ReturnUrl
        return_url = None
        login_page_url = None
        for h in r.history:
            loc = h.headers.get('Location', '')
            log(f"  Redirect: {h.status_code} -> {loc[:150]}")
            if 'ReturnUrl=' in loc:
                parsed = parse_qs(urlparse(loc).query)
                return_url = parsed.get('ReturnUrl', [None])[0]
                if return_url:
                    log(f"  -> ReturnUrl: {unquote(return_url)[:150]}...")
            if '/Account/Login' in loc:
                if loc.startswith('http'):
                    login_page_url = loc
                else:
                    login_page_url = f'https://sso.sflep.com{loc}'

        if not login_page_url:
            log("  未找到 Account/Login URL，尝试构造...")
            if return_url:
                login_page_url = f'https://sso.sflep.com/idsvr/Account/Login?ReturnUrl={return_url}'
            else:
                log("  无 ReturnUrl，无法继续")
                return

        log(f"\n  登录页URL: {login_page_url[:200]}")

        # Step 2: GET login page
        log("\n[Step 2] GET Account/Login...")
        try:
            r = session.get(login_page_url, timeout=30)
            log(f"  状态码: {r.status_code}")
            log(f"  页面标题: {re.search(r'<title>([^<]*)</title>', r.text).group(1) if '<title>' in r.text else 'N/A'}")
            log(f"  HTML前400字符: {r.text[:400]}")
        except Exception as e:
            log(f"  ERROR: {e}")

        # Step 3: 尝试多种 POST 参数
        if not return_url:
            log("\n  无 ReturnUrl，跳过POST测试")
            return

        attempts = [
            {'ReturnUrl': return_url, 'Username': USERNAME, 'Password': PASSWORD, 'RememberMe': 'false', 'button': 'login'},
            {'ReturnUrl': return_url, 'Username': USERNAME, 'Password': PASSWORD, 'button': 'login'},
            {'ReturnUrl': return_url, 'Account': USERNAME, 'Password': PASSWORD},
            {'ReturnUrl': return_url, 'username': USERNAME, 'password': PASSWORD},
            {'returnUrl': return_url, 'username': USERNAME, 'password': PASSWORD},
            {'returnUrl': return_url, 'Username': USERNAME, 'Password': PASSWORD},
        ]

        for i, data in enumerate(attempts):
            log(f"\n[Step 3.{i+1}] POST params={list(data.keys())}...")
            try:
                r = session.post(login_page_url, data=data,
                               headers={'User-Agent': session.headers['User-Agent'],
                                       'Content-Type': 'application/x-www-form-urlencoded',
                                       'Referer': login_page_url},
                               allow_redirects=False, timeout=30)
                log(f"  状态码: {r.status_code}")
                loc = r.headers.get('Location', 'N/A')
                log(f"  Location: {loc[:250]}")

                if r.status_code in (301, 302, 303, 307, 308):
                    log(f"  *** 重定向！可能是登录成功！ ***")
                    # 跟随看看
                    redir_url = loc
                    if not redir_url.startswith('http'):
                        redir_url = f'https://sso.sflep.com{loc}'
                    r2 = session.get(redir_url, allow_redirects=True, timeout=30,
                                    headers={'User-Agent': session.headers['User-Agent']})
                    log(f"  跟随重定向后URL: {r2.url}")
                    if '我的主页' in r2.text or 'welearn.sflep.com/student' in r2.url:
                        log(f"  *** 登录成功!!! ***")
                        # 验证课程
                        r3 = session.get(
                            'https://welearn.sflep.com/ajax/authCourse.aspx?action=gmc',
                            headers={'Referer': 'https://welearn.sflep.com/student/index.aspx',
                                    'User-Agent': session.headers['User-Agent']},
                            timeout=30)
                        log(f"  课程API: {r3.text[:300]}")
                        break
                else:
                    log(f"  Body前200: {r.text[:200]}")
            except Exception as e:
                log(f"  ERROR: {e}")

    except Exception as e:
        log(f"\nFATAL: {traceback.format_exc()}")
    finally:
        save_and_exit()

if __name__ == '__main__':
    main()
