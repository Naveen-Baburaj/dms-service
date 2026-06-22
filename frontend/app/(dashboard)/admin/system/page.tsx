'use client';
import { useState } from 'react';
import { Shield, Database, Globe, Bell, Save } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';

export default function SystemSettingsPage() {
  const [saved, setSaved] = useState(false);

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  const systemInfo = [
    { label: 'Backend Version', value: 'Frappe v15.0.0', status: 'healthy' },
    { label: 'Database', value: 'MariaDB 10.6', status: 'healthy' },
    { label: 'Cache', value: 'Redis 7.0', status: 'healthy' },
    { label: 'Frontend', value: 'Next.js 15.5.19', status: 'healthy' },
    { label: 'API Status', value: 'Not connected', status: 'warning' },
  ];

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">System Settings</h1>
        <p className="text-muted-foreground text-sm mt-0.5">Platform-wide configuration and administration</p>
      </div>

      <Tabs defaultValue="general">
        <TabsList className="mb-6">
          <TabsTrigger value="general" className="flex items-center gap-2">
            <Globe className="h-4 w-4" /> General
          </TabsTrigger>
          <TabsTrigger value="security" className="flex items-center gap-2">
            <Shield className="h-4 w-4" /> Security
          </TabsTrigger>
          <TabsTrigger value="notifications" className="flex items-center gap-2">
            <Bell className="h-4 w-4" /> Notifications
          </TabsTrigger>
          <TabsTrigger value="system" className="flex items-center gap-2">
            <Database className="h-4 w-4" /> System Info
          </TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">General Configuration</CardTitle>
              <CardDescription>Platform-level settings for the DMS group</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2 col-span-2">
                  <Label>Platform Name</Label>
                  <Input defaultValue="DMS Portal" />
                </div>
                <div className="space-y-2">
                  <Label>Default Currency</Label>
                  <Input defaultValue="INR (₹)" />
                </div>
                <div className="space-y-2">
                  <Label>Date Format</Label>
                  <Input defaultValue="DD/MM/YYYY" />
                </div>
                <div className="space-y-2">
                  <Label>Financial Year Start</Label>
                  <Input defaultValue="April 1" />
                </div>
                <div className="space-y-2">
                  <Label>Default Timezone</Label>
                  <Input defaultValue="Asia/Kolkata (IST)" />
                </div>
                <div className="space-y-2 col-span-2">
                  <Label>Support Email</Label>
                  <Input defaultValue="support@dms.local" type="email" />
                </div>
              </div>
              <Separator />
              <div className="flex justify-end">
                <Button onClick={handleSave}>
                  <Save className="mr-2 h-4 w-4" />
                  {saved ? '✓ Saved' : 'Save Settings'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Security Settings</CardTitle>
              <CardDescription>Authentication and access control configuration</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Session Timeout (hours)</Label>
                  <Input defaultValue="8" type="number" min="1" max="24" />
                </div>
                <div className="space-y-2">
                  <Label>Refresh Token Validity (days)</Label>
                  <Input defaultValue="30" type="number" min="1" max="90" />
                </div>
                <div className="space-y-2">
                  <Label>Max Login Attempts</Label>
                  <Input defaultValue="5" type="number" min="3" max="10" />
                </div>
                <div className="space-y-2">
                  <Label>Lockout Duration (minutes)</Label>
                  <Input defaultValue="30" type="number" min="5" max="120" />
                </div>
              </div>
              {[
                { label: 'Enforce 2FA for Group Admins', checked: true },
                { label: 'Require strong passwords (min 8 chars, mixed case)', checked: true },
                { label: 'Log all admin actions', checked: true },
                { label: 'IP allowlist for admin accounts', checked: false },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between py-2">
                  <p className="text-sm">{item.label}</p>
                  <label className="relative inline-flex cursor-pointer items-center">
                    <input type="checkbox" className="peer sr-only" defaultChecked={item.checked} />
                    <div className="peer h-5 w-9 rounded-full bg-input transition-colors peer-checked:bg-primary after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:after:translate-x-4" />
                  </label>
                </div>
              ))}
              <Separator />
              <div className="flex justify-end">
                <Button onClick={handleSave}>
                  <Save className="mr-2 h-4 w-4" />
                  {saved ? '✓ Saved' : 'Save Settings'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">System Notification Settings</CardTitle>
              <CardDescription>Configure platform-level alerts and digests</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Admin Alert Email</Label>
                <Input defaultValue="admin@dms.local" type="email" />
              </div>
              <div className="space-y-2">
                <Label>Daily Digest Time</Label>
                <Input defaultValue="08:00" type="time" />
              </div>
              {[
                { label: 'Send daily performance digest to Group Admin', checked: true },
                { label: 'Alert on new user registrations', checked: true },
                { label: 'Alert on failed login attempts (> 3)', checked: true },
                { label: 'Weekly cross-company comparison report', checked: false },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between py-2">
                  <p className="text-sm">{item.label}</p>
                  <label className="relative inline-flex cursor-pointer items-center">
                    <input type="checkbox" className="peer sr-only" defaultChecked={item.checked} />
                    <div className="peer h-5 w-9 rounded-full bg-input transition-colors peer-checked:bg-primary after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:after:translate-x-4" />
                  </label>
                </div>
              ))}
              <Separator />
              <div className="flex justify-end">
                <Button onClick={handleSave}>{saved ? '✓ Saved' : 'Save Settings'}</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="system">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">System Status</CardTitle>
              <CardDescription>Current state of all platform services</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {systemInfo.map((item) => (
                <div key={item.label} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                  <div>
                    <p className="text-sm font-medium">{item.label}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{item.value}</p>
                  </div>
                  <Badge variant={item.status === 'healthy' ? 'success' : 'warning'} className="text-xs">
                    {item.status === 'healthy' ? '● Healthy' : '● Warning'}
                  </Badge>
                </div>
              ))}
              <div className="pt-3 rounded-lg bg-muted/50 p-4 mt-2">
                <p className="text-xs text-muted-foreground">
                  Last system check: <span className="font-medium text-foreground">Just now</span>
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Uptime: <span className="font-medium text-foreground">99.8%</span> (30 days)
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
