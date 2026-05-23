import re
import sys
import traceback
from random import randint

import requests

# 标准请求头
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# 全局异常捕获，防止闪退
def global_excepthook(exc_type, exc_value, exc_tb):
    print('\n' + '='*51)
    print('程序出现未捕获的异常:')
    traceback.print_exception(exc_type, exc_value, exc_tb)
    print('='*51)
    input('\n按任意键退出...')
    sys.exit(1)
sys.excepthook = global_excepthook

session = requests.Session()
def printline():
    print('-'*51)
# 获取账户密码
try:  # 直接从命令行中获取
    username, password = sys.argv[1], sys.argv[2]
except:
    loginmode=input('请选择登录方式: \n  1.账号密码登录(暂时废弃,请直接使用cookies) \n  2.Cookie登录\n\n请输入数字1或2: ')
    printline()
    if loginmode=='1':
        username = input('请输入账号: ')
        password = input('请输入密码: ')
        # 登录模块
        response = requests.get(
            'https://welearn.sflep.com/user/prelogin.aspx?loginret=http%3a%2f%2fwelearn.sflep.com%2fuser%2floginredirect.aspx', allow_redirects=False)
        rturl = response.headers['Location'].replace(
            'https://sso.sflep.com/idsvr', '')
        data = {
            'rturl': rturl,
            'account': username,
            'pwd': password,
        }
        res = session.post(
            "https://sso.sflep.com/idsvr/account/login", data=data)
        url = 'https://sso.sflep.com/idsvr'+rturl
        res = session.get(url)
        if "我的主页" in res.text:
            print("登录成功!!")
        else:
            input("登录失败!!")
            exit(0)
    elif loginmode=='2':
        cookie_str = input('请粘贴Cookie: ').strip()
        try:
            cookie = {}
            for item in cookie_str.split(";"):
                item = item.strip()
                if item and '=' in item:
                    k, v = item.split('=', 1)
                    cookie[k.strip()] = v.strip()
            if not cookie:
                raise ValueError("空Cookie")
        except:
            input('Cookie输入错误!!!')
            exit(0)
        for k,v in cookie.items():
              session.cookies[k]=v
    else:
        input('输入错误!!')
        exit(0)
# 验证Cookie是否有效
try:
    headers = DEFAULT_HEADERS.copy()
    headers['Referer'] = 'https://welearn.sflep.com/student/index.aspx'
    test_req = session.get('https://welearn.sflep.com/ajax/authCourse.aspx?action=gmc',
                           headers=headers)
    if '\"clist\":[]}' in test_req.text or '错误' in test_req.text:
        input('\nCookie无效或已过期，请重新获取Cookie后重试！')
        exit(0)
except requests.exceptions.RequestException:
    input('\n网络连接失败，请检查网络后重试！')
    exit(0)
printline()
while True:
    # 查询课程信息
    url = "https://welearn.sflep.com/ajax/authCourse.aspx?action=gmc"
    headers = DEFAULT_HEADERS.copy()
    headers['Referer'] = 'https://welearn.sflep.com/student/index.aspx'
    response = session.get(url, headers=headers)
    
    if not response.text.strip():
        input('错误: 服务器返回空响应，请检查网络连接或稍后重试!')
        exit(0)
    
    if '\"clist\":[]}' in response.text:
        input('发生错误!!!可能是登录错误或没有课程!!!')
        exit(0)
    
    try:
        back = response.json()["clist"]
    except ValueError as e:
        input(f'错误: 服务器返回的数据格式不正确! 错误信息: {e}\n响应内容: {response.text[:200]}...')
        exit(0)
    
    print('查询课程成功!!!')
    printline()
    print('我的课程: \n')
    for i, course in enumerate(back, start=1):
        print(f'[NO.{i:>2}] 完成度{course["per"]:>3}% {course["name"]}')

    # 选择课程
    order = int(input("\n请输入需要完成的课程序号（上方[]内的数字）: "))
    cid = back[order - 1]["cid"]
    printline()
    print("获取单元中...")
    printline()
    # 刷课模块
    url = f"https://welearn.sflep.com/student/course_info.aspx?cid={cid}"
    headers = DEFAULT_HEADERS.copy()
    response = session.get(url, headers=headers)

    uid = re.search('"uid":(.*?),', response.text).group(1)
    classid = re.search('"classid":"(.*?)"', response.text).group(1)

    url = 'https://welearn.sflep.com/ajax/StudyStat.aspx'
    headers = DEFAULT_HEADERS.copy()
    headers['Referer'] = 'https://welearn.sflep.com/student/course_info.aspx'
    response = session.get(url, params={'action':'courseunits','cid':cid,'uid':uid}, headers=headers)
    back = response.json()['info']

    # 选择单元 使用了WELearnToSleeep的代码
    print('[NO. 0]  按顺序完成全部单元课程')
    unitsnum = len(back)
    for i,x in enumerate(back,start=1):
        if x['visible']=='true':
            print(f'[NO.{i:>2d}]  [已开放]  {x["unitname"]}  {x["name"]}')
        else:
            print(f'[NO.{i:>2d}] ![未开放]! {x["unitname"]}  {x["name"]}')
    unitidx = int(input('\n\n请选择需要完成的单元序号（上方[]内的数字，输入0为按顺序刷全部单元）： '))
    printline()
    inputcrate = input('模式1:每个练习指定正确率，请直接输入指定的正确率\n如:希望每个练习正确率均为100，则输入 100\n\n模式2:每个练习随机正确率，请输入正确率上下限并用英文逗号隔开\n如:希望每个练习正确率为70～100，则输入 70,100\n\n请严格按照以上格式输入每个练习的正确率: ')
    if ',' in inputcrate:
        mycrate=[int(x.strip()) for x in inputcrate.split(',')]
        randommode=True
    else:
        mycrate=inputcrate
        randommode=False
    printline()
    # 伪造请求
    way1Succeed, way2Succeed, way1Failed, way2Failed = 0, 0, 0, 0

    ajaxUrl = "https://welearn.sflep.com/Ajax/SCO.aspx"
    infoHeaders = DEFAULT_HEADERS.copy()
    infoHeaders["Referer"] = f"https://welearn.sflep.com/student/course_info.aspx?cid={cid}"

    if(unitidx == 0):
        i = 0
    else:
        i = unitidx - 1
        unitsnum = unitidx

    while True:
        headers = DEFAULT_HEADERS.copy()
        headers.update(infoHeaders)
        response = session.get(
            f'https://welearn.sflep.com/ajax/StudyStat.aspx?action=scoLeaves&cid={cid}&uid={uid}&unitidx={i}&classid={classid}', headers=headers)

        if "异常" in response.text or "出错了" in response.text:
            break

        for course in response.json()["info"]:
            if course['isvisible']=='false':  # 跳过未开放课程
                print(f'[!!跳过!!]    {course["location"]}')
            elif "未" in course["iscomplete"]:  # 章节未完成
                print(f'[即将完成]    {course["location"]}')
                if randommode is True:
                    crate=str(randint(mycrate[0],mycrate[1]))
                else:
                    crate=mycrate
                data = '{"cmi":{"completion_status":"completed","interactions":[],"launch_data":"","progress_measure":"1","score":{"scaled":"'+crate+'","raw":"100"},"session_time":"0","success_status":"unknown","total_time":"0","mode":"normal"},"adl":{"data":[]},"cci":{"data":[],"service":{"dictionary":{"headword":"","short_cuts":""},"new_words":[],"notes":[],"writing_marking":[],"record":{"files":[]},"play":{"offline_media_id":"9999"}},"retry_count":"0","submit_time":""}}[INTERACTIONINFO]'

                id = course["id"]
                study_headers = DEFAULT_HEADERS.copy()
                study_headers["Referer"] = f"https://welearn.sflep.com/Student/StudyCourse.aspx?cid={cid}&classid={classid}&sco={id}"
                session.post(ajaxUrl, data={"action": "startsco160928",
                                            "cid": cid,
                                            "scoid": id,
                                            "uid": uid
                                            },
                             headers=study_headers)
                response = session.post(ajaxUrl, data={"action": "setscoinfo",
                                                       "cid": cid,
                                                       "scoid": id,
                                                       "uid": uid,
                                                       "data": data,
                                                       "isend": "False" },
                                        headers=study_headers)
                print(f'>>>>>>>>>>>>>>正确率:{crate:>3}%',end='  ')
                if '"ret":0' in response.text:
                    print("方式1:成功!!!", end="  ")
                    way1Succeed += 1
                else:
                    print("方式1:失败!!!", end="  ")
                    way1Failed += 1

                response = session.post(ajaxUrl, data={"action": "savescoinfo160928",
                                                       "cid": cid,
                                                       "scoid": id,
                                                       "uid": uid,
                                                       "progress": "100",
                                                       "crate": crate,
                                                       "status": "unknown",
                                                       "cstatus": "completed",
                                                       "trycount": "0",
                                                       },
                                        headers=study_headers)
#                sleep(1) # 延迟1秒防止服务器压力过大
                if '"ret":0' in response.text:
                    print("方式2:成功!!!")
                    way2Succeed += 1
                else:
                    print("方式2:失败!!!")
                    way2Failed += 1
            else:  # 章节已完成
                print(f'[ 已完成 ]    {course["location"]}')

        if unitidx != 0:
            break
        else:
            i += 1
    if unitidx == 0:
        break
    else:
        print('本单元运行完毕！回到选课处！！\n\n\n\n')
        printline()

printline()
print(f"""
***************************************************
全部完成!!

总计:
方式1: {way1Succeed} 成功, {way1Failed} 失败
方式2: {way2Succeed} 成功, {way2Failed} 失败

**********  有问题请邮件联系hhy5562877@163.com  **********""")
input("按任意键退出")