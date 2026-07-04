import sys
import asyncio
import httpx
import logging
import ssl
import nonebot
import random
from nonebot import logger
from nonebot.adapters.onebot.v11 import Adapter, GroupMessageEvent, MessageSegment, Bot
from nonebot.matcher import Matcher
import scripts.patch_pw_import

scripts.patch_pw_import.patch()


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(Adapter)

# ===================== Kirara AI 配置项 =====================
KIRARA_API_URL = "http://localhost:8084/v1/chat"  # Kirara AI 的接口地址
# 可选：如果需要区分不同会话，可自定义 session_id 前缀
SESSION_ID_PREFIX = "nonebot-group-"
# 忽略的触发词（避免 AI 回复覆盖原有逻辑）
IGNORE_KEYWORDS = {
    "ping", "玩挺大", "人机", "入机", "/help", "/rd", "/roll", "/掷骰",
    "#识别", "#人物", "#角色", "/谁问我了", "/jm", "/幻影坦克", "/分离幻影坦克",
    "提取封面", "今日老婆", "jrlp", "每日老婆", "/表情包制作", "/24点",
    "/setu", "/涩图", "/色图", "/瑟图", "/搜图"
}

# ===================== 原有 SSL/HTTP 配置 =====================
# 创建自定义 SSL 上下文
ssl_context = ssl.create_default_context()
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')

# 创建禁用代理并配置 SSL 的 httpx 客户端
client = httpx.AsyncClient(verify=ssl_context, timeout=30.0)
driver._client = client
driver.config.httpx = {
    "verify": ssl_context,
    "timeout": 30.0,
    "http2": True
}

# ===================== 原有消息处理逻辑 =====================
ping = nonebot.on_message(priority=1, block=False)

# 加载插件
nonebot.load_from_toml("pyproject.toml")

@ping.handle()
async def handle_ping(matcher: Matcher, event: GroupMessageEvent, bot: Bot):
    plain_text = event.get_plaintext().strip()
    group_id = event.group_id
    user_id = event.user_id

    # 1. 原有 @ 检测逻辑（保留）
    if event.is_tome():
        if "的213吗" in plain_text or "的爱丽丝吗" in plain_text:
            image = MessageSegment.image(file=r"C:\Users\86139\Desktop\qqbot\auto213\pic\盒.jpg")
            await matcher.finish(image)
        if plain_text:
            if plain_text.startswith('/'):
                image = MessageSegment.image(file=r"C:\Users\86139\Desktop\qqbot\auto213\pic\人机.jpg")
                await matcher.finish(image)
            else:
                random_num = random.randint(1, 3)
                image_path = fr"C:\Users\86139\Desktop\qqbot\auto213\pic\我不知道{random_num}.jpg"
                image = MessageSegment.image(file=image_path)
                await matcher.finish(image)
        else:
            image = MessageSegment.image(file=r"C:\Users\86139\Desktop\qqbot\auto213\pic\爱丽丝在网上就是叠.jpg")
            await matcher.finish(image)

    # 2. 原有关键词触发逻辑（保留）
    # 简化关键词判断，避免重复代码
    trigger_conditions = [
        (plain_text == "ping", "Pong!"),
        (any(word in plain_text for word in ["怎么都", "怎么我", "谁干的"]), "我干的"),
        (any(word in plain_text for word in ["也干了", "我怎么", "被做局了"]), "我做的局"),
        (any(word in plain_text for word in ["shuiguole", "水过了", "水果了", "火星"]),
         MessageSegment.image(file=fr"C:\Users\86139\Desktop\qqbot\auto213\pic\火星{random.randint(1,5)}.jpg")),
        ("你怎么知道" in plain_text, MessageSegment.image(file=r"C:\Users\86139\Desktop\qqbot\auto213\pic\没人问你.jpg")),
        (any(word in plain_text for word in ["v50", "v我50", "V50", "V我50", "vivo50"]),
         MessageSegment.image(file=r"C:\Users\86139\Desktop\qqbot\auto213\pic\v50.jpg")),
        (plain_text == "玩挺大", MessageSegment.image(file=r"C:\Users\86139\Desktop\qqbot\auto213\pic\玩挺大.jpg")),
        (plain_text in ["人机", "入机"], MessageSegment.image(file=r"C:\Users\86139\Desktop\qqbot\auto213\pic\入机.jpg")),
        (plain_text == "/help",
         ('*掷骰子 投出x个y面骰子   \n-     /rd || /roll || /掷骰 [x]d[y] \n\n'
          '*查询动漫/galgame角色出处 \n-     #识别{动漫/gal} || #人物{动漫/gal}  || #角色{动漫/gal} [图片] \n\n'
          '*@记录  查询有谁@过你\n-     /谁问我了 \n\n'
          '*查询jm  自动下载jm(漫画太大会宕机)\n-     /jm[数字] \n\n' 
          '*幻影坦克   将两张图片合成幻影坦克，也可以分离拆解幻影坦克\n-     /幻影坦克 || /miragetank || /合成幻影坦克 [color/gray] [图片]\n-     /分离幻影坦克 [图片]\n'
          '*提取B站视频封面   用av号/链接/bv号提取封面\n-     提取封面 [链接/av号/bv号]\n\n'
          '*今日老婆  随机抓走一个群友当老婆\n-     今日老婆 || jrlp || 每日老婆\n\n'
          '*制作表情包  简易制作表情,有非常多子命令,输入/表情包制作 查看(新版手机QQ发图和转发不能触发！)\n-     /关键词 [图片]\n\n'
          '*玩24点  经典24点小游戏，输入/24点help获取详细帮助，连续模式有bug请不要启用\n-       /24点\n\n'
          '*随机涩图  随机发送一张涩图\n-    /setu || /涩图 || /色图 || /瑟图\n\n'
          '*搜图    搜索图片(新图和截图可能搜不出来！)\n      /搜图'))
    ]

    # 检查原有触发条件
    for condition, response in trigger_conditions:
        if condition and not any(seg.type != "text" for seg in event.message):
            await matcher.finish(response)
            return

    # 3. Kirara AI 对话逻辑（新增）
    # 过滤空消息、触发词消息、非文本消息
    if not plain_text:
        return
    if any(keyword in plain_text for keyword in IGNORE_KEYWORDS):
        return
    if any(seg.type != "text" for seg in event.message):
        return

    # 调用 Kirara AI 获取回复
    try:
        # 构造 Kirara AI 请求参数
        request_data = {
            "session_id": f"{SESSION_ID_PREFIX}{group_id}-{user_id}",  # 按群+用户区分会话
            "username": f"user_{user_id}",
            "message": plain_text
        }

        # 发送请求到 Kirara AI
        response = await client.post(
            KIRARA_API_URL,
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        result = response.json()

        # 处理 Kirara AI 响应
        if result.get("result") == "SUCCESS" and result.get("message"):
            # 拼接多段回复（Kirara 可能返回数组）
            ai_reply = "".join(result["message"])
            if ai_reply:
                await matcher.finish(ai_reply)
        else:
            logger.warning(f"Kirara AI 响应失败: {result}")
            # 降级回复（可选）
            await matcher.finish("我好像出了点小问题，暂时无法回复～")

    except httpx.ConnectError:
        logger.error(f"无法连接到 Kirara AI: {KIRARA_API_URL}")
        await matcher.finish("AI 服务未启动，暂时无法回复～")
    except httpx.HTTPStatusError as e:
        logger.error(f"Kirara AI HTTP 错误: {e.response.status_code} - {e.response.text}")
        await matcher.finish("AI 服务出错了，暂时无法回复～")
    except Exception as e:
        logger.error(f"Kirara AI 调用异常: {str(e)}", exc_info=True)
        # 不阻断其他插件，仅记录错误
        return

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        nonebot.run()
    except httpx.ConnectError as e:
        logger.error(f"启动时连接错误: {e}")
    except Exception as e:
        logger.error(f"启动时未知错误: {e}", exc_info=True)