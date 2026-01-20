export interface Server {
  server_id: string
  bmc_ip: string
  os_ip?: string
  ssh_user: string
  ssh_password: string
  status: string
  description: string
  bmc_online: boolean
  os_online: boolean
  reboot_status: string
  reboot_phase: string
  reboot_loop: string
  memtest_status: string
  memtest_phase: string
  memtest_runtime_configured: string
  ac_ip: string
  ac_socket: string
  ac_temp_ip: string
  last_report_time: string
}

export interface WebhookData {
  server_id: string
  task_type: 'reboot' | 'memtest'
  status: string
  phase: string
  loop: string
}
