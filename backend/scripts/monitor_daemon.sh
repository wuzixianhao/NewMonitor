#!/bin/bash

# ===============================================
# 通用监控脚本 (适配 Reboot 和 ACReboot)
# ===============================================

BACKEND_URL="{{BACKEND_URL}}"
SERVER_ID="{{SERVER_ID}}"

# --- 1. 动态识别环境 ---
# 获取当前脚本所在目录 (兼容 /root/Reboot 和 /root/ACReboot)
WORK_DIR=$(cd "$(dirname "$0")" && pwd)

# 根据目录名判断任务类型
if [[ "$WORK_DIR" == *"ACReboot"* ]]; then
    TASK_TYPE="acreboot"
    LOG_SUB_DIR="ACReboot"
    # AC 模式下，主进程是 Cycle 脚本
    TARGET_PROCESS_KEY="Cycle_OSReboot" 
else
    TASK_TYPE="reboot"
    LOG_SUB_DIR="Reboot"
    # 普通模式下，主进程是 Chain 脚本
    TARGET_PROCESS_KEY="auto_cold_warm_stress_chain.sh"
fi

# 定义文件路径
LOG_DIR="/root/Test_Logs/$LOG_SUB_DIR"
mkdir -p "$LOG_DIR"

FLAG_FILE="$WORK_DIR/.chain_monitor_status"
# AC 和 Reboot 的轮次文件都是这个名字，但位置不同
LOOP_FILE="$WORK_DIR/reboot_all_times" 
LOCAL_LOG="$LOG_DIR/monitor_detail.log"
RUNNING_LOCK="$WORK_DIR/.is_reboot_running"
THIS_SCRIPT="$WORK_DIR/monitor_daemon.sh"
RC_LOC="/etc/rc.d/rc.local"

# --- 2. 日志轮转 (保持不变) ---
rotate_log() {
    local max_size=$((5 * 1024 * 1024))
    if [ -f "$LOCAL_LOG" ]; then
        local size=$(stat -c%s "$LOCAL_LOG")
        if [ $size -ge $max_size ]; then
            mv "$LOCAL_LOG" "$LOCAL_LOG.$(date +%Y%m%d_%H%M%S).bak"
            ls -t "$LOG_DIR"/*.bak | tail -n +6 | xargs -r rm
        fi
    fi
}

log_to_local() {
    local msg=$1
    local time_now=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$time_now] $msg" >> "$LOCAL_LOG"
    rotate_log
}

# --- 3. 开机自启 (保持不变) ---
ensure_startup() {
    local cmd="bash $THIS_SCRIPT > /dev/null 2>&1 &"
    if [ -f "$RC_LOC" ]; then
        chmod +x "$RC_LOC"
        if ! grep -q "$THIS_SCRIPT" "$RC_LOC"; then
            if grep -q "exit 0" "$RC_LOC"; then
                sed -i "/exit 0/i $cmd" "$RC_LOC"
            else
                echo "$cmd" >> "$RC_LOC"
            fi
        fi
    fi
}
ensure_startup

# --- 4. 智能看门狗 & 状态检测 ---
check_process_status() {
    if [ ! -f "$RUNNING_LOCK" ]; then return 0; fi # 锁没了，说明被停止了

    # 检查主进程是否存在
    PIDS=$(pgrep -f "$TARGET_PROCESS_KEY" | grep -v "grep" | grep -v "monitor")

    if [ -z "$PIDS" ]; then
        # 进程不见了！
        log_to_local "警告: 主进程 ($TARGET_PROCESS_KEY) 未运行"
        
        # 1. 如果是 Reboot (Chain脚本)，我们尝试拉起
        if [[ "$TASK_TYPE" == "reboot" ]]; then
            AUTO_SCRIPT="$WORK_DIR/auto_cold_warm_stress_chain.sh"
            if [ -f "$AUTO_SCRIPT" ]; then
                log_to_local "正在尝试拉起 Chain 脚本..."
                nohup bash "$AUTO_SCRIPT" > /dev/null 2>&1 &
            fi
        else
            # 2. 如果是 ACReboot，不自动拉起
            log_to_local "ACReboot 主进程丢失 (需人工介入)"
        fi
    fi
}

# --- 5. 上报后端 ---
report_backend() {
    local phase=$1
    local loop=$2
    local status=$3
    
    # 清理换行符
    phase=$(echo "$phase" | tr -d '\n')
    loop=$(echo "$loop" | tr -d '\n')
    
    JSON_DATA="{\"server_id\": \"$SERVER_ID\", \"task_type\": \"$TASK_TYPE\", \"phase\": \"$phase\", \"loop\": \"$loop\", \"status\": \"$status\"}"
    
    curl --noproxy "*" -s -X POST "$BACKEND_URL" \
         -H "Content-Type: application/json" \
         -d "$JSON_DATA" --connect-timeout 5 -m 10 > /dev/null 2>&1
}

echo "--- Monitor Started (Mode: $TASK_TYPE) ---" >> "$LOCAL_LOG"
touch "$RUNNING_LOCK"

# --- 主循环 ---
while true; do
    # 1. 检查停止信号
    if [ ! -f "$RUNNING_LOCK" ]; then
        log_to_local "检测到停止信号 (Lock removed)，退出。"
        exit 0
    fi

    # 2. 检查进程健康
    check_process_status

    # 3. 读取轮次
    curr_loop="0"
    if [ -f "$LOOP_FILE" ]; then 
        val=$(cat "$LOOP_FILE")
        if [[ "$val" =~ ^[0-9]+$ ]]; then curr_loop=$val; fi
    fi
    
    # 4. 读取阶段 (状态文件)
    curr_phase="运行中..."
    if [ -f "$FLAG_FILE" ]; then 
        curr_phase=$(cat "$FLAG_FILE")
    else
        PIDS=$(pgrep -f "$TARGET_PROCESS_KEY" | grep -v "grep" | grep -v "monitor")
        if [ -n "$PIDS" ]; then
            curr_phase="测试进行中"
        else
            curr_phase="等待进程启动..."
        fi
    fi

    # ==================================================
    # 🔥🔥🔥 核心修改：针对 Reboot 模式读取 rc.local 🔥🔥🔥
    # ==================================================
    if [[ "$TASK_TYPE" == "reboot" ]] && [ -f "$RC_LOC" ]; then
        # 1. 冷重启特征: -m -l ... 201
        # 使用 grep -F 固定字符串匹配，或者 regex 匹配
        if grep -q "Cycle_OSReboot_V2.2.2.sh -m -l -i 201" "$RC_LOC"; then
            curr_phase="冷重启进行中 (Cold)"
        
        # 2. 压力重启特征: -m ... 12 (注意：这里假设中间是空格)
        # 为了兼容可能的空格差异，使用 grep 正则匹配: -m.*-i 12
        elif grep -q "Cycle_OSReboot_V2.2.2.sh -m.*-i 12" "$RC_LOC"; then
            curr_phase="压力重启进行中 (Stress)"
        
        # 3. 热重启特征: -m ... 201 (不含 -l)
        # 注意顺序：先判断了冷重启，剩下的含 201 的就是热重启
        elif grep -q "Cycle_OSReboot_V2.2.2.sh -m.*-i 201" "$RC_LOC"; then
            curr_phase="热重启进行中 (Warm)"
        fi
    fi
    # ==================================================

    log_to_local "[Loop:$curr_loop] $curr_phase"
    
    # 5. 上报
    report_backend "$curr_phase" "$curr_loop" "Running"

    sleep 30
done