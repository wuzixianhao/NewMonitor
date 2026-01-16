import os
from config import *
from utils import get_ssh_client, run_ssh_command
from models import ServerSchema
from logger import logger

# --- 1. 部署逻辑 (保持不变) ---
def deploy_memtest_env(server: ServerSchema):
    try:
        logger.info(f"[{server.server_id}] 开始部署 Memtest 环境...")
        script_src = os.path.join(LOCAL_SCRIPT_DIR, SCRIPT_MEMTEST_NAME)
        tar_src = os.path.join(LOCAL_SCRIPT_DIR, FILE_MEMTEST_TAR)
        
        if not os.path.exists(script_src) or not os.path.exists(tar_src):
            return False, "本地 Memtest 文件缺失"

        ssh = get_ssh_client(server.os_ip, server.ssh_user, server.ssh_password)
        
        # 预处理
        setup_cmd = f"""
            rm -rf {REMOTE_MEMTEST_DIR}
            mkdir -p {REMOTE_MEMTEST_DIR}
            mkdir -p /root/Test_Logs/Memtest
            # 安装依赖
            if ! command -v bc >/dev/null 2>&1; then yum install -y bc; fi
            if ! command -v dos2unix >/dev/null 2>&1; then yum install -y dos2unix; fi
            dmesg -c >/dev/null
        """
        ssh.exec_command(setup_cmd)
        
        sftp = ssh.open_sftp()
        sftp.put(script_src, f"{REMOTE_MEMTEST_DIR}/{SCRIPT_MEMTEST_NAME}")
        sftp.put(tar_src, f"{REMOTE_MEMTEST_DIR}/{FILE_MEMTEST_TAR}")
        sftp.close()

        cmd_install = f"""
            cd {REMOTE_MEMTEST_DIR} || exit 1
            if command -v dos2unix >/dev/null 2>&1; then dos2unix -q *.sh; fi
            tar -zxvf {FILE_MEMTEST_TAR}
            DIR_NAME=$(tar -tf {FILE_MEMTEST_TAR} | head -1 | cut -f1 -d"/")
            if [ -d "$DIR_NAME" ]; then
                cd "$DIR_NAME"
                if [ ! -f "memtester" ]; then make && make install; fi
                cd ..
            fi
            chmod +x {SCRIPT_MEMTEST_NAME}
        """
        stdin, stdout, stderr = ssh.exec_command(cmd_install)
        if stdout.channel.recv_exit_status() != 0:
            ssh.close()
            return False, f"编译失败: {stderr.read().decode()}"
            
        ssh.close()
        return True, "Memtest 环境部署成功"
    except Exception as e:
        return False, f"部署异常: {str(e)}"

# --- 2. 启动逻辑 (完美模拟用户打开终端) ---
def start_memtest(server: ServerSchema, runtime: str):
    logger.info(f"[{server.server_id}] 启动 Memtest (Runtime={runtime})")

    # 1. 杀掉旧进程
    kill_old_cmd = f"""
        safe_kill() {{
            local name=$1
            PIDS=$(pgrep -f "$name" | grep -v "$$" | grep -v "grep")
            if [ -n "$PIDS" ]; then echo "$PIDS" | xargs -r kill -9; fi
        }}
        safe_kill "memtest_daemon.sh"
        safe_kill "{SCRIPT_MEMTEST_NAME}"
        killall -9 memtester 2>/dev/null || true
    """
    run_ssh_command(server.os_ip, server.ssh_user, server.ssh_password, kill_old_cmd)

    # 2. 生成监控脚本
    monitor_script = f"""#!/bin/bash
SERVER_ID="{server.server_id}"
URL="http://{BACKEND_IP_PORT}/report/webhook"

LOG_DIR="/root/Test_Logs/Memtest"
mkdir -p "$LOG_DIR"
LOCAL_LOG="$LOG_DIR/memtest_detail.log"

rotate_log() {{
    local max_size=$((5 * 1024 * 1024))
    if [ -f "$LOCAL_LOG" ]; then
        local size=$(stat -c%s "$LOCAL_LOG")
        if [ $size -ge $max_size ]; then
            mv "$LOCAL_LOG" "$LOCAL_LOG.$(date +%Y%m%d_%H%M%S).bak"
            ls -t "$LOG_DIR"/*.bak | tail -n +4 | xargs -r rm
        fi
    fi
}}

log_to_local() {{
    local msg=$1
    local time_now=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$time_now] $msg" >> "$LOCAL_LOG"
    rotate_log
}}

report_backend() {{
    local status=$1
    local msg=$2
    JSON_DATA="{{\\"server_id\\": \\"$SERVER_ID\\", \\"task_type\\": \\"memtest\\", \\"phase\\": \\"$msg\\", \\"status\\": \\"$status\\"}}"
    curl --noproxy "*" -s -X POST "$URL" -H "Content-Type: application/json" -d "$JSON_DATA" >/dev/null 2>&1
}}

log_to_local "Daemon Started. Waiting 15s..."
sleep 15

while true; do
    RAW_PIDS=$(pgrep -f "memtester")
    VALID_PIDS=$(echo "$RAW_PIDS" | xargs -r ps -fp 2>/dev/null | grep -v "grep" | grep -v "memtest_daemon" | grep -v "bash -c" | grep -v "PID" | awk '{{print $2}}')
    COUNT=$(echo "$VALID_PIDS" | wc -w)

    if [ -n "$VALID_PIDS" ]; then
        MSG="压测中 ($COUNT 个核心运行中)"
        log_to_local "$MSG"
        report_backend "Running" "$MSG"
    else
        MSG="压测已结束"
        log_to_local "$MSG. Stopping Daemon."
        report_backend "Finished" "$MSG"
        exit 0
    fi
    sleep 30
done
"""
    
    # 3. 启动命令
    cmd = f"""
        cd {REMOTE_MEMTEST_DIR} || exit 1
        
        # 写入监控脚本
        cat > memtest_daemon.sh << 'EOF_MON'
{monitor_script}
EOF_MON
        
        if command -v dos2unix >/dev/null 2>&1; then dos2unix -q *.sh; fi
        chmod +x memtest_daemon.sh
        
        # 1. 替换 runtime (这一步必须做)
        sed -i 's/^runtime=[0-9]*/runtime={runtime}/' {SCRIPT_MEMTEST_NAME}
        
        # ⚠️ 注意：这里删除了 sed 替换 read -> sleep 的代码
        # 我们希望保留 read 命令，以便在终端中显示 prompt
        
        export DISPLAY=:0
        
        # 打开系统监控 (后台静默)
        nohup gnome-terminal --title="System Monitor" -- gnome-system-monitor >/dev/null 2>&1 < /dev/null &
        
        sleep 2
        
        # 🔥🔥🔥 核心：打开真正的执行窗口 🔥🔥🔥
        # 1. --title: 设置窗口标题
        # 2. --geometry: 设置窗口大小 (100列 x 30行)
        # 3. bash -c "..." 内部：
        #    ./script.sh  -> 执行脚本，此时 read 会从该窗口读取输入，不会自杀
        #    exec bash    -> 关键！脚本执行完(或被中断)后，保持窗口不关闭，变成一个 Shell
        nohup gnome-terminal --working-directory="{REMOTE_MEMTEST_DIR}" --title="Memtest Execution" --geometry=100x30 -- bash -c "./{SCRIPT_MEMTEST_NAME}; echo '===================='; echo 'Script Process Ended.'; exec bash" >/dev/null 2>&1 &
        
        # 启动后台上报 Daemon
        nohup ./memtest_daemon.sh >/dev/null 2>&1 < /dev/null &
        
        echo "SUCCESS: Memtest Launched in Terminal"
    """
    return run_ssh_command(server.os_ip, server.ssh_user, server.ssh_password, cmd)

# --- 3. 停止与归档 ---
def stop_memtest(server: ServerSchema):
    logger.info(f"[{server.server_id}] 停止 Memtest 并归档...")
    
    stop_cmd = f"""
        kill_target() {{ pgrep -f "$1" | grep -v grep | grep -v python | xargs -r kill -9 2>/dev/null || true; }}
        kill_target "memtest_daemon.sh"
        kill_target "{SCRIPT_MEMTEST_NAME}"
        killall -9 memtester 2>/dev/null || true
        pkill -f "bash -c .*memtester" || true
    """
    run_ssh_command(server.os_ip, server.ssh_user, server.ssh_password, stop_cmd)

    archive_cmd = f"""
        cd {REMOTE_MEMTEST_DIR} || exit 1
        dmesg > dmesg.log
        
        TIME_TAG=$(date +%Y%m%d_%H%M%S)
        TAR_NAME="memtest_result_$TIME_TAG.tar.gz"
        
        FILES_TO_TAR="dmesg.log"
        if [ -d "mem_result" ]; then
             FILES_TO_TAR="$FILES_TO_TAR mem_result"
        fi
        
        tar -czvf $TAR_NAME $FILES_TO_TAR
        echo "SUCCESS: Archived Result to $TAR_NAME"
    """
    return run_ssh_command(server.os_ip, server.ssh_user, server.ssh_password, archive_cmd)

def archive_memtest(server: ServerSchema):
    return stop_memtest(server)