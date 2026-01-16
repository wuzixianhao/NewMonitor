<template>
  <div class="container py-4">
    <Header :backend-status="backendStatus" @refresh="refreshStatus" />

    <ul class="nav nav-tabs">
      <li class="nav-item" v-for="m in ['reboot', 'acreboot', 'memtest', 'meminfo']" :key="m">
        <a class="nav-link" 
           :class="{ active: mode === m }" 
           href="#" 
           @click.prevent="mode = m">
           {{ m.charAt(0).toUpperCase() + m.slice(1) }}
        </a>
      </li>
    </ul>

    <ServerTable 
      :servers="servers" 
      :mode="mode" 
      :loading-state="loadingState"
      @action="handleAction"
      @memtest-start="startMemtest"
      @delete="deleteServer"
    />

    <AddServerForm @add="addServer" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import Header from './components/Header.vue'
import ServerTable from './components/ServerTable.vue'
import AddServerForm from './components/AddServerForm.vue'

const servers = ref([])
const mode = ref('reboot')
const backendStatus = ref('检查中...')
const loadingState = ref({})
const timer = ref(null)

// 刷新状态
const refreshStatus = async () => {
  try {
    const res = await axios.post('/monitor/refresh')
    servers.value = res.data.results
    backendStatus.value = '在线'
  } catch (error) {
    // 这里如果报 404，说明 vite.config.js 没配好 proxy
    console.error("刷新失败:", error)
    backendStatus.value = '离线 (连接失败)'
  }
}

// ✅✅✅ 修复参数接收 ✅✅✅
const startMemtest = async (srv, runtime) => {
  const sid = srv.server_id
  
  // 简单的参数校验
  if (!runtime) {
      alert("取消操作")
      return
  }
  
  loadingState.value[sid] = true
  try {
    const url = `/servers/${sid}/memtest/start`
    // 发送 POST 请求，带上 runtime
    const res = await axios.post(url, { runtime: runtime })
    
    if (res.data.success) {
      alert(`Memtest 启动成功: ${res.data.message}`)
      refreshStatus()
    } else {
      alert(`启动失败: ${res.data.message}`)
    }
  } catch (e) {
    console.error(e)
    alert(`请求异常: ${e.message}`)
  } finally {
    loadingState.value[sid] = false
  }
}

// ✅✅✅ 终极修正版 handleAction ✅✅✅
const handleAction = async (srv, actionPath, payload = null) => {
  const sid = srv.server_id
  let url = ''

  // 1. 打印调试信息 (帮助我们确诊)
  console.log(`[Debug] Mode: ${mode.value}, Action: ${actionPath}`)

  // 2. 路由分发 (使用 switch case 更清晰，防止 if-else 混乱)
  if (actionPath.includes('/')) {
      // 绝对路径模式 (如 acreboot/stop, meminfo/run)
      url = `/servers/${sid}/${actionPath}`
  } else {
      switch (mode.value) {
          case 'reboot':
              url = `/servers/${sid}/${actionPath}`
              break;
          
          case 'acreboot':
              // ⚠️ 重点在这里：必须把 start_test 拦截下来！
              if (actionPath === 'deploy') url = `/servers/${sid}/acreboot/deploy`
              else if (actionPath === 'start_test') url = `/servers/${sid}/acreboot/start` // <--- 必须是这个！
              else if (actionPath === 'stop_test') url = `/servers/${sid}/acreboot/stop`
              else if (actionPath === 'save_config') url = `/servers/${sid}/acreboot/save_config`
              else url = `/servers/${sid}/${actionPath}` // 兜底
              break;

          case 'memtest':
              if (actionPath === 'deploy') url = `/servers/${sid}/memtest/deploy`
              else url = `/servers/${sid}/${actionPath}`
              break;

          case 'meminfo':
              if (actionPath === 'deploy') url = `/servers/${sid}/meminfo/deploy`
              else if (actionPath === 'run') url = `/servers/${sid}/meminfo/run`
              else url = `/servers/${sid}/${actionPath}`
              break;
              
          default:
              url = `/servers/${sid}/${actionPath}`
      }
  }

  // 3. 最后的防线：如果是 AC 模式，URL 里必须包含 acreboot
  if (mode.value === 'acreboot' && !url.includes('acreboot')) {
      alert(`❌ 严重错误！\n当前是 AC 模式，但生成的 URL 是：${url}\n请截图给开发人员！`)
      return
  }

  if (!url) return alert("错误: 无法构建请求 URL")

  // 4. 执行请求
  loadingState.value[sid] = true 
  try {
    const res = await axios.post(url, payload || {})
    
    if (res.data.success) {
      if (actionPath === 'save_config') {
          refreshStatus()
      } else {
          // 成功提示
          console.log("Success:", res.data)
          alert(`操作成功: ${res.data.message}`)
          refreshStatus() 
      }
    } else {
      alert(`操作失败: ${res.data.message}`)
    }
  } catch (e) {
    console.error(e)
    alert(`请求异常: ${e.response ? e.response.status : e.message}\nURL: ${url}`)
  } finally {
    loadingState.value[sid] = false 
  }
}

const addServer = async (serverData) => {
  try {
    await axios.post('/servers/add', serverData)
    alert("添加成功")
    refreshStatus()
  } catch (e) {
    alert("添加失败")
  }
}

const deleteServer = async (id) => {
  if(!confirm("确定删除吗？")) return
  try {
    await axios.delete(`/servers/delete/${id}`)
    refreshStatus()
  } catch(e) { alert("删除失败") }
}

onMounted(() => {
  refreshStatus()
  timer.value = setInterval(refreshStatus, 3000)
})

onUnmounted(() => {
  if (timer.value) clearInterval(timer.value)
})
</script>