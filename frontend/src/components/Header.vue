<template>
  <div class="d-flex justify-content-between align-items-center mb-4">
    <h2 class="mb-0"><i class="bi bi-robot"></i> 服务器自动化测试监控</h2>
    <div>
      <span class="badge me-2" 
            :class="backendStatus === '在线' ? 'bg-success' : 'bg-secondary'">
        后端: {{ backendStatus }}
      </span>
      <button class="btn btn-outline-primary btn-sm" @click="$emit('refresh')">
        <i class="bi bi-arrow-clockwise"></i> 刷新
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  backendStatus: String
})
defineEmits(['refresh'])
</script>