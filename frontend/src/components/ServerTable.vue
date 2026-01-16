<template>
  <div class="card shadow-sm server-table">
    <div class="card-body p-0">
      <table class="table table-hover mb-0 align-middle">
        <thead class="table-light">
          <tr>
            <th>ID / IP</th>
            <th>BMC状态</th>
            <th>测试状态</th>
            <th>操作控制 ({{ mode.toUpperCase() }})</th>
            <th>管理</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="srv in servers" :key="srv.server_id">
            
            <td>
              <div class="fw-bold">{{ srv.server_id }}</div>
              <div class="text-muted small">
                <i class="bi bi-hdd-network"></i> {{ srv.os_ip || 'N/A' }}
              </div>
            </td>

            <td>
              <span v-if="srv.bmc_online" class="badge bg-success">BMC 在线</span>
              <span v-else class="badge bg-danger">BMC 离线</span>
              <div class="small text-muted">{{ srv.bmc_ip }}</div>
            </td>

            <td>
              <div v-if="isRealOffline(srv)">
                  <span class="badge bg-danger"><i class="bi bi-wifi-off"></i> OS 离线</span>
                  <div style="font-size: 11px; color: #dc3545; margin-top: 4px;">无法连接测试</div>
              </div>
              <div v-else>
                  <div v-if="!srv.os_online" class="mb-1">
                      <span class="badge bg-warning text-dark" style="font-size: 10px;">
                          <i class="bi bi-arrow-repeat"></i> 重启/连接中...
                      </span>
                  </div>

                  <div v-if="mode === 'reboot'">
                      <span class="badge" :class="getStatusBadge(srv.reboot_status)">{{ srv.reboot_status }}</span>
                      <div class="small text-muted mt-1">{{ srv.reboot_phase }}</div>
                      <div class="small text-secondary mt-1">轮次: <b>{{ srv.reboot_loop }}</b></div>
                  </div>

                  <div v-if="mode === 'acreboot'">
                      <span class="badge" :class="getStatusBadge(srv.reboot_status)">{{ srv.reboot_status }}</span>
                      <div class="small text-muted mt-1">{{ srv.reboot_phase }}</div>
                      
                      <div class="small text-secondary mt-1">
                          轮次: <b>{{ srv.reboot_loop }}</b>
                      </div>

                      <div class="small text-primary mt-1" v-if="srv.ac_ip">
                        AC: {{ srv.ac_ip }} (口:{{ srv.ac_socket }})
                      </div>
                      <div class="small text-danger mt-1" v-else>
                        <i class="bi bi-exclamation-circle"></i> 未配置 AC
                      </div>
                  </div>

                  <div v-if="mode === 'memtest'">
                      <span class="badge" :class="getStatusBadge(srv.memtest_status)">{{ srv.memtest_status }}</span>
                      <div class="small text-muted mt-1">{{ srv.memtest_phase }}</div>
                  </div>

                  <div v-if="mode === 'meminfo'">
                      <span class="badge bg-secondary">就绪</span>
                  </div>

                  <div class="text-muted" style="font-size: 10px; margin-top: 2px;">
                      Update: {{ srv.last_report_time }}
                  </div>
              </div>
            </td>

            <td>
              <div class="btn-group btn-group-sm">
                
                <template v-if="mode === 'acreboot'">
                   <button class="btn btn-outline-dark" @click="openACConfig(srv)">
                    <i class="bi bi-gear-fill"></i> 配置
                  </button>

                  <button class="btn btn-outline-primary" 
                          @click="$emit('action', srv, 'deploy')" 
                          :disabled="isLoading(srv)">
                    <i class="bi bi-cloud-upload"></i> 部署
                  </button>

                  <button class="btn btn-outline-success" 
                          @click="$emit('action', srv, 'start_test')" 
                          :disabled="isLoading(srv) || srv.reboot_status === 'Running'">
                    <i class="bi bi-play-fill"></i> 启动
                  </button>

                  <button class="btn btn-outline-danger" 
                          @click="$emit('action', srv, 'stop_test')" 
                          :disabled="isLoading(srv)">
                    <i class="bi bi-stop-fill"></i> 停止
                  </button>
                </template>


                <template v-if="mode === 'reboot'">
                  <button class="btn btn-outline-primary" 
                          @click="$emit('action', srv, 'deploy')" 
                          :disabled="isLoading(srv)">
                    <i class="bi bi-cloud-upload"></i> 部署
                  </button>
                  <button class="btn btn-outline-success" 
                          @click="$emit('action', srv, 'start_test')" 
                          :disabled="isLoading(srv) || srv.reboot_status === 'Running'">
                    <i class="bi bi-play-fill"></i> 启动
                  </button>
                  <button class="btn btn-outline-danger" 
                          @click="$emit('action', srv, 'stop_test')" 
                          :disabled="isLoading(srv)">
                    <i class="bi bi-stop-fill"></i> 停止
                  </button>
                  <button class="btn btn-outline-secondary" 
                          @click="$emit('action', srv, 'reset_files')" 
                          :disabled="isLoading(srv)">
                    <i class="bi bi-trash"></i> 重置
                  </button>
                </template>


                <template v-if="mode === 'memtest'">
                   <button class="btn btn-outline-primary" 
                          @click="$emit('action', srv, 'deploy')" 
                          :disabled="isLoading(srv)">
                    <i class="bi bi-cloud-upload"></i> 部署
                  </button>
                   <button class="btn btn-outline-success" 
                           @click="handleMemtestStart(srv)" 
                           :disabled="isLoading(srv) || srv.memtest_status === 'Running'">
                    <i class="bi bi-play-fill"></i> Start(1h)
                  </button>
                  <button class="btn btn-outline-warning" 
                          @click="$emit('action', srv, 'memtest/archive')" 
                          :disabled="isLoading(srv)">
                    <i class="bi bi-box-seam"></i> 归档
                  </button>
                </template>

                <template v-if="mode === 'meminfo'">
                    <button class="btn btn-outline-primary" 
                          @click="$emit('action', srv, 'deploy')" 
                          :disabled="isLoading(srv)">
                      <i class="bi bi-cloud-upload"></i> 部署
                    </button>
                    <button class="btn btn-outline-success" 
                            @click="$emit('action', srv, 'meminfo/run')" 
                            :disabled="isLoading(srv)">
                      <i class="bi bi-cpu"></i> 检查
                    </button>
                    <a class="btn btn-outline-dark" 
                       :href="`/servers/${srv.server_id}/meminfo/download`" 
                       target="_blank">
                      <i class="bi bi-download"></i> 下载
                    </a>
                </template>

              </div>
            </td>

            <td>
              <button class="btn btn-link text-danger p-0" @click="$emit('delete', srv.server_id)">
                <i class="bi bi-x-circle"></i>
              </button>
            </td>
          </tr>
          
          <tr v-if="servers.length === 0">
            <td colspan="5" class="text-center py-4 text-muted">暂无服务器，请在下方添加</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  servers: Array,
  mode: String,
  loadingState: Object
})

const emit = defineEmits(['action', 'memtest-start', 'delete'])

const isLoading = (srv) => !!props.loadingState[srv.server_id]

const isRealOffline = (srv) => {
  if (!srv.os_online) {
    if (srv.reboot_status !== 'Running' && srv.memtest_status !== 'Running') {
      return true
    }
  }
  return false
}

const getStatusBadge = (status) => {
  if (!status) return 'bg-secondary'
  const s = status.toLowerCase()
  if (s === 'running') return 'bg-primary'
  if (s === 'deployed') return 'bg-info text-dark'
  if (s === 'stopped' || s === 'finished') return 'bg-success'
  if (s === 'idle') return 'bg-secondary'
  if (s === 'offline') return 'bg-danger'
  return 'bg-secondary'
}

const handleMemtestStart = (srv) => {
    const runtime = prompt("请输入压测时间 (秒)，默认 3600", "3600")
    if (runtime) {
        emit('memtest-start', srv, runtime)
    }
}

// ✅ 新增：处理 AC 配置弹窗
const openACConfig = (srv) => {
    // 1. 输入 AC IP
    const ac_ip = prompt("请输入 AC 盒子 IP:", srv.ac_ip || "172.17.33.62")
    if (ac_ip === null) return

    // 2. 输入 插座号
    const ac_socket = prompt("请输入插座口 (1/2/3/4):", srv.ac_socket || "1")
    if (ac_socket === null) return

    // 3. 输入 临时 IP
    const ac_temp_ip = prompt("请输入 OS 临时 IP (如果能 ping 通 AC 可留空):", srv.ac_temp_ip || "")
    if (ac_temp_ip === null) return

    // 通过 action 触发保存，带上 payload
    emit('action', srv, 'save_config', {
        ac_ip, ac_socket, ac_temp_ip
    })
}
</script>

<style scoped>
  .server-table {
    overflow: hidden;
    border-radius: 0 0 var(--bs-card-border-radius) var(--bs-card-border-radius);
    border-top: none;
  }
</style>