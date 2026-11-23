import akshare as ak
import requests
import json
import os
from datetime import datetime

# ========== 配置区 ==========
watch_list = [
    {
        "name": "悍高集团",
        "code": "001221",
        "type": "hold",
        "rate_threshold": 1.0,
        "buy_price": None
    },
    {
        "name": "建设银行",
        "code": "601939",
        "type": "watch",
        "rate_threshold": 1.8,
        "buy_price": 5.30
    },
    {
        "name": "招商银行",
        "code": "600036",
        "type": "watch",
        "rate_threshold": 2.0,
        "buy_price": 26.50
    },
    {
        "name": "中国神华",
        "code": "601088",
        "type": "watch",
        "rate_threshold": 2.2,
        "buy_price": 33.50
    },
    {
        "name": "格力电器",
        "code": "000651",
        "type": "watch",
        "rate_threshold": 2.8,
        "buy_price": 32.00
    },
    {
        "name": "长江电力",
        "code": "600900",
        "type": "watch",
        "rate_threshold": 1.5,
        "buy_price": 24.20
    },
    {
        "name": "美的集团",
        "code": "000333",
        "type": "watch",
        "rate_threshold": 2.8,
        "buy_price": 48.00
    },
    {
        "name": "贵州茅台",
        "code": "600519",
        "type": "watch",
        "rate_threshold": 2.5,
        "buy_price": 1420.00
    },
    {
        "name": "现货黄金",
        "code": "XAUUSD",
        "type": "outer",
        "rate_threshold": 1.2,
        "buy_price": None
    },
    {
        "name": "纳斯达克指数",
        "code": "NDX",
        "type": "outer",
        "rate_threshold": 1.8,
        "buy_price": None
    }
]

# ========== 企微环境变量 ==========
CORP_ID = os.getenv("CORP_ID")
CORP_SECRET = os.getenv("CORP_SECRET")
AGENT_ID = os.getenv("AGENT_ID")
TO_USER = os.getenv("TO_USER")

# ========== 企微推送 ==========
def get_access_token():
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORP_ID}&corpsecret={CORP_SECRET}"
    resp = requests.get(url, timeout=10)
    return resp.json()["access_token"]

def send_wecom_msg(content):
    token = get_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    data = {
        "touser": TO_USER,
        "msgtype": "text",
        "agentid": int(AGENT_ID),
        "text": {"content": content}
    }
    requests.post(url, json=data, timeout=10)

# ========== 行情获取 ==========
def get_a_stock(symbol: str):
    df = ak.stock_zh_a_spot_em()
    row = df[df["代码"] == symbol]
    if row.empty:
        return None
    price = float(row["最新价"].iloc[0])
    pct = float(row["涨跌幅"].iloc[0])
    return {"price": price, "pct": pct}

def get_xauusd():
    df = ak.fx_spot_quote()
    row = df[df["品种"] == "现货黄金"]
    if row.empty:
        return None
    price = float(row["最新价"].iloc[0])
    pct = float(row["涨跌幅"].iloc[0])
    return {"price": price, "pct": pct}

def get_ndx():
    df = ak.stock_us_index()
    row = df[df["名称"] == "纳斯达克综合指数"]
    if row.empty:
        return None
    price = float(row["最新价"].iloc[0])
    pct = float(row["涨跌幅"].iloc[0])
    return {"price": price, "pct": pct}

# ========== 早报：昨日收盘汇总 ==========
def run_daily_report():
    lines = ["=====【昨日收盘早报】====="]
    lines.append("【持仓】")
    hg = ak.stock_zh_a_hist(symbol="001221", period="daily", adjust="qfq").iloc[-1]
    lines.append(f"悍高集团(001221)：{hg['收盘']:.2f}  昨涨跌：{hg['涨跌幅']:.2f}%")

    lines.append("【观察池】")
    watch_codes = [
        ("601939", "建设银行",5.30),
        ("600036", "招商银行",26.50),
        ("601088", "中国神华",33.50),
        ("000651", "格力电器",32.00),
        ("600900", "长江电力",24.20),
        ("000333", "美的集团",48.00),
        ("600519", "贵州茅台",1420.00)
    ]
    for code,name,buy in watch_codes:
        row = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").iloc[-1]
        lines.append(f"{name}({code})：{row['收盘']:.2f}  目标买入价：{buy:.2f}")

    lines.append("【长期追踪】")
    g = get_xauusd()
    n = get_ndx()
    if g:
        lines.append(f"现货黄金：{g['price']:.2f}  涨跌：{g['pct']:.2f}%")
    if n:
        lines.append(f"纳斯达克指数：{n['price']:.2f}  涨跌：{n['pct']:.2f}%")
    lines.append("=========================")
    lines.append("今日重点留意：悍高异动；观察池等待买点")
    msg = "\n".join(lines)
    send_wecom_msg(msg)
    print("早报已发送")

# ========== 盘中告警监控 ==========
def run_alert():
    now = datetime.now()
    hour = now.hour
    # 外盘静默窗口 23:00 ~ 07:00
    outer_silent = (hour >=23) or (hour <7)

    alert_msg_list = []

    for item in watch_list:
        name = item["name"]
        code = item["code"]
        stype = item["type"]
        rate_th = item["rate_threshold"]
        buy_p = item["buy_price"]

        if stype in ["hold","watch"]:
            res = get_a_stock(code)
        elif code == "XAUUSD":
            res = get_xauusd()
        elif code == "NDX":
            res = get_ndx()
        else:
            res = None
        if not res:
            print(f"{name} 行情获取失败")
            continue
        price = res["price"]
        pct = res["pct"]

        # 外盘静默判断
        if stype == "outer" and outer_silent:
            continue

        # 1.涨跌幅异动告警
        if abs(pct) >= rate_th:
            if stype == "hold":
                title = "【告警｜持仓】"
            elif stype == "watch":
                title = "【告警｜观察波动】"
            else:
                title = "【告警｜外盘追踪】"
            txt = (
                f"{title}{name} {code}\n"
                f"现价：{price:.2f}\n"
                f"日内涨跌幅：{pct:.2f}%\n"
                f"触发原因：涨跌幅超过±{rate_th}%"
            )
            alert_msg_list.append(txt)

        # 2.买点告警（仅观察池）
        if stype == "watch" and buy_p is not None:
            if price <= buy_p:
                txt = (
                    f"【告警｜观察买点】{name} {code}\n"
                    f"现价：{price:.2f}\n"
                    f"目标买入价：{buy_p:.2f}\n"
                    f"触发原因：到达预设买入位置，可以留意"
                )
                alert_msg_list.append(txt)

    if alert_msg_list:
        full_msg = "\n\n".join(alert_msg_list)
        send_wecom_msg(full_msg)
        print("告警已推送：\n", full_msg)
    else:
        print("本轮无告警")

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv)>=2 else "alert"
    if mode == "report":
        run_daily_report()
    else:
        run_alert()
