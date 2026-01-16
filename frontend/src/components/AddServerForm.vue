<template>
  <div class="card mt-4 shadow-sm">
    <div class="card-body">
      <h5 class="card-title mb-3">添加测试机器</h5>
      <div class="row g-2">
        <div class="col-md-3">
          <input v-model="form.server_id" class="form-control" placeholder="Server ID (e.g. S01)">
        </div>
        <div class="col-md-3">
          <input v-model="form.os_ip" class="form-control" placeholder="OS IP">
        </div>
        <div class="col-md-3">
          <input v-model="form.bmc_ip" class="form-control" placeholder="BMC IP">
        </div>
        <div class="col-md-3">
          <button class="btn btn-success w-100" @click="handleSubmit">
            <i class="bi bi-plus-lg"></i> 添加列表
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['add'])

const form = ref({
  server_id: '', os_ip: '', bmc_ip: '', ssh_user: 'root', ssh_password: '1'
})

const handleSubmit = () => {
  if (!form.value.server_id || !form.value.os_ip) return alert("请填写完整")
  // 发送给父组件
  emit('add', { ...form.value })
  // 清空表单
  form.value = { server_id: '', os_ip: '', bmc_ip: '', ssh_user: 'root', ssh_password: '1' }
}
</script>