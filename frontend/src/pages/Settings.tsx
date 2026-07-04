import { useRef, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2, Save, KeyRound, User, Camera, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const Settings = () => {
  const { user, updateUser } = useAuth();

  const [profile, setProfile] = useState({
    first_name: user?.first_name || "",
    last_name: user?.last_name || "",
    email: user?.email || "",
  });
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState("");
  const [profileErr, setProfileErr] = useState("");

  const fileRef = useRef<HTMLInputElement>(null);
  const [avatarSaving, setAvatarSaving] = useState(false);
  const [avatarErr, setAvatarErr] = useState("");

  const saveAvatar = async (dataUrl: string) => {
    setAvatarSaving(true);
    setAvatarErr("");
    try {
      const res = await apiFetch("/users/me", {
        method: "PATCH",
        body: JSON.stringify({ avatar_url: dataUrl }),
      });
      if (res.ok) {
        updateUser({ avatar_url: dataUrl || null });
      } else {
        const d = await res.json().catch(() => ({}));
        setAvatarErr(d.error === "AVATAR_TOO_LARGE" ? "Image too large — try a smaller photo." : d.error || "Could not save photo.");
      }
    } catch {
      setAvatarErr("Network error — check your connection.");
    }
    setAvatarSaving(false);
  };

  const handleAvatarFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) { setAvatarErr("Please choose an image file."); return; }
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const SIZE = 256;
      const canvas = document.createElement("canvas");
      canvas.width = SIZE;
      canvas.height = SIZE;
      const ctx = canvas.getContext("2d");
      if (!ctx) { setAvatarErr("Could not process the image."); return; }
      // cover-crop to a centered square
      const side = Math.min(img.width, img.height);
      const sx = (img.width - side) / 2;
      const sy = (img.height - side) / 2;
      ctx.drawImage(img, sx, sy, side, side, 0, 0, SIZE, SIZE);
      saveAvatar(canvas.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = () => { URL.revokeObjectURL(url); setAvatarErr("Could not read the image."); };
    img.src = url;
  };

  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg, setPwMsg] = useState("");
  const [pwErr, setPwErr] = useState("");

  const handleProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileSaving(true);
    setProfileMsg(""); setProfileErr("");
    try {
      const res = await apiFetch("/users/me", { method: "PATCH", body: JSON.stringify(profile) });
      if (res.ok) { setProfileMsg("Profile updated."); }
      else { const d = await res.json(); setProfileErr(d.error || "Update failed."); }
    } catch { setProfileErr("Network error."); }
    setProfileSaving(false);
  };

  const handlePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pw.next !== pw.confirm) { setPwErr("Passwords do not match."); return; }
    if (pw.next.length < 8) { setPwErr("Password must be at least 8 characters."); return; }
    setPwSaving(true);
    setPwMsg(""); setPwErr("");
    try {
      const res = await apiFetch("/users/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: pw.current, new_password: pw.next }),
      });
      if (res.ok) {
        setPwMsg("Password changed.");
        setPw({ current: "", next: "", confirm: "" });
      } else {
        const d = await res.json();
        setPwErr(d.error || "Password change failed.");
      }
    } catch { setPwErr("Network error."); }
    setPwSaving(false);
  };

  return (
    <AppLayout active="Settings">
      <div className="max-w-2xl">
        <div className="mb-8">
          <h1 className="text-2xl font-extrabold tracking-tight">Settings</h1>
          <p className="text-muted-foreground mt-1">Manage your account and preferences</p>
        </div>

        {/* Profile section */}
        <div className="rounded-2xl border border-border bg-card p-6 mb-6 shadow-sm">
          <div className="flex items-center gap-3 mb-5">
            <div className="h-9 w-9 rounded-lg flex items-center justify-center bg-primary/10 border border-primary/25">
              <User size={18} className="text-primary" />
            </div>
            <div>
              <h2 className="font-bold">Profile</h2>
              <p className="text-xs text-muted-foreground">Update your name and email</p>
            </div>
          </div>

          {profileMsg && (
            <div className="p-3 rounded-lg text-sm mb-4 border border-primary/30 bg-primary/5 text-primary">
              {profileMsg}
            </div>
          )}
          {profileErr && (
            <div className="p-3 rounded-lg text-sm mb-4 border border-destructive/30 bg-destructive/5 text-destructive">
              {profileErr}
            </div>
          )}

          <div className="flex items-center gap-4 mb-6">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="Profile" className="h-16 w-16 rounded-full object-cover border border-border" />
            ) : (
              <div className="h-16 w-16 rounded-full flex items-center justify-center text-lg font-bold bg-primary text-primary-foreground">
                {user?.first_name?.[0]}{user?.last_name?.[0]}
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <div className="flex gap-2">
                <Button type="button" size="sm" variant="outline" disabled={avatarSaving} onClick={() => fileRef.current?.click()}>
                  {avatarSaving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Camera size={14} className="mr-1" />}
                  {user?.avatar_url ? "Change Photo" : "Upload Photo"}
                </Button>
                {user?.avatar_url && (
                  <Button type="button" size="sm" variant="outline" disabled={avatarSaving} onClick={() => saveAvatar("")}
                    className="text-destructive border-destructive/30 hover:bg-destructive/5">
                    <Trash2 size={14} className="mr-1" /> Remove
                  </Button>
                )}
              </div>
              <span className="text-xs text-muted-foreground">JPG or PNG. It will be cropped to a square.</span>
              {avatarErr && <span className="text-xs text-destructive">{avatarErr}</span>}
            </div>
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleAvatarFile} />
          </div>

          <form onSubmit={handleProfile} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-muted-foreground">First Name</Label>
                <Input className="mt-1 bg-surface" value={profile.first_name} onChange={e => setProfile(p => ({ ...p, first_name: e.target.value }))} required />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Last Name</Label>
                <Input className="mt-1 bg-surface" value={profile.last_name} onChange={e => setProfile(p => ({ ...p, last_name: e.target.value }))} required />
              </div>
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Email</Label>
              <Input className="mt-1 bg-surface" type="email" value={profile.email} onChange={e => setProfile(p => ({ ...p, email: e.target.value }))} required />
            </div>
            <div className="flex justify-end">
              <Button type="submit" disabled={profileSaving} size="sm" className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                {profileSaving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}
                Save Profile
              </Button>
            </div>
          </form>
        </div>

        {/* Password section */}
        <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-5">
            <div className="h-9 w-9 rounded-lg flex items-center justify-center bg-blue-50 border border-blue-200">
              <KeyRound size={18} className="text-blue-600" />
            </div>
            <div>
              <h2 className="font-bold">Change Password</h2>
              <p className="text-xs text-muted-foreground">Choose a strong password</p>
            </div>
          </div>

          {pwMsg && (
            <div className="p-3 rounded-lg text-sm mb-4 border border-primary/30 bg-primary/5 text-primary">
              {pwMsg}
            </div>
          )}
          {pwErr && (
            <div className="p-3 rounded-lg text-sm mb-4 border border-destructive/30 bg-destructive/5 text-destructive">
              {pwErr}
            </div>
          )}

          <form onSubmit={handlePassword} className="space-y-4">
            <div>
              <Label className="text-xs text-muted-foreground">Current Password</Label>
              <Input className="mt-1 bg-surface" type="password" value={pw.current} onChange={e => setPw(p => ({ ...p, current: e.target.value }))} required />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">New Password</Label>
              <Input className="mt-1 bg-surface" type="password" value={pw.next} onChange={e => setPw(p => ({ ...p, next: e.target.value }))} required minLength={8} />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Confirm New Password</Label>
              <Input className="mt-1 bg-surface" type="password" value={pw.confirm} onChange={e => setPw(p => ({ ...p, confirm: e.target.value }))} required />
            </div>
            <div className="flex justify-end">
              <Button type="submit" disabled={pwSaving} size="sm" className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                {pwSaving ? <Loader2 size={14} className="animate-spin mr-1" /> : <KeyRound size={14} className="mr-1" />}
                Change Password
              </Button>
            </div>
          </form>
        </div>
      </div>
    </AppLayout>
  );
};

export default Settings;
