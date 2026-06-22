'use client';
import { useState } from 'react';
import { User, Bell, Lock, Building2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuthStore } from '@/store/authStore';

export default function SettingsPage() {
  const { user } = useAuthStore();
  const [saved, setSaved] = useState(false);

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground text-sm mt-0.5">Manage your account and preferences</p>
      </div>

      <Tabs defaultValue="profile">
        <TabsList className="mb-6">
          <TabsTrigger value="profile" className="flex items-center gap-2">
            <User className="h-4 w-4" /> Profile
          </TabsTrigger>
          <TabsTrigger value="notifications" className="flex items-center gap-2">
            <Bell className="h-4 w-4" /> Notifications
          </TabsTrigger>
          <TabsTrigger value="security" className="flex items-center gap-2">
            <Lock className="h-4 w-4" /> Security
          </TabsTrigger>
          <TabsTrigger value="dealership" className="flex items-center gap-2">
            <Building2 className="h-4 w-4" /> Dealership
          </TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Profile Information</CardTitle>
              <CardDescription>Update your personal details</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Full Name</Label>
                  <Input defaultValue={user?.full_name ?? ''} />
                </div>
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input defaultValue={user?.email ?? ''} type="email" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Role</Label>
                <Input value={user?.role?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) ?? ''} readOnly className="bg-muted" />
              </div>
              <div className="space-y-2">
                <Label>Company</Label>
                <Input value={user?.company ?? ''} readOnly className="bg-muted" />
              </div>
              <Separator />
              <div className="flex justify-end">
                <Button onClick={handleSave}>
                  {saved ? '✓ Saved' : 'Save changes'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Notification Preferences</CardTitle>
              <CardDescription>Choose what you want to be notified about</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {[
                { label: 'New lead assigned', desc: 'Get notified when a lead is assigned to you' },
                { label: 'Booking confirmation', desc: 'Get notified when a booking is confirmed' },
                { label: 'Test drive reminder', desc: 'Get reminders 1 hour before scheduled test drives' },
                { label: 'Sales target updates', desc: 'Weekly summary of sales vs target' },
                { label: 'Service job completion', desc: 'When a service job is marked complete' },
              ].map((item) => (
                <div key={item.label} className="flex items-start justify-between py-2">
                  <div>
                    <p className="text-sm font-medium">{item.label}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{item.desc}</p>
                  </div>
                  <label className="relative inline-flex cursor-pointer items-center">
                    <input type="checkbox" className="peer sr-only" defaultChecked />
                    <div className="peer h-5 w-9 rounded-full bg-input transition-colors peer-checked:bg-primary after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all peer-checked:after:translate-x-4" />
                  </label>
                </div>
              ))}
              <Separator />
              <div className="flex justify-end">
                <Button onClick={handleSave}>{saved ? '✓ Saved' : 'Save preferences'}</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Change Password</CardTitle>
              <CardDescription>Update your login password</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Current Password</Label>
                <Input type="password" placeholder="••••••••" />
              </div>
              <div className="space-y-2">
                <Label>New Password</Label>
                <Input type="password" placeholder="••••••••" />
              </div>
              <div className="space-y-2">
                <Label>Confirm New Password</Label>
                <Input type="password" placeholder="••••••••" />
              </div>
              <Separator />
              <div className="flex justify-end">
                <Button onClick={handleSave}>{saved ? '✓ Updated' : 'Update password'}</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="dealership">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Dealership Details</CardTitle>
              <CardDescription>Information about your dealership location</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2 col-span-2">
                  <Label>Dealership Name</Label>
                  <Input defaultValue={`${user?.company ?? ''} Dealership`} />
                </div>
                <div className="space-y-2 col-span-2">
                  <Label>Address</Label>
                  <Input placeholder="123 Main Street" />
                </div>
                <div className="space-y-2">
                  <Label>City</Label>
                  <Input placeholder="Mumbai" />
                </div>
                <div className="space-y-2">
                  <Label>State</Label>
                  <Input placeholder="Maharashtra" />
                </div>
                <div className="space-y-2">
                  <Label>GSTIN</Label>
                  <Input placeholder="27AABCU9603R1ZX" />
                </div>
                <div className="space-y-2">
                  <Label>Phone</Label>
                  <Input placeholder="+91 98765 43210" />
                </div>
              </div>
              <Separator />
              <div className="flex justify-end">
                <Button onClick={handleSave}>{saved ? '✓ Saved' : 'Save details'}</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
