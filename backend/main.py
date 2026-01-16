import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 1. 关键：从 routes.py 导入 router
# 如果这行报错，说明你的 routes.py 文件名不对，或者不在同一个文件夹下
from routes import router as api_router

app = FastAPI(title="自动化测试监控平台 API", version="3.0")

# 2. 配置跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 核心：挂载路由！
# 这一行如果不写，所有的接口都会报 404
app.include_router(api_router)

# 👇👇👇 必须加上这一段！没有它，脚本就是哑巴 👇👇👇
if __name__ == "__main__":
    print("------------------------------------------------")
    print("✅ 正在启动后端服务...")
    print("🔍 已加载的接口路由:")
    # 打印出所有注册的路由，让你眼见为实
    for route in app.routes:
        print(f"   - {route.path}")
    print("------------------------------------------------")
    
    import uvicorn
    # 启动服务！
    uvicorn.run(app, host="0.0.0.0", port=8000)