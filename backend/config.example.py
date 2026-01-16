import os

# --- 1. 基础路径配置 ---
# 使用绝对路径更安全，防止在不同目录下运行报错
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOCAL_SCRIPT_DIR = os.path.join(BASE_DIR, "scripts")
TEMP_SCRIPT_DIR = os.path.join(BASE_DIR, "temp_scripts")
DB_FILE = os.path.join(BASE_DIR, "data", "servers_db.json")
LOCAL_DOWNLOAD_DIR = os.path.join(BASE_DIR, "data", "downloads")

# 自动创建必要目录
if not os.path.exists(os.path.dirname(DB_FILE)): os.makedirs(os.path.dirname(DB_FILE))
if not os.path.exists(LOCAL_DOWNLOAD_DIR): os.makedirs(LOCAL_DOWNLOAD_DIR)

# --- 2. 服务器连接配置 ---
SSH_PORT = 22
# ✅ 你的实际 IP
BACKEND_IP_PORT = "*.*.*.*:*"

# --- 3. 脚本文件名定义 ---

# Reboot 专用 (V2.2.3)
SCRIPT_CYCLE_NAME = "Cycle_OSReboot_V2.2.3.sh"
SCRIPT_CHAIN_NAME = "auto_cold_warm_stress_chain.sh"

# ✅ ACReboot 专用 (V2.2.2) 
# 请务必确认 scripts/ 目录下有这个文件
SCRIPT_AC_NAME = "Cycle_OSReboot_V2.2.2.sh"

# 监控脚本 (通用)
SCRIPT_MONITOR_NAME = "monitor_daemon.sh"

# Memtest 相关
SCRIPT_MEMTEST_NAME = "memtester.sh"
FILE_MEMTEST_TAR = "memtester-4.6.0.tar.gz"

# MemInfo 相关
SCRIPT_MEM_INFO_NAME = "get_memory_info.sh"

# --- 4. 远程路径配置 ---
REMOTE_WORK_DIR = "/root/Reboot"
REMOTE_MEMTEST_DIR = "/root/Memtest"
REMOTE_MEM_DIR = "/root/MemInfo"

# ✅ ACReboot 独立目录
REMOTE_AC_DIR = "/root/ACReboot"

# --- 5. RC.Local 恢复模板 ---
CLEAN_RC_LOCAL_CONTENT = r"""#!/bin/bash
# THIS FILE IS ADDED FOR COMPATIBILITY PURPOSES
#
# It is highly advisable to create own systemd services or udev rules
# to run scripts during boot instead of using this file.
#
# In contrast to previous versions due to parallel execution during boot
# this script will NOT be run after all other services.
#
# Please note that you must run 'chmod +x /etc/rc.d/rc.local' to ensure
# that this script will be executed during boot.

touch /var/lock/subsys/local
exit 0
"""