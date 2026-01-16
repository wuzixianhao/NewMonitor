import os
import shutil
import re
from config import *
from utils import get_ssh_client, run_ssh_command, convert_to_unix_format
from models import ServerSchema
from logger import logger

# --- 辅助工具 ---
SOCKET_MAP = {
    "1": "1000", "2": "0100", "3": "0010", "4": "0001"
}

def get_socket_code(num: str):
    if len(num) == 4 and all(c in '01' for c in num): return num
    return SOCKET_MAP.get(str(num), "0000")

# --- 1. 检查连通性 ---
def check_ac_connectivity(server: ServerSchema):
    if not server.ac_ip: return False, "未配置 AC 盒子 IP"
    
    logger.info(f"[{server.server_id}] [AC] 检查连通性: OS->{server.ac_ip}")
    ssh = get_ssh_client(server.os_ip, server.ssh_user, server.ssh_password)
    try:
        if server.ac_temp_ip:
            # 尝试配置 IP，不报错
            cmd_set_ip = f"""
                NIC=$(ip -o -4 route show to default | awk '{{print $5}}' | head -1)
                [ -z "$NIC" ] && NIC=$(ls /sys/class/net/ | grep -v lo | head -1)
                ip addr add {server.ac_temp_ip}/24 dev $NIC >/dev/null 2>&1 || true
            """
            ssh.exec_command(cmd_set_ip)

        stdin, stdout, stderr = ssh.exec_command(f"ping -c 3 -W 1 {server.ac_ip}")
        if stdout.channel.recv_exit_status() == 0:
            return True, "连通性检查通过"
        else:
            return False, f"OS 无法 Ping 通 AC ({server.ac_ip})"
    finally:
        ssh.close()

# --- 2. 部署逻辑 (SFTP 版 - 解决 Code -1 问题) ---
def deploy_ac_script(server: ServerSchema):
    can_ping, msg = check_ac_connectivity(server)
    if not can_ping: return False, msg

    try:
        logger.info(f"[{server.server_id}] [AC] 部署脚本 V2.2.2 (SFTP模式)...")
        
        # 1. 本地准备
        if os.path.exists(TEMP_SCRIPT_DIR): shutil.rmtree(TEMP_SCRIPT_DIR)
        os.makedirs(TEMP_SCRIPT_DIR)

        # A. 准备 Monitor
        monitor_path = os.path.join(LOCAL_SCRIPT_DIR, SCRIPT_MONITOR_NAME)
        backend_url = f"http://{BACKEND_IP_PORT}/report/webhook"
        with open(monitor_path, 'r', encoding='utf-8') as f:
            mon_content = f.read().replace("{{BACKEND_URL}}", backend_url).replace("{{SERVER_ID}}", server.server_id)
        with open(os.path.join(TEMP_SCRIPT_DIR, SCRIPT_MONITOR_NAME), 'w', encoding='utf-8', newline='\n') as f:
            f.write(convert_to_unix_format(mon_content))

        # B. 准备 AC Cycle 脚本
        script_path = os.path.join(LOCAL_SCRIPT_DIR, SCRIPT_AC_NAME)
        with open(script_path, 'r', encoding='utf-8') as f:
            cycle_content = f.read()
        
        # 注入参数
        cycle_content = re.sub(r'box_ip=".*?"', f'box_ip="{server.ac_ip}"', cycle_content)
        s_code = get_socket_code(server.ac_socket)
        cycle_content = re.sub(r'box_socket=".*?"', f'box_socket="{s_code}"', cycle_content)
        
        with open(os.path.join(TEMP_SCRIPT_DIR, SCRIPT_AC_NAME), 'w', encoding='utf-8', newline='\n') as f:
            f.write(convert_to_unix_format(cycle_content))

        # C. 准备 rc.local
        rc_content = r"""#!/bin/bash
# THIS FILE IS ADDED FOR COMPATIBILITY PURPOSES
touch /var/lock/subsys/local
exit 0
"""
        with open(os.path.join(TEMP_SCRIPT_DIR, "rc.local"), 'w', encoding='utf-8', newline='\n') as f:
            f.write(convert_to_unix_format(rc_content))

        # 3. SSH 操作 (分步执行清理，避免 Code -1)
        ssh = get_ssh_client(server.os_ip, server.ssh_user, server.ssh_password)
        
        try:
            # 简单清理，不含复杂逻辑
            ssh.exec_command(f"pkill -f '{SCRIPT_MONITOR_NAME}'")
            ssh.exec_command(f"pkill -f '{SCRIPT_AC_NAME}'")
            ssh.exec_command(f"pkill -f 'Cycle_OSReboot_V2.2.3.sh'") # 防止冲突
            
            ssh.exec_command(f"mkdir -p {REMOTE_AC_DIR}")
            ssh.exec_command("mkdir -p /root/Test_Logs/ACReboot")
            ssh.exec_command(f"rm -f {REMOTE_AC_DIR}/.is_reboot_running")
            
            # Trash 归档
            ssh.exec_command(f"mkdir -p {REMOTE_AC_DIR}/Trash")
            ssh.exec_command(f"cd {REMOTE_AC_DIR} && mv *.sh *.log *.out Trash/ >/dev/null 2>&1")
        except:
            pass # 忽略清理错误

        # 4. SFTP 上传
        sftp = ssh.open_sftp()
        sftp.put(os.path.join(TEMP_SCRIPT_DIR, SCRIPT_AC_NAME), f"{REMOTE_AC_DIR}/{SCRIPT_AC_NAME}")
        sftp.put(os.path.join(TEMP_SCRIPT_DIR, SCRIPT_MONITOR_NAME), f"{REMOTE_AC_DIR}/{SCRIPT_MONITOR_NAME}")
        sftp.put(os.path.join(TEMP_SCRIPT_DIR, "rc.local"), "/etc/rc.d/rc.local")
        sftp.close()
        
        # 5. 赋权
        ssh.exec_command(f"chmod +x {REMOTE_AC_DIR}/*.sh")
        ssh.exec_command("chmod +x /etc/rc.d/rc.local")
        
        ssh.close()
        shutil.rmtree(TEMP_SCRIPT_DIR)
        
        return True, f"部署成功 (SFTP模式)"
        
    except Exception as e:
        logger.exception(f"[{server.server_id}] AC 部署异常")
        return False, f"部署异常: {str(e)}"

# --- 3. 启动逻辑 (恢复 Reboot 的严谨逻辑：dos2unix, setsid, PID检查) ---
def start_ac_test(server: ServerSchema):
    logger.info(f"[{server.server_id}] [AC] 启动测试...")
    loops = "201"
    
    start_cmd = f"""
        cd {REMOTE_AC_DIR} || exit 1
        
        # 1. 代理清理
        export http_proxy=""
        export https_proxy=""
        
        # 2. 格式修复 (Reboot 同款)
        if command -v dos2unix >/dev/null 2>&1; then dos2unix -q *.sh; fi
        chmod +x *.sh
        
        # 3. 创建锁文件
        touch .is_reboot_running
        
        # 4. 启动监控 (使用 setsid)
        setsid nohup bash {SCRIPT_MONITOR_NAME} > monitor.out 2>&1 < /dev/null &
        
        sleep 2
        
        # 5. 启动主脚本 (AC 模式: -ma)
        # ⚠️ 这里和 Reboot 不同：Reboot 由 Monitor 拉起 Chain，AC 直接在这里拉起 Cycle
        setsid nohup bash {SCRIPT_AC_NAME} -ma -i {loops} > chain.log 2>&1 < /dev/null &
        
        # 6. PID 检查 (Reboot 同款验证逻辑)
        sleep 1
        PID_MON=$(pgrep -f "{SCRIPT_MONITOR_NAME}")
        PID_CYC=$(pgrep -f "{SCRIPT_AC_NAME}")
        
        if [ -n "$PID_MON" ] && [ -n "$PID_CYC" ]; then
            echo "SUCCESS: ACReboot Started (Monitor:$PID_MON, Cycle:$PID_CYC)"
        else
            echo "FAILED: Start failed. Monitor:$PID_MON, Cycle:$PID_CYC"
        fi
    """
    return run_ssh_command(server.os_ip, server.ssh_user, server.ssh_password, start_cmd)

# --- 4. 停止逻辑 (恢复 Reboot 的严谨逻辑：Quit信号, Safe Kill, 归档) ---
def stop_ac_test(server: ServerSchema):
    logger.info(f"[{server.server_id}] [AC] 停止测试...")
    
    stop_cmd = f"""
        cd {REMOTE_AC_DIR} || exit 0
        
        # 1. 移除锁
        rm -f .is_reboot_running
        
        # 2. 优雅停止 (发送 -q 信号)
        if [ -f "{SCRIPT_AC_NAME}" ]; then 
            bash {SCRIPT_AC_NAME} -q || true
        fi
        
        # 3. 强杀进程 (Safe Kill)
        safe_kill() {{
            pgrep -f "$1" | grep -v grep | xargs -r kill -9 2>/dev/null || true
        }}
        safe_kill "{SCRIPT_MONITOR_NAME}"
        safe_kill "{SCRIPT_AC_NAME}"
        
        # 4. 恢复 rc.local (简单的 Echo 覆盖，避免上传依赖)
        echo '#!/bin/bash' > /etc/rc.d/rc.local
        echo 'touch /var/lock/subsys/local' >> /etc/rc.d/rc.local
        echo 'exit 0' >> /etc/rc.d/rc.local
        chmod +x /etc/rc.d/rc.local
        
        # 5. 归档日志
        LOG_DIR="/root/Test_Logs"
        if [ -d "$LOG_DIR" ]; then
            TIME_TAG=$(date +%Y%m%d_%H%M%S)
            TAR_NAME="acreboot_logs_$TIME_TAG.tar.gz"
            tar -czvf $TAR_NAME -C /root/Test_Logs . >/dev/null 2>&1
            echo "SUCCESS: Archived to $TAR_NAME"
        else
            echo "SUCCESS: Stopped (No logs)"
        fi
    """
    return run_ssh_command(server.os_ip, server.ssh_user, server.ssh_password, stop_cmd)

# --- 5. 重置逻辑 ---
def reset_ac_files(server: ServerSchema):
    logger.info(f"[{server.server_id}] 重置 ACReboot 环境...")
    
    reset_cmd = f"""
        cd {REMOTE_AC_DIR} || exit 0
        
        rm -f .is_reboot_running
        pkill -f "{SCRIPT_AC_NAME}"
        pkill -f "{SCRIPT_MONITOR_NAME}"
        
        echo '#!/bin/bash' > /etc/rc.d/rc.local
        echo 'touch /var/lock/subsys/local' >> /etc/rc.d/rc.local
        echo 'exit 0' >> /etc/rc.d/rc.local
        chmod +x /etc/rc.d/rc.local
        
        rm -rf /root/Test_Logs/ACReboot
        
        mkdir -p Trash
        find . -maxdepth 1 -type f -not -name "*.sh" -exec mv {{}} Trash/ \\;
        
        echo "SUCCESS: Reset Done"
    """
    return run_ssh_command(server.os_ip, server.ssh_user, server.ssh_password, reset_cmd)