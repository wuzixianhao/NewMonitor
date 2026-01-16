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

# --- 1. 监控刷新接口 (核心修复版) ---
@router.post("/monitor/refresh")
def refresh_status():
    """
    修复说明：
    之前版本在 Ping 耗时期间持有旧的 Server 对象，Ping 完后强行覆盖写入，
    导致 Ping 期间 Webhook 汇报的状态（如 Loop 数、Phase 变化）被回滚。
    
    现在改为：
    1. 拿快照 -> 2. Ping (耗时) -> 3. 重新 fetch 最新对象 -> 4. 更新 Ping 结果 -> 5. 写入
    """
    # 1. 获取所有服务器的快照 (仅用于获取 IP 列表)
    servers_snapshot = db.get_all_servers()
    results = []
    
    # 2. 执行 Ping 操作 (耗时操作，此时不锁库，允许 Webhook 并发写入)
    ping_results = {}
    for s_id, server in servers_snapshot.items():
        bmc_alive = ping_ip(server.bmc_ip)
        # 如果配置了 OS IP 才 ping，否则默认为 False
        os_alive = ping_ip(server.os_ip) if server.os_ip else False
        ping_results[s_id] = (bmc_alive, os_alive)
    
    # 3. 【关键步骤】Ping 结束后，逐个获取最新的 Server 对象进行更新
    for s_id, (bmc_alive, os_alive) in ping_results.items():
        latest_server = db.get_server(s_id)
        if not latest_server: 
            continue # 防止 Ping 期间服务器被删了
        
        # 4. 只更新 Ping 相关的字段
        latest_server.bmc_online = bmc_alive
        
        # OS 在线状态判断逻辑
        if os_alive:
            latest_server.os_online = True
        else:
            # Ping 不通，直接置为 False
            # (前端会根据 reboot_status='Running' && os_online=False 显示为'重启中')
            latest_server.os_online = False

        # 5. 写入数据库 (此时覆盖风险极低，因为从 get 到 upsert 只有极短时间)
        db.upsert_server(latest_server)
        results.append(latest_server)
    
    return {"results": [s.model_dump() for s in results]}

# --- 2. Webhook 回调 ---
@router.post("/report/webhook")
def receive_report(data: WebhookSchema):
    # 从 Redis 获取最新对象
    srv = db.get_server(data.server_id)
    if not srv:
        return {"status": "ignored"}

    import datetime
    now_str = datetime.datetime.now().strftime("%H:%M:%S")

    # 根据任务类型更新字段
    if data.task_type == "memtest":
        srv.memtest_status = data.status
        srv.memtest_phase = data.phase
    else:
        # Reboot 任务
        srv.reboot_status = data.status
        srv.reboot_phase = data.phase
        srv.reboot_loop = data.loop

    srv.last_report_time = now_str
    
    # ✅ 写回 Redis
    db.upsert_server(srv)
    return {"status": "ok"}

# --- 3. Reboot 相关接口 (修复并发覆盖问题) ---
@router.post("/servers/{server_id}/deploy")
def reboot_deploy(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404, "Server not found")
    
    # 耗时操作
    success, msg = service_reboot.deploy_reboot_scripts(srv)
    
    # 重新获取最新状态，防止覆盖
    if success:
        srv_latest = db.get_server(server_id)
        if srv_latest:
            srv_latest.reboot_status = "Deployed"
            srv_latest.reboot_phase = "已部署"
            db.upsert_server(srv_latest)
            
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/start_test")
async def reboot_start(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    # 耗时操作 (SSH 连接)
    success, msg = await service_reboot.start_reboot_test(srv)
    
    # 重新获取最新状态
    if success:
        srv_latest = db.get_server(server_id)
        if srv_latest:
            srv_latest.reboot_status = "Running"
            srv_latest.reboot_phase = "正在启动..."
            db.upsert_server(srv_latest)
            
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/stop_test")
async def reboot_stop(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    # 耗时操作
    success, msg = await service_reboot.stop_reboot_test(srv)
    
    # 重新获取最新状态
    if success:
        srv_latest = db.get_server(server_id)
        if srv_latest:
            srv_latest.reboot_status = "Stopped"
            srv_latest.reboot_phase = "用户已停止"
            db.upsert_server(srv_latest)
            
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/reset_files")
async def reboot_reset(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    # 耗时操作
    success, msg = await service_reboot.reset_reboot_files(srv)
    
    # 重新获取最新状态
    if success:
        srv_latest = db.get_server(server_id)
        if srv_latest:
            srv_latest.reboot_status = "Idle"
            srv_latest.reboot_phase = "环境已重置"
            srv_latest.reboot_loop = "-"
            db.upsert_server(srv_latest)
            
    return {"success": success, "message": msg}

# --- 4. Memtest 相关接口 (同样加固) ---
@router.post("/servers/{server_id}/memtest/deploy")
def memtest_deploy(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    success, msg = service_memtest.deploy_memtest_env(srv)
    
    if success:
        srv_latest = db.get_server(server_id)
        if srv_latest:
            srv_latest.memtest_status = "Deployed"
            srv_latest.memtest_phase = "环境就绪"
            db.upsert_server(srv_latest)
            
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/memtest/start")
def memtest_start(server_id: str, payload: dict = Body(...)):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    runtime = payload.get("runtime", "3600")
    
    success, msg = service_memtest.start_memtest(srv, str(runtime))
    
    if success:
        srv_latest = db.get_server(server_id)
        if srv_latest:
            srv_latest.memtest_status = "Running"
            srv_latest.memtest_phase = f"启动指令已发 (限时{runtime}s)"
            srv_latest.memtest_runtime_configured = str(runtime)
            db.upsert_server(srv_latest)
            
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/memtest/archive")
def memtest_archive(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    success, msg = service_memtest.archive_memtest(srv)
    
    if success:
        srv_latest = db.get_server(server_id)
        if srv_latest:
            srv_latest.memtest_status = "Finished"
            srv_latest.memtest_phase = "已归档"
            db.upsert_server(srv_latest)
            
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
    
    if not srv.ac_ip:
        return {"success": False, "message": "请先配置 AC 盒子 IP"}
        
    success, msg = service_ac.deploy_ac_script(srv)
    
    if success:
        srv_latest = db.get_server(server_id)
        if srv_latest:
            srv_latest.reboot_status = "Deployed" 
            srv_latest.reboot_phase = "AC 脚本已部署"
            db.upsert_server(srv_latest)
            
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/acreboot/start")
def acreboot_start(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    success, msg = service_ac.start_ac_test(srv)
    
    if success:
        srv_latest = db.get_server(server_id)
        if srv_latest:
            srv_latest.reboot_status = "Running"
            srv_latest.reboot_phase = "AC压测进行中..."
            db.upsert_server(srv_latest)
            
    return {"success": success, "message": msg}

@router.post("/servers/{server_id}/acreboot/stop")
def acreboot_stop(server_id: str):
    srv = db.get_server(server_id)
    if not srv: raise HTTPException(404)
    
    success, msg = service_ac.stop_ac_test(srv)
    
    if success:
        srv_latest = db.get_server(server_id)
        if srv_latest:
            srv_latest.reboot_status = "Stopped"
            srv_latest.reboot_phase = "AC压测已停止"
            db.upsert_server(srv_latest)
            
    return {"success": success, "message": msg}

# --- 6. 服务器管理 ---
@router.post("/servers/add")
def add_server(server: ServerSchema):
    # 添加时不需要担心并发，直接写入
    db.upsert_server(server)
    return {"success": True, "message": "添加成功"}

@router.delete("/servers/delete/{server_id}")
def delete_server(server_id: str):
    if db.get_server(server_id):
        db.delete_server(server_id)
        return {"success": True, "status": "success"}
    raise HTTPException(404, "Server not found")