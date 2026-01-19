<script lang="ts" setup>
import axios from 'axios'
import { useToast } from 'primevue'
import { onMounted, onUnmounted, ref } from 'vue'
import ServerTable from './components/ServerTable.vue'
import { addServerDialog } from './status'

const servers = ref([])
const mode = ref('reboot')
const backendStatus = ref('连接中...')
const loadingData = ref(true)
const loadingState = ref({})
const toast = useToast()

const ws = ref<WebSocket | null>(null)
const reconnectTimer = ref<number | null>(null)

// 建立 WebSocket 连接
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  // 这里的 /ws 与后端路由对应，Vite 代理会处理转发
  const wsUrl = `${protocol}//${window.location.host}/ws`

  console.log(`[WebSocket] 正在连接: ${wsUrl}`)
  ws.value = new WebSocket(wsUrl)

  ws.value.onopen = () => {
    console.log('[WebSocket] 已连接')
    backendStatus.value = '在线'
    if (reconnectTimer.value) {
      clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
    }
  }

  ws.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.results) {
        servers.value = data.results
      }
    }
    catch (e) {
      console.error('[WebSocket] 消息解析失败:', e)
    }
  }

  ws.value.onclose = (e) => {
    console.warn('[WebSocket] 连接关闭，尝试重连...', e.reason)
    backendStatus.value = '离线 (重连中...)'
    // 3秒后尝试重连
    reconnectTimer.value = setTimeout(() => {
      initWebSocket()
    }, 3000)
  }

  ws.value.onerror = (error) => {
    console.error('[WebSocket] 错误:', error)
    ws.value.close()
  }
}

// 刷新状态
async function refreshStatus() {
  try {
    loadingData.value = true
    const res = await axios.post('/monitor/refresh')
    servers.value = res.data.results
    loadingData.value = false
    backendStatus.value = '在线'
  }
  catch (error) {
    // 这里如果报 404，说明 vite.config.js 没配好 proxy
    console.error('刷新失败:', error)
    backendStatus.value = '离线 (连接失败)'
  }
}

// ✅✅✅ 修复参数接收 ✅✅✅
async function startMemtest(srv, runtime) {
  const sid = srv.server_id

  // 简单的参数校验
  if (!runtime) {
    toast.add({ severity: 'warn', summary: '取消操作', life: 3000 })
    return
  }

  loadingState.value[sid] = true
  try {
    const url = `/servers/${sid}/memtest/start`
    // 发送 POST 请求，带上 runtime
    const res = await axios.post(url, { runtime })

    if (res.data.success) {
      toast.add({ severity: 'success', summary: '内存测试已启动', life: 3000 })
      refreshStatus()
    }
    else {
      toast.add({ severity: 'error', summary: '启动失败', detail: res.data.message, life: 3000 })
    }
  }
  catch (e) {
    console.error(e)
    toast.add({ severity: 'error', summary: `请求异常: ${e.message}` })
  }
  finally {
    loadingState.value[sid] = false
  }
}

// ✅✅✅ 终极修正版 handleAction ✅✅✅
async function handleAction(srv, actionPath, payload = null) {
  const sid = srv.server_id
  let url = ''

  // 1. 打印调试信息 (帮助我们确诊)
  console.log(`[Debug] Mode: ${mode.value}, Action: ${actionPath}`)

  // 2. 路由分发 (使用 switch case 更清晰，防止 if-else 混乱)
  if (actionPath.includes('/')) {
    // 绝对路径模式 (如 acreboot/stop, meminfo/run)
    url = `/servers/${sid}/${actionPath}`
  }
  else {
    switch (mode.value) {
      case 'reboot':
        url = `/servers/${sid}/${actionPath}`
        break

      case 'acreboot':
        // ⚠️ 重点在这里：必须把 start_test 拦截下来！
        if (actionPath === 'deploy')
          url = `/servers/${sid}/acreboot/deploy`
        else if (actionPath === 'start_test')
          url = `/servers/${sid}/acreboot/start` // <--- 必须是这个！
        else if (actionPath === 'stop_test')
          url = `/servers/${sid}/acreboot/stop`
        else if (actionPath === 'save_config')
          url = `/servers/${sid}/acreboot/save_config`
        else url = `/servers/${sid}/${actionPath}` // 兜底
        break

      case 'memtest':
        if (actionPath === 'deploy')
          url = `/servers/${sid}/memtest/deploy`
        else url = `/servers/${sid}/${actionPath}`
        break

      case 'meminfo':
        if (actionPath === 'deploy')
          url = `/servers/${sid}/meminfo/deploy`
        else if (actionPath === 'run')
          url = `/servers/${sid}/meminfo/run`
        else url = `/servers/${sid}/${actionPath}`
        break

      default:
        url = `/servers/${sid}/${actionPath}`
    }
  }

  // 3. 最后的防线：如果是 AC 模式，URL 里必须包含 acreboot
  if (mode.value === 'acreboot' && !url.includes('acreboot')) {
    toast.add({ severity: 'error', summary: `❌ 严重错误！\n当前是 AC 模式，但生成的 URL 是：${url}\n请截图给开发人员！` })
    return
  }

  if (!url) {
    toast.add({ severity: 'error', summary: '错误: 无法构建请求 URL' })
    return
  }
  // 4. 执行请求
  loadingState.value[sid] = true
  try {
    const res = await axios.post(url, payload || {})

    if (res.data.success) {
      if (actionPath === 'save_config') {
        refreshStatus()
      }
      else {
        // 成功提示
        console.log('Success:', res.data)
        toast.add({ severity: 'success', summary: `操作成功: ${res.data.message}` })
        refreshStatus()
      }
    }
    else {
      toast.add({ severity: 'error', summary: `操作失败: ${res.data.message}` })
    }
  }
  catch (e) {
    console.error(e)
    toast.add({ severity: 'error', summary: `请求异常: ${e.response ? e.response.status : e.message}\nURL: ${url}` })
  }
  finally {
    loadingState.value[sid] = false
  }
}

async function addServer(serverData) {
  try {
    await axios.post('/servers/add', serverData)
    toast.add({ severity: 'success', summary: '添加成功' })
    addServerDialog.value = false
    refreshStatus()
  }
  catch (e) {
    toast.add({ severity: 'error', summary: '添加失败' })
  }
}

async function deleteServer(id: string) {
  if (!confirm('确定删除吗？'))
    return
  try {
    await axios.delete(`/servers/delete/${id}`)
    refreshStatus()
  }
  catch {
    toast.add({ severity: 'error', summary: '删除失败' })
  }
}

onMounted(() => {
  initWebSocket()
})

onUnmounted(() => {
  if (ws.value) {
    ws.value.close()
  }
  if (reconnectTimer.value) {
    clearTimeout(reconnectTimer.value)
  }
})
</script>

<template>
  <div class="container mx-auto py-4">
    <ServerTable
      v-model:mode="mode"
      :servers
      :loading-state
      :loading-data
      :backend-status
      @action="handleAction"
      @memtest-start="startMemtest"
      @delete="deleteServer"
      @refresh="refreshStatus"
      @add-server="addServer"
    />
  </div>
  <Toast />
</template>
