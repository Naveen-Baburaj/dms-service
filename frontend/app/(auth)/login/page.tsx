'use client';
import { useState } from 'react';
import { Eye, EyeOff, Car } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import type { LoginCredentials } from '@/types';

export default function LoginPage() {
  const { login, isLoading, loginError } = useAuth();
  const [credentials, setCredentials] = useState<LoginCredentials>({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Partial<LoginCredentials>>({});

  function validate(): boolean {
    const errs: Partial<LoginCredentials> = {};
    if (!credentials.email) errs.email = 'Email is required';
    else if (!/^\S+@\S+\.\S+$/.test(credentials.email)) errs.email = 'Invalid email';
    if (!credentials.password) errs.password = 'Password is required';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (validate()) login(credentials);
  }

  const errorMessage =
    loginError instanceof Error
      ? loginError.message
      : (loginError as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        'Invalid credentials. Please try again.';

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 p-4">
      <div className="relative w-full max-w-md space-y-6">
        <div className="text-center">
          <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-600 shadow-lg shadow-blue-600/30 mb-4">
            <Car className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">DMS Portal</h1>
          <p className="mt-1 text-sm text-slate-400">Dealer Management System</p>
        </div>

        <Card className="border-slate-700/50 bg-slate-800/60 backdrop-blur-sm shadow-2xl">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-xl text-white">Sign in</CardTitle>
            <CardDescription className="text-slate-400">
              Enter your credentials to access your dashboard
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-slate-300">Email address</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  autoComplete="email"
                  value={credentials.email}
                  onChange={(e) => setCredentials((p) => ({ ...p, email: e.target.value }))}
                  className={cn(
                    'bg-slate-900/50 border-slate-600 text-white placeholder:text-slate-500 focus-visible:ring-blue-500',
                    errors.email && 'border-red-500',
                  )}
                />
                {errors.email && <p className="text-xs text-red-400">{errors.email}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-slate-300">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    autoComplete="current-password"
                    value={credentials.password}
                    onChange={(e) => setCredentials((p) => ({ ...p, password: e.target.value }))}
                    className={cn(
                      'bg-slate-900/50 border-slate-600 text-white placeholder:text-slate-500 focus-visible:ring-blue-500 pr-10',
                      errors.password && 'border-red-500',
                    )}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password && <p className="text-xs text-red-400">{errors.password}</p>}
              </div>

              {loginError && (
                <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3">
                  <p className="text-sm text-red-400">{errorMessage}</p>
                </div>
              )}

              <Button
                type="submit"
                disabled={isLoading}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold h-11"
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                    Signing in...
                  </span>
                ) : (
                  'Sign in'
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="flex items-center justify-center gap-6 text-xs text-slate-500">
          <span className="font-semibold text-red-500">HONDA</span>
          <span className="h-3 w-px bg-slate-600" />
          <span className="font-semibold text-blue-400">NEXA</span>
          <span className="h-3 w-px bg-slate-600" />
          <span className="font-semibold text-slate-300">JAGUAR</span>
        </div>
      </div>
    </div>
  );
}
