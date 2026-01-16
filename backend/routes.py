from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import FileResponse
import os
from typing import List

# ✅ 引入新的 Redis DB 对象
from database import db
from models import ServerSchema, WebhookSchema
from utils import ping_ip

# 引入业务服务
from services import reboot as service_reboot
from services import memtest as service_memtest
from services import meminfo as service_meminfo
from services import acreboot as service_ac

router = APIRouter()

# --- 1. 监控刷新接口 (逻辑大改) ---
@router.post("/monitor/refresh")
def refresh_status():
    # 1. 从 Redis 拉取最新全量数据
    servers_dict = db.get_all_servers()
    results = []
    
    for s_id, server in servers_dict.items():
        old_os = server.os_online
        
        # 执行 Ping
        server.bmc_online = ping_ip(server.bmc_ip)
        current_os_online = ping_ip(server.os_ip) if server.os_ip else False
        
        # 状态判定逻辑
        if current_os_online:
            server.os_online = True
        else:
            if server.reboot_status == "Running":
                server.os_online = False 
            else:
                server.os_online = False

        # ✅ 关键：每次状态变化，必须立即写回 Redis！
        # 以前是最后统一 save_db()，现在我们每台机器处理完都更新一下（Redis很快）
        # 或者你可以比较 has_changed 再更新，但直接 upsert 更稳
        db.upsert_server(server)
        
        results.append(server)
    
    return {"results": [s.model_dump() for s in results]}

# --- 2. Webhook 回调 ---
@router.post("/report/webhook")
def receive_report(data: WebhookSchema):
    # 从 Redis 获取
    srv = db.get_server(data.server_id)
    if not srv:
        return {"status": "ignored"}

    import datetime
    now_str = datetime.datetime.now().strftime("%H:%M:%S")

    if data.task_type == "memtest":
        srv.memtest_status = data.status
        srv.memtest_phase = data.phase
    else:
        srv.reboot_status = data.status
        srv.reboot_phase = data.phase
        srv.reboot_loop = data.loop

    srv.last_report_time = now_str
    
    # ✅ 写回 Redis
    db.upsert_server(srv)
    return {"status": "ok"}

# --- 3. Reboot 相关接口 ---
@router.post("/servers/{server_id}/deploy")
def reboot_deploy(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404, "Server not found")
    
    success, msg = service_reboot.deploy_reboot_scripts(srv)
    if success:
        srv.reboot_status = "Deployed"
        srv.reboot_phase = "已部署"
        db.upsert_server(srv) # ✅ 保存状态
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/start_test")
async def reboot_start(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    success, msg = await service_reboot.start_reboot_test(srv)
    if success:
        srv.reboot_status = "Running"
        srv.reboot_phase = "正在启动..."
        db.upsert_server(srv) # ✅ 保存状态
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/stop_test")
async def reboot_stop(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    success, msg = await service_reboot.stop_reboot_test(srv)
    if success:
        srv.reboot_status = "Stopped"
        srv.reboot_phase = "用户已停止"
        db.upsert_server(srv) # ✅ 保存状态
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/reset_files")
async def reboot_reset(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    success, msg = await service_reboot.reset_reboot_files(srv)
    if success:
        srv.reboot_status = "Idle"
        srv.reboot_phase = "环境已重置"
        srv.reboot_loop = "-"
        db.upsert_server(srv) # ✅ 保存状态
    return {"success": success, "message": msg}

# --- 4. Memtest 相关接口 ---
@router.post("/servers/{server_id}/memtest/deploy")
def memtest_deploy(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    success, msg = service_memtest.deploy_memtest_env(srv)
    if success:
        srv.memtest_status = "Deployed"
        srv.memtest_phase = "环境就绪"
        db.upsert_server(srv) # ✅ 保存状态
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/memtest/start")
def memtest_start(server_id: str, payload: dict = Body(...)):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    runtime = payload.get("runtime", "3600")
    
    success, msg = service_memtest.start_memtest(srv, str(runtime))
    if success:
        srv.memtest_status = "Running"
        srv.memtest_phase = f"启动指令已发 (限时{runtime}s)"
        srv.memtest_runtime_configured = str(runtime)
        db.upsert_server(srv) # ✅ 保存状态
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/memtest/archive")
def memtest_archive(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    success, msg = service_memtest.archive_memtest(srv)
    if success:
        srv.memtest_status = "Finished"
        srv.memtest_phase = "已归档"
        db.upsert_server(srv) # ✅ 保存状态
    return {"success": success, "message": msg}

# --- 5. MemInfo 相关接口 ---
@router.post("/servers/{server_id}/meminfo/deploy")
def meminfo_deploy(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    success, msg = service_meminfo.deploy_meminfo(srv)
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/meminfo/run")
async def meminfo_run(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    success, msg = await service_meminfo.run_meminfo(srv)
    return {"success": success, "message": msg}

@router.get("/servers/{server_id}/meminfo/download")
async def meminfo_download(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    success, msg, path = await service_meminfo.download_meminfo_result(srv)
    
    if success and path and os.path.exists(path):
        return FileResponse(path=path, filename=os.path.basename(path), media_type='text/plain')
    return {"success": False, "message": msg or "文件不存在"}


# ================= AC REBOOT 路由 =================

@router.post("/servers/{server_id}/acreboot/save_config")
def acreboot_save_config(server_id: str, payload: dict = Body(...)):
    """保存 AC 配置 (IP, Socket, TempIP)"""
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    srv.ac_ip = payload.get("ac_ip", "")
    srv.ac_socket = payload.get("ac_socket", "1")
    srv.ac_temp_ip = payload.get("ac_temp_ip", "")
    
    db.upsert_server(srv)
    return {"success": True, "message": "AC 配置已保存"}

@router.post("/servers/{server_id}/acreboot/deploy")
def acreboot_deploy(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    # 检查配置
    if not srv.ac_ip:
        return {"success": False, "message": "请先配置 AC 盒子 IP"}
        
    success, msg = service_ac.deploy_ac_script(srv)
    if success:
        srv.reboot_status = "Deployed" # 复用 reboot_status 字段，因为也是一种 Reboot
        srv.reboot_phase = "AC 脚本已部署"
        db.upsert_server(srv)
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/acreboot/start")
def acreboot_start(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    success, msg = service_ac.start_ac_test(srv)
    if success:
        srv.reboot_status = "Running"
        srv.reboot_phase = "AC压测进行中..."
        db.upsert_server(srv)
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/acreboot/stop")
def acreboot_stop(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    # 调用 service_ac 里的停止逻辑
    success, msg = service_ac.stop_ac_test(srv)
    
    if success:
        srv.reboot_status = "Stopped"
        srv.reboot_phase = "AC压测已停止"
        db.upsert_server(srv)
    return {"success": success, "message": msg}

# --- 6. 服务器管理 ---
@router.post("/servers/add")
def add_server(server: ServerSchema):
    # ✅ 写入 Redis
    db.upsert_server(server)
    return {"success": True, "message": "添加成功"}

@router.delete("/servers/delete/{server_id}")
def delete_server(server_id: str):
    # ✅ 从 Redis 删除
    if db.get_server(server_id):
        db.delete_server(server_id)
        return {"success": True, "status": "success"}
    raise HTTPException(404, "Server not found")