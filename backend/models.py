from pydantic import BaseModel
from typing import Optional

# --- 1. 服务器模型 (包含 AC 字段) ---
class ServerSchema(BaseModel):
    server_id: str
    bmc_ip: str
    os_ip: Optional[str] = None
    ssh_user: str = "root"
    ssh_password: str = "1"
    
    status: str = "Idle"
    description: str = ""
    bmc_online: bool = False
    os_online: bool = False
    
    # --- Reboot 状态 ---
    reboot_status: str = "Idle"
    reboot_phase: str = "未部署"
    reboot_loop: str = "-"
    
    # --- Memtest 状态 ---
    memtest_status: str = "Idle"
    memtest_phase: str = "未部署"
    memtest_runtime_configured: str = "3600"

    # --- ✅ ACReboot 专属字段 ---
    ac_ip: str = ""          # AC 盒子 IP
    ac_socket: str = "1"     # AC 插座号
    ac_temp_ip: str = ""     # 临时 OS IP
    
    last_report_time: str = "-"

# --- 2. ✅ Webhook 模型 (补回这个类) ---
class WebhookSchema(BaseModel):
    server_id: str
    task_type: str = "reboot"  # 'reboot' 或 'memtest'
    status: str                # Running, Finished, Error
    phase: str                 # 当前阶段描述
    loop: str = "-"            # 当前轮次