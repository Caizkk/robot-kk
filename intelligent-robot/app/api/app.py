from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

# 导入模型
from app.domains.common_models import HealthResponse, CommonResponse, StatusCode
from typing import Dict, Any

# 导入控制器
from app.api.controllers.process_controller import router as process_router

app = FastAPI(title="智能机器人API", description="智能机器人系统API接口", version="0.1.0")

# 允许渲染进程通过 file:// 或本地 http 页面访问 API
# 在 Electron 生产环境中，前端以 file 协议加载，浏览器会发送 Origin: null
# 这里使用通配解决 CORS，并且不使用凭据
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由器
app.include_router(process_router, prefix="/api/v1")

@app.get("/", response_model=CommonResponse[Dict[str, Any]])
async def root():
    return CommonResponse[Dict[str, Any]](
        code=StatusCode.SUCCESS,
        message="服务运行正常",
        data={"message": "智能机器人API服务"}
    )

@app.get("/health", response_model=CommonResponse[HealthResponse])
async def health_check():
    return CommonResponse[HealthResponse](
        code=StatusCode.SUCCESS,
        message="服务运行正常",
        data=HealthResponse(status="healthy", version="0.1.0")
    )


