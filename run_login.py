import asyncio
import sys
from login_helper import run_login_flow

if __name__ == "__main__":
    if any(arg in sys.argv for arg in ["--wipe", "-w"]):
        from login_helper import wipe_all_credentials
        res = wipe_all_credentials()
        print("✅ 个人登录凭据与会话缓存已彻底销毁清除:", res)
        sys.exit(0)

    clear = any(arg in sys.argv for arg in ["--switch", "--clear", "-s", "-c"])
    asyncio.run(run_login_flow(clear_session_first=clear))
