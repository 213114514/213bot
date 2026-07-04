import asyncio
import json
import websockets
import httpx

# ===================== 核心配置 =====================
NAPCAT_WS_URL = "ws://127.0.0.1:30001/onebot/v11/ws"  # NapCat正向WS地址
SELF_QQ_UIN = 3407268500  # 机器人自身的QQ号
RECONNECT_INTERVAL = 5  # 断开后重连间隔（秒）
PRIVATE_REPLY_CONTENT = "你好"  # 私聊默认回复内容

# Kirara AI 配置
KIRARA_API_URL = "http://localhost:8084/v1/chat"  # Kirara AI的v1接口（推荐）
KIRARA_TIMEOUT = 30.0  # Kirara AI接口超时时间

# 创建全局httpx异步客户端
httpx_client = httpx.AsyncClient(timeout=KIRARA_TIMEOUT)


# ===================== 发送消息函数 =====================
async def send_private_msg(websocket, user_id: int, message: str):
    """发送私聊消息"""
    send_data = {
        "action": "send_private_msg",
        "params": {
            "user_id": user_id,
            "message": [
                {
                    "type": "text",
                    "data": {
                        "text": message
                    }
                }
            ],
            "echo": f"echo_{asyncio.get_event_loop().time()}"
        }
    }

    try:
        await websocket.send(json.dumps(send_data, ensure_ascii=False))
        print(f"✅ 已向用户[{user_id}]发送私聊回复: {message[:20]}...")
    except Exception as e:
        print(f"❌ 发送私聊消息失败: {str(e)}")


async def send_group_msg(websocket, group_id: int, message: str):
    """发送群消息"""
    send_data = {
        "action": "send_group_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {
                    "type": "text",
                    "data": {
                        "text": message
                    }
                }
            ],
            "echo": f"echo_{asyncio.get_event_loop().time()}"
        }
    }

    try:
        await websocket.send(json.dumps(send_data, ensure_ascii=False))
        print(f"✅ 已向群[{group_id}]发送回复: {message[:20]}...")
    except Exception as e:
        print(f"❌ 发送群消息失败: {str(e)}")


# ===================== 调用Kirara AI =====================
async def call_kirara_ai(session_id: str, username: str, message: str) -> str:
    """
    调用Kirara AI的/v1/chat接口获取回复
    :param session_id: 会话ID（区分不同会话）
    :param username: 用户名
    :param message: 用户消息
    :return: AI回复文本（失败返回空字符串）
    """
    if not message.strip():
        return ""

    # 构造请求参数（严格匹配文档要求）
    request_data = {
        "session_id": session_id,
        "username": username,
        "message": message.strip()
    }

    try:
        print(f"📡 调用Kirara AI: {KIRARA_API_URL} | 会话ID: {session_id} | 消息: {message[:20]}...")
        # 发送POST请求
        response = await httpx_client.post(
            KIRARA_API_URL,
            json=request_data,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )

        # 检查HTTP状态码
        response.raise_for_status()

        # 解析响应
        resp_data = response.json()
        print(f"📩 Kirara AI响应: {json.dumps(resp_data, ensure_ascii=False)}")

        # 处理响应结果（兼容SUCCESS/DONE状态）
        if resp_data.get("result") in ["SUCCESS", "DONE"] and resp_data.get("message"):
            # 拼接多段消息（message是数组）
            reply_text = "".join(resp_data["message"]).strip()
            return reply_text if reply_text else ""

        print(f"⚠️ Kirara AI返回无有效内容: {resp_data.get('result')}")
        return ""

    except httpx.HTTPStatusError as e:
        print(f"❌ Kirara AI HTTP错误: {e.response.status_code} - {e.response.text}")
        return ""
    except httpx.ConnectError:
        print(f"❌ 无法连接到Kirara AI服务: {KIRARA_API_URL}")
        return ""
    except json.JSONDecodeError:
        print(f"❌ Kirara AI返回非JSON格式响应: {response.text if 'response' in locals() else '无内容'}")
        return ""
    except Exception as e:
        print(f"❌ Kirara AI调用异常: {type(e).__name__} - {str(e)}")
        return ""


# ===================== 消息处理函数 =====================
async def handle_message(websocket, raw_msg: str):
    """处理接收到的NapCat消息"""
    try:
        # 解析JSON消息
        msg_data = json.loads(raw_msg)

        # 1. 打印完整消息（便于调试）
        formatted_msg = json.dumps(msg_data, ensure_ascii=False, indent=2)
        print("\n" + "=" * 60)
        print("📥 收到NapCat消息:")
        print(formatted_msg)
        print("=" * 60 + "\n")

        # 2. 处理私聊消息（直接回复固定内容）
        if (msg_data.get("post_type") == "message"
                and msg_data.get("message_type") == "private"
                and msg_data.get("user_id") != SELF_QQ_UIN):

            user_id = msg_data.get("user_id")
            raw_content = msg_data.get("raw_message", "")
            print(f"🔍 识别到私聊消息 - 用户[{user_id}]: {raw_content[:20]}...")
            await send_private_msg(websocket, user_id, PRIVATE_REPLY_CONTENT)

        # 3. 处理群聊@机器人消息（调用Kirara AI回复）
        elif (msg_data.get("post_type") == "message"
              and msg_data.get("message_type") == "group"
              and msg_data.get("user_id") != SELF_QQ_UIN):

            group_id = msg_data.get("group_id")
            user_id = msg_data.get("user_id")
            message_segments = msg_data.get("message", [])
            raw_content = msg_data.get("raw_message", "")

            # 检查是否@了机器人
            is_at_me = False
            for segment in message_segments:
                if segment.get("type") == "at" and segment.get("data", {}).get("qq") == str(SELF_QQ_UIN):
                    is_at_me = True
                    break

            # 如果@了机器人，调用Kirara AI回复
            if is_at_me:
                print(f"🔍 识别到群@消息 - 群[{group_id}] 用户[{user_id}]: {raw_content[:20]}...")

                # 构造Kirara AI的会话ID和用户名（区分不同群/用户）
                session_id = f"group-{group_id}-{user_id}"  # 群+用户唯一会话ID
                username = f"qq-{user_id}"  # 用户名格式：qq-用户ID

                # 清理消息内容（移除@机器人的部分）
                clean_message = raw_content.replace(f"[CQ:at,qq={SELF_QQ_UIN}]", "").strip()
                # 如果清理后为空，使用原始消息
                if not clean_message:
                    clean_message = raw_content

                # 调用Kirara AI获取回复
                kirara_reply = await call_kirara_ai(session_id, username, clean_message)

                # 发送回复（有内容才发送）
                if kirara_reply:
                    await send_group_msg(websocket, group_id, kirara_reply)
                else:
                    print(f"⚠️ Kirara AI未返回有效回复，跳过发送")

    except json.JSONDecodeError:
        # 非JSON格式消息直接输出
        print("\n" + "=" * 60)
        print("📥 收到非JSON格式消息:")
        print(raw_msg)
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"⚠️ 消息处理出错: {type(e).__name__} - {str(e)}")


# ===================== 连接NapCat =====================
async def connect_napcat():
    """连接NapCat正向WS，持续接收并处理消息"""
    while True:
        try:
            print(f"🔌 正在连接NapCat WS: {NAPCAT_WS_URL}")
            # 建立WebSocket连接
            async with websockets.connect(NAPCAT_WS_URL) as websocket:
                print("✅ 成功连接NapCat！开始监听消息...")

                # 持续接收消息并处理
                async for message in websocket:
                    await handle_message(websocket, message)

        except websockets.exceptions.ConnectionClosed:
            print("🔌 NapCat连接已断开")
        except Exception as e:
            print(f"❌ 连接出错: {type(e).__name__} - {str(e)}")

        # 断开后自动重连
        print(f"⏳ {RECONNECT_INTERVAL}秒后尝试重连...\n")
        await asyncio.sleep(RECONNECT_INTERVAL)


# ===================== 程序退出清理 =====================
async def cleanup():
    """程序退出时清理资源"""
    await httpx_client.aclose()
    print("🧹 已关闭HTTP客户端连接")


# ===================== 程序入口 =====================
if __name__ == "__main__":
    # Windows系统事件循环兼容处理
    if asyncio.get_event_loop_policy().__class__.__name__ == "WindowsProactorEventLoopPolicy":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # 启动主程序（包含清理逻辑）
    try:
        async def main():
            try:
                await connect_napcat()
            finally:
                await cleanup()


        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 程序被用户终止")