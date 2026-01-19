export interface ServerItem {
  id: string
  name: string
  status: 'online' | 'offline' | 'maintenance'
  ipAddress: string
  bmcAddress: string
  sshUsername: string
  sshPassword: string
  createdAt: Date
  updatedAt: Date
}
