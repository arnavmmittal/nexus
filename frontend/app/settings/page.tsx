'use client';

import { useState } from 'react';
import { Sidebar } from '@/components/layout/Sidebar';
import { cn } from '@/lib/utils';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { IntegrationsPanel } from '@/components/settings/IntegrationsPanel';
import { useDashboardStore } from '@/stores/dashboard';
import {
  Settings,
  Plug,
  Palette,
  User,
  Moon,
  Sun,
  Monitor,
  Bell,
  Shield,
  ChevronLeft,
} from 'lucide-react';

function GeneralPanel() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">General Settings</h2>
        <p className="text-sm text-muted-foreground">
          Manage your account and preferences.
        </p>
      </div>

      <div className="grid gap-4">
        {/* Profile Section */}
        <Card className="glass-panel border-white/10">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/5 border border-white/10">
                <User className="h-5 w-5 text-primary" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold">Profile</CardTitle>
                <CardDescription className="text-xs text-muted-foreground mt-0.5">
                  Your personal information
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground">Display Name</label>
                <Input
                  placeholder="Your name"
                  defaultValue="User"
                  className="bg-white/5 border-white/10"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground">Email</label>
                <Input
                  type="email"
                  placeholder="your@email.com"
                  className="bg-white/5 border-white/10"
                />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground">Timezone</label>
              <Input
                placeholder="America/Los_Angeles"
                defaultValue="America/Los_Angeles"
                className="bg-white/5 border-white/10"
              />
            </div>
            <Button size="sm" className="mt-2">Save Changes</Button>
          </CardContent>
        </Card>

        {/* Notifications Section */}
        <Card className="glass-panel border-white/10">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/5 border border-white/10">
                <Bell className="h-5 w-5 text-orange-400" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold">Notifications</CardTitle>
                <CardDescription className="text-xs text-muted-foreground mt-0.5">
                  Control how you receive notifications
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium">Daily Summary</p>
                <p className="text-xs text-muted-foreground">Receive a daily email digest</p>
              </div>
              <Button variant="outline" size="sm">
                Enable
              </Button>
            </div>
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium">Goal Reminders</p>
                <p className="text-xs text-muted-foreground">Get notified about upcoming deadlines</p>
              </div>
              <Button variant="outline" size="sm">
                Enable
              </Button>
            </div>
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium">AI Insights</p>
                <p className="text-xs text-muted-foreground">Weekly AI-generated insights</p>
              </div>
              <Button variant="outline" size="sm">
                Enable
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Privacy Section */}
        <Card className="glass-panel border-white/10">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/5 border border-white/10">
                <Shield className="h-5 w-5 text-purple-400" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold">Privacy & Security</CardTitle>
                <CardDescription className="text-xs text-muted-foreground mt-0.5">
                  Manage your data and security settings
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium">Export Data</p>
                <p className="text-xs text-muted-foreground">Download all your data</p>
              </div>
              <Button variant="outline" size="sm">
                Export
              </Button>
            </div>
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium text-red-400">Delete Account</p>
                <p className="text-xs text-muted-foreground">Permanently delete your account and data</p>
              </div>
              <Button variant="destructive" size="sm">
                Delete
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function AppearancePanel() {
  const [theme, setTheme] = useState<'dark' | 'light' | 'system'>('dark');
  const [accentColor, setAccentColor] = useState('emerald');
  const [fontSize, setFontSize] = useState(14);

  const accentColors = [
    { name: 'emerald', color: '#10b981' },
    { name: 'blue', color: '#3b82f6' },
    { name: 'purple', color: '#8b5cf6' },
    { name: 'orange', color: '#f59e0b' },
    { name: 'pink', color: '#ec4899' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Appearance</h2>
        <p className="text-sm text-muted-foreground">
          Customize the look and feel of Nexus.
        </p>
      </div>

      <div className="grid gap-4">
        {/* Theme Section */}
        <Card className="glass-panel border-white/10">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/5 border border-white/10">
                <Moon className="h-5 w-5 text-primary" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold">Theme</CardTitle>
                <CardDescription className="text-xs text-muted-foreground mt-0.5">
                  Select your preferred color scheme
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-3">
              <button
                onClick={() => setTheme('dark')}
                className={cn(
                  'flex flex-col items-center gap-2 p-4 rounded-lg border transition-all',
                  theme === 'dark'
                    ? 'border-primary bg-primary/10'
                    : 'border-white/10 hover:border-white/20 bg-white/5'
                )}
              >
                <Moon className="h-5 w-5" />
                <span className="text-xs font-medium">Dark</span>
              </button>
              <button
                onClick={() => setTheme('light')}
                className={cn(
                  'flex flex-col items-center gap-2 p-4 rounded-lg border transition-all',
                  theme === 'light'
                    ? 'border-primary bg-primary/10'
                    : 'border-white/10 hover:border-white/20 bg-white/5'
                )}
              >
                <Sun className="h-5 w-5" />
                <span className="text-xs font-medium">Light</span>
              </button>
              <button
                onClick={() => setTheme('system')}
                className={cn(
                  'flex flex-col items-center gap-2 p-4 rounded-lg border transition-all',
                  theme === 'system'
                    ? 'border-primary bg-primary/10'
                    : 'border-white/10 hover:border-white/20 bg-white/5'
                )}
              >
                <Monitor className="h-5 w-5" />
                <span className="text-xs font-medium">System</span>
              </button>
            </div>
            <p className="text-xs text-muted-foreground mt-3 text-center">
              Note: Nexus is optimized for dark mode. Light mode coming soon.
            </p>
          </CardContent>
        </Card>

        {/* Accent Color Section */}
        <Card className="glass-panel border-white/10">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/5 border border-white/10">
                <Palette className="h-5 w-5 text-purple-400" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold">Accent Color</CardTitle>
                <CardDescription className="text-xs text-muted-foreground mt-0.5">
                  Choose your primary accent color
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex gap-3 justify-center">
              {accentColors.map((color) => (
                <button
                  key={color.name}
                  onClick={() => setAccentColor(color.name)}
                  className={cn(
                    'h-10 w-10 rounded-full transition-all ring-2 ring-offset-2 ring-offset-background',
                    accentColor === color.name ? 'ring-white scale-110' : 'ring-transparent hover:scale-105'
                  )}
                  style={{ backgroundColor: color.color }}
                  title={color.name}
                />
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Font Size Section */}
        <Card className="glass-panel border-white/10">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/5 border border-white/10">
                <span className="text-sm font-bold text-blue-400">Aa</span>
              </div>
              <div>
                <CardTitle className="text-base font-semibold">Font Size</CardTitle>
                <CardDescription className="text-xs text-muted-foreground mt-0.5">
                  Adjust the base font size
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <span className="text-xs text-muted-foreground w-8">12</span>
              <Slider
                value={[fontSize]}
                onValueChange={(value) => setFontSize(Array.isArray(value) ? value[0] : value)}
                min={12}
                max={18}
                step={1}
                className="flex-1"
              />
              <span className="text-xs text-muted-foreground w-8">18</span>
            </div>
            <p className="text-center text-sm" style={{ fontSize: `${fontSize}px` }}>
              Preview text at {fontSize}px
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const { sidebarOpen } = useDashboardStore();
  const [activeTab, setActiveTab] = useState('integrations');

  return (
    <div className="min-h-screen gradient-mesh">
      <Sidebar />

      {/* Main Content */}
      <main
        className={cn(
          'min-h-screen transition-all duration-300',
          sidebarOpen ? 'ml-56' : 'ml-16'
        )}
      >
        {/* Header */}
        <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur-lg">
          <div className="flex h-16 items-center gap-4 px-6">
            <a
              href="/"
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
              <span className="text-sm">Back to Dashboard</span>
            </a>
            <div className="h-4 w-px bg-border" />
            <div className="flex items-center gap-2">
              <Settings className="h-5 w-5 text-primary" />
              <h1 className="text-lg font-semibold">Settings</h1>
            </div>
          </div>
        </header>

        {/* Content */}
        <div className="p-6 max-w-4xl mx-auto">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList variant="line" className="mb-8 border-b border-white/10 pb-px">
              <TabsTrigger value="general" className="gap-2 px-4">
                <User className="h-4 w-4" />
                General
              </TabsTrigger>
              <TabsTrigger value="integrations" className="gap-2 px-4">
                <Plug className="h-4 w-4" />
                Integrations
              </TabsTrigger>
              <TabsTrigger value="appearance" className="gap-2 px-4">
                <Palette className="h-4 w-4" />
                Appearance
              </TabsTrigger>
            </TabsList>

            <TabsContent value="general">
              <GeneralPanel />
            </TabsContent>

            <TabsContent value="integrations">
              <IntegrationsPanel />
            </TabsContent>

            <TabsContent value="appearance">
              <AppearancePanel />
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  );
}
