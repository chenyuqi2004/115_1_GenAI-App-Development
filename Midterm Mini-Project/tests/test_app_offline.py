"""離線測試：真實 OpenAI SDK＋模擬 HTTP，不連線、不計費，也不是模型成果。

在 Midterm Mini-Project 資料夾執行：python -X utf8 tests/test_app_offline.py
"""

import json
import os
from pathlib import Path
from unittest import mock

import httpx
import openai
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
FAKE_KEY = "sk-offline-test-not-real"

GOOD = {
    "required_skills": ["Python", "SQL"],
    "matched_skills": ["Python：課堂專題使用"],
    "skill_gaps": ["SQL：職缺要求基本查詢"],
    "missing_info": [],
    "application_advice": "可以投遞，但建議先補強 SQL。",
}


def body(text, status="completed", refusal=None):
    """組出 Responses API 的回應；只有這段是假的，SDK 與解析都是真的。"""
    content = (
        {"type": "refusal", "refusal": refusal}
        if refusal
        else {"type": "output_text", "text": text, "annotations": []}
    )
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 0,
        "status": status,
        "model": "fake",
        "output": [{
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [content],
        }],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
    }


class Server:
    """記錄請求數與內容的假伺服器。"""

    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload if payload is not None else body(json.dumps(GOOD))
        self.requests = []

    def __call__(self, request):
        self.requests.append(json.loads(request.content))
        return httpx.Response(self.status_code, json=self.payload)


def start(server, key=FAKE_KEY):
    """啟動 App，把 SDK 的網路層換成假伺服器。"""
    real_client = openai.OpenAI

    def client(**kwargs):
        return real_client(
            http_client=httpx.Client(transport=httpx.MockTransport(server)),
            **kwargs,
        )

    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    if key:
        env["OPENAI_API_KEY"] = key
    # 不讀本機 .env，測試結果才不受自己是否放了真金鑰影響。
    patches = [
        mock.patch.dict(os.environ, env, clear=True),
        mock.patch("openai.OpenAI", client),
        mock.patch("dotenv.load_dotenv", lambda *args, **kwargs: False),
    ]
    for patch in patches:
        patch.start()
    at = AppTest.from_file(APP, default_timeout=30).run()
    return at, patches


def stop(patches):
    for patch in patches:
        patch.stop()


def click(at, label):
    next(b for b in at.button if b.label == label).click()
    return at.run()


def submit(at, job="需要 Python 與 SQL", skills="我會 Python"):
    at.text_area[0].input(job)
    at.text_area[1].input(skills)
    return click(at, "開始分析")


def errors(at):
    return " ".join(e.value for e in at.error)


def check(name, condition, detail=""):
    print(("PASS" if condition else "FAIL"), name, detail if not condition else "")
    return bool(condition)


def scenario_offline(results):
    server = Server()
    at, patches = start(server)
    try:
        results.append(check("預設關閉 API", at.checkbox[0].value is False and not at.exception))
        results.append(check("預設沒有結果與錯誤", not at.success and not at.error))

        submit(at, job="   ")
        results.append(check("職缺空白被擋", "職缺描述" in errors(at)))
        submit(at, skills="   ")
        results.append(check("技能空白被擋", "技能簡述" in errors(at)))

        submit(at, job="文" * 6000, skills="字")
        results.append(check("合計 6001 字元被擋", "6001" in errors(at)))

        submit(at, job="文" * 5999, skills="字")
        results.append(check("合計 6000 字元通過", not at.error and at.info))
        results.append(check("離線模式沒有結果", not at.success))
        results.append(check("離線全程 0 次請求", len(server.requests) == 0))
    finally:
        stop(patches)


def scenario_missing_key(results):
    server = Server()
    at, patches = start(server, key="")
    try:
        at.checkbox[0].check().run()
        submit(at)
        results.append(check("缺金鑰在請求前停止", "OPENAI_API_KEY" in errors(at) and not server.requests))
    finally:
        stop(patches)


def scenario_success(results):
    server = Server()
    at, patches = start(server)
    try:
        at.checkbox[0].check().run()
        submit(at)
        results.append(check("成功顯示結果", at.success and not at.error and not at.exception))
        results.append(check("一次提交 1 次請求", len(server.requests) == 1))

        sent = server.requests[0]
        schema = sent["text"]["format"]
        results.append(check("送出 strict Schema", schema["type"] == "json_schema" and schema["strict"] is True))
        results.append(check("Schema 禁止多餘欄位", schema["schema"]["additionalProperties"] is False))
        results.append(check("Schema 全部必填", set(schema["schema"]["required"]) == set(GOOD)))
        results.append(check("store=False", sent["store"] is False))
        results.append(check("兩段原文都送出", "需要 Python 與 SQL" in sent["input"] and "我會 Python" in sent["input"]))

        headings = [s.value for s in at.subheader]
        results.append(check("欄位標籤都顯示", headings == ["職缺要求", "我已符合", "待補強", "還需要確認的資訊", "投遞建議"], headings))
        results.append(check("附上當筆原文", any("需要 Python 與 SQL" in t.value for t in at.text)))
        results.append(check("分類數量相符不警告", not at.warning))

        at.run()
        results.append(check("一般重跑保留結果", at.success and len(server.requests) == 1))

        submit(at, job="   ")
        results.append(check("再送出失敗清掉舊結果", not at.success and "職缺描述" in errors(at)))
        results.append(check("失敗提交不追加請求", len(server.requests) == 1))

        submit(at)
        click(at, "清除結果")
        results.append(check("清除按鈕清掉結果", not at.success and len(server.requests) == 2))

        submit(at)
        at.checkbox[0].uncheck().run()
        results.append(check("切換開關清掉結果", not at.success and len(server.requests) == 3))
    finally:
        stop(patches)


def scenario_count_warning(results):
    data = dict(GOOD, skill_gaps=[])
    server = Server(payload=body(json.dumps(data)))
    at, patches = start(server)
    try:
        at.checkbox[0].check().run()
        submit(at)
        results.append(check("分類數量不符會警告", at.success and at.warning))
    finally:
        stop(patches)


def scenario_failures(results):
    missing = {k: v for k, v in GOOD.items() if k != "skill_gaps"}
    cases = {
        "拒答": Server(payload=body("", refusal="無法處理")),
        "未完成": Server(payload=body(json.dumps(GOOD), status="incomplete")),
        "空回應": Server(payload=body("")),
        "壞 JSON": Server(payload=body("{不是 JSON")),
        "少欄位": Server(payload=body(json.dumps(missing))),
        "多欄位": Server(payload=body(json.dumps(dict(GOOD, extra="x")))),
        "型別錯誤": Server(payload=body(json.dumps(dict(GOOD, skill_gaps="SQL")))),
        "文字全空白": Server(payload=body(json.dumps(dict(GOOD, application_advice="  ")))),
        "清單項目空白": Server(payload=body(json.dumps(dict(GOOD, missing_info=[" "])))),
        "服務錯誤 500": Server(status_code=500, payload={"error": {"message": FAKE_KEY}}),
    }
    for name, server in cases.items():
        at, patches = start(server)
        try:
            at.checkbox[0].check().run()
            submit(at)
            ok = at.error and not at.success and not at.exception
            results.append(check(f"{name}：不保存並顯示錯誤", ok, errors(at)))
            results.append(check(f"{name}：不重試", len(server.requests) == 1, len(server.requests)))
            results.append(check(f"{name}：錯誤不含金鑰", FAKE_KEY not in errors(at)))
        finally:
            stop(patches)


def main():
    results = []
    scenario_offline(results)
    scenario_missing_key(results)
    scenario_success(results)
    scenario_count_warning(results)
    scenario_failures(results)
    print(f"\n{sum(results)}/{len(results)} 通過")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
