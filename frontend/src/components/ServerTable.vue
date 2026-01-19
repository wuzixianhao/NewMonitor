<script lang="ts" setup>
import { ref } from 'vue'
import { addServerDialog } from '@/status'
import AddServerForm from './AddServerForm.vue'

const props = defineProps<{
  servers: []
  loadingState: { [key: string]: boolean }
  loadingData: boolean
  backendStatus: string
}>()

const emit = defineEmits<{
  (e: 'action', payload: { server: any, action: string, payload?: any }): void
  (e: 'memtest-start', payload: { server: any, runtime: number }): void
  (e: 'delete', server: any): void
  (e: 'refresh'): void
  (e: 'add-server', server: any): void
}>()

const mode = defineModel<string>('mode')

const modeOptions = ref([
  { label: '重启测试', value: 'reboot' },
  { label: 'AC重启测试', value: 'acreboot' },
  { label: '内存压测', value: 'memtest' },
  { label: '内存信息采集', value: 'meminfo' },
])
const isLoading = srv => !!props.loadingState[srv.server_id]

function isRealOffline(data) {
  if (!data.os_online) {
    if (data.reboot_status !== 'Running' && data.memtest_status !== 'Running') {
      return true
    }
  }
  return false
}

function getStatusTag(status: string) {
  switch (status) {
    case 'Passed':
      return 'bg-success'
    case 'Failed':
      return 'bg-danger'
    case 'Running':
      return 'bg-primary'
    case 'Error':
      return 'bg-warning text-dark'
    default:
      return 'bg-secondary'
  }
}

function openACConfig(srv) {
  // 1. 输入 AC IP
  const ac_ip = prompt('请输入 AC 盒子 IP:', srv.ac_ip || '172.17.33.62')
  if (ac_ip === null)
    return

  // 2. 输入 插座号
  const ac_socket = prompt('请输入插座口 (1/2/3/4):', srv.ac_socket || '1')
  if (ac_socket === null)
    return

  // 3. 输入 临时 IP
  const ac_temp_ip = prompt('请输入 OS 临时 IP (如果能 ping 通 AC 可留空):', srv.ac_temp_ip || '')
  if (ac_temp_ip === null)
    return

  // 通过 action 触发保存，带上 payload
  emit('action', srv, 'save_config', {
    ac_ip,
    ac_socket,
    ac_temp_ip,
  })
}

function handleMemtestStart(srv) {
  const runtime = prompt('请输入压测时间 (秒)，默认 3600', '3600')
  if (runtime) {
    emit('memtest-start', srv, runtime)
  }
}
</script>

<template>
  <DataTable :value="servers">
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <span class="text-xl font-bold">
          <i class="pi pi-android text-[length:inherit]" /> 服务器自动化测试监控
        </span>
        <div class="space-x-2">
          <SelectButton
            v-model="mode"
            :options="modeOptions"
            option-label="label"
            option-value="value"
            :allow-empty="false"
          />
          <Tag :severity="backendStatus === '在线' ? 'success' : 'danger'">
            后端: {{ backendStatus }}
          </Tag>
          <Button
            icon="pi pi-refresh"
            :class="{
              'animate-spin': loadingData,
            }"
            rounded
            raised
            :disabled="loadingData"
            @click="$emit('refresh')"
          />
          <Button
            icon="pi pi-plus"
            raised
            :disabled="addServerDialog"
            @click="addServerDialog = true"
          />
        </div>
      </div>
    </template>
    <Column field="server_id" header="ID / IP">
      <template #body="{ data }">
        <Skeleton v-if="isLoading(data)" />
        <div v-else class="leading-6">
          <p>
            <strong>{{ data.server_id }}</strong>
          </p>
          <p>OS: {{ data.os_ip }}</p>
          <p>BMC: {{ data.bmc_ip }}</p>
        </div>
      </template>
    </Column>
    <Column header="连接状态">
      <template #body="{ data }">
        <Skeleton v-if="isLoading(data)" />
        <div v-else class="space-x-2">
          <Tag v-if="data.bmc_online" icon="pi pi-check" severity="success" rounded value="BMC" />
          <Tag v-else icon="pi pi-times" severity="danger" rounded value="BMC" />
          <Tag v-if="data.os_online" icon="pi pi-check" severity="success" rounded value="OS" />
          <Tag v-else icon="pi pi-times" severity="danger" rounded value="OS" />
        </div>
      </template>
    </Column>
    <Column header="测试状态">
      <template #body="{ data }">
        <Skeleton v-if="isLoading(data)" />
        <div v-else-if="isRealOffline(data)" class="space-y-1">
          <Tag rounded>
            <i class="bi bi-wifi-off" /> OS 离线
          </Tag>
          <div class="text-xs" style="color: #dc3545">
            无法连接测试
          </div>
        </div>
        <div v-else class="space-y-0.5">
          <Panel collapsed toggleable>
            <template #header>
              <div class="flex gap-2">
                <Tag v-if="data.memtest_status" :severity="getStatusTag(data.memtest_status)">
                  {{ data.memtest_status }}
                </Tag>
                <Tag v-if="data.reboot_status" :severity="getStatusTag(data.reboot_status)">
                  {{ data.reboot_status }}
                </Tag>
              </div>
            </template>

            <div class="small text-muted mt-1">
              {{ data.reboot_phase }}
            </div>
            <div class="small text-secondary mt-1">
              轮次: <b>{{ data.reboot_loop }}</b>
            </div>
          </Panel>

          <div v-if="mode === 'acreboot'">
            <Tag :severity="getStatusTag(data.reboot_status)">
              {{ data.reboot_status }}
            </Tag>
            <div class="small text-muted mt-1">
              {{ data.reboot_phase }}
            </div>

            <div class="small text-secondary mt-1">
              轮次: <b>{{ data.reboot_loop }}</b>
            </div>

            <div v-if="data.ac_ip" class="small text-primary mt-1">
              AC: {{ data.ac_ip }} (口:{{ data.ac_socket }})
            </div>
            <div v-else class="small text-danger mt-1">
              <i class="bi bi-exclamation-circle" /> 未配置 AC
            </div>
          </div>

          <div v-if="mode === 'memtest'">
            <div class="small text-muted mt-1">
              {{ data.memtest_phase }}
            </div>
          </div>

          <div class="text-muted" style="font-size: 10px">
            Update: {{ data.last_report_time }}
          </div>
        </div>
      </template>
    </Column>
    <Column>
      <template #body="{ data }">
        <Skeleton v-if="isLoading(data)" />
        <template v-else>
          <template v-if="mode === 'acreboot'">
            <InputGroup>
              <InputGroupAddon>
                <Button icon="pi pi-cog" size="small" label="配置" @click="openACConfig(data)" />
              </InputGroupAddon>
              <InputGroupAddon>
                <Button
                  icon="pi pi-file-arrow-up"
                  size="small"
                  :disabled="isLoading(data)"
                  label="部署"
                  @click="$emit('action', data, 'deploy')"
                />
              </InputGroupAddon>
              <InputGroupAddon>
                <Button
                  icon="pi pi-play"
                  size="small"
                  :disabled="isLoading(data) || data.reboot_status === 'Running'"
                  label="启动"
                  @click="$emit('action', data, 'start_test')"
                />
              </InputGroupAddon>
              <InputGroupAddon>
                <Button
                  icon="pi pi-stop"
                  size="small"
                  :disabled="isLoading(data)"
                  severity="danger"
                  label="停止"
                  @click="$emit('action', data, 'stop_test')"
                />
              </InputGroupAddon>
            </InputGroup>
          </template>

          <template v-if="mode === 'reboot'">
            <InputGroup>
              <InputGroupAddon>
                <Button
                  icon="pi pi-file-arrow-up"
                  size="small"
                  :disabled="isLoading(data)"
                  label="部署"
                  @click="$emit('action', data, 'deploy')"
                />
              </InputGroupAddon>
              <InputGroupAddon>
                <Button
                  icon="pi pi-play"
                  size="small"
                  :disabled="isLoading(data) || data.reboot_status === 'Running'"
                  label="启动"
                  @click="$emit('action', data, 'start_test')"
                />
              </InputGroupAddon>
              <InputGroupAddon>
                <Button
                  icon="pi pi-stop"
                  size="small"
                  :disabled="isLoading(data)"
                  severity="danger"
                  label="停止"
                  @click="$emit('action', data, 'stop_test')"
                />
              </InputGroupAddon>
              <InputGroupAddon>
                <Button
                  icon="pi pi-trash"
                  size="small"
                  severity="secondary"
                  :disabled="isLoading(data)"
                  label="清理文件"
                  @click="$emit('action', data, 'reset_files')"
                />
              </InputGroupAddon>
            </InputGroup>
          </template>

          <template v-if="mode === 'memtest'">
            <InputGroup>
              <InputGroupAddon>
                <Button
                  icon="pi pi-file-arrow-up"
                  size="small"
                  :disabled="isLoading(data)"
                  label="部署"
                  @click="$emit('action', data, 'deploy')"
                />
              </InputGroupAddon>
              <InputGroupAddon>
                <Button
                  class="btn btn-outline-success"
                  label="Start(1h)"
                  size="small"
                  :disabled="isLoading(data) || data.memtest_status === 'Running'"
                  @click="handleMemtestStart(data)"
                />
              </InputGroupAddon>
              <InputGroupAddon>
                <Button
                  icon="pi pi-save"
                  label="归档"
                  size="small"
                  severity="secondary"
                  :disabled="isLoading(data)"
                  @click="$emit('action', data, 'memtest/archive')"
                />
              </InputGroupAddon>
            </InputGroup>
          </template>

          <template v-if="mode === 'meminfo'">
            <InputGroup>
              <InputGroupAddon>
                <Button
                  icon="pi pi-file-arrow-up"
                  size="small"
                  :disabled="isLoading(data)"
                  label="部署"
                  @click="$emit('action', data, 'deploy')"
                />
              </InputGroupAddon>
              <InputGroupAddon>
                <Button
                  icon="pi pi-microchip"
                  label="检查"
                  size="small"
                  :disabled="isLoading(data)"
                  @click="$emit('action', data, 'meminfo/run')"
                />
              </InputGroupAddon>
              <InputGroupAddon>
                <Button
                  icon="pi pi-download"
                  label="下载"
                  size="small"
                  @click="open(`/servers/${data.server_id}/meminfo/download`)"
                />
              </InputGroupAddon>
            </InputGroup>
          </template>
        </template>
      </template>
    </Column>
    <Column>
      <template #body="{ data }">
        <Skeleton v-if="isLoading(data)" />
        <Button
          v-else
          icon="pi pi-times"
          severity="danger"
          size="small"
          :disabled="isLoading(data)"
          @click="$emit('delete', data)"
        />
      </template>
    </Column>

    <AddServerForm @add="$emit('add-server', $event)" />
  </DataTable>
</template>
