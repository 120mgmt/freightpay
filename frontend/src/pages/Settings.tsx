import { useEffect, useRef, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2, Save, KeyRound, User, Camera, Trash2, Users, Plus, Copy, Link2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface TeamMember {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  is_self: boolean;
}

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

  // ---- Team members (company admins only) ----
  const isCompanyAdmin = (user?.role || "").toLowerCase() === "admin";
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [teamLoading, setTeamLoading] = useState(false);
  const [teamErr, setTeamErr] = useState("");
  const [showInvite, setShowInvite] = useState(false);
  const [inviting, setInviting] = useState(false);
  const [newMember, setNewMember] = useState({ email: "", first_name: "", last_name: "", role: "viewer" });
  const [inviteLink, setInviteLink] = useState("");
  const [busyMember, setBusyMember] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);

  const loadTeam = async () => {
    setTeamLoading(true);
    setTeamErr("");
    try {
      const res = await apiFetch("/users/team");
      const data = await res.json().catch(() => []);
      if (res.ok) setTeam(Array.isArray(data) ? data : []);
      else setTeamErr(data.error || "Could not load team.");
    } catch { setTeamErr("Network error."); }
    setTeamLoading(false);
  };

  useEffect(() => { if (isCompanyAdmin) loadTeam(); /* eslint-disable-next-line */ }, [isCompanyAdmin]);

  const copyLink = async (link: string) => {
    setInviteLink(link);
    try { await navigator.clipboard.writeText(link); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* shown for manual copy */ }
  };

  const addMember = async () => {
    setInviting(true);
    setTeamErr("");
    setInviteLink("");
    try {
      const res = await apiFetch("/users/team", { method: "POST", body: JSON.stringify(newMember) });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setNewMember({ email: "", first_name: "", last_name: "", role: "viewer" });
        setShowInvite(false);
        await loadTeam();
        if (data.invite_url) copyLink(data.invite_url);
      } else {
        const map: Record<string, string> = {
          EMAIL_ALREADY_EXISTS: "That email is already in use.",
          MISSING_REQUIRED_FIELDS: "Fill in name and email.",
          INVALID_EMAIL: "Enter a valid email.",
        };
        setTeamErr(map[data.error] || data.error || "Could not add member.");
      }
    } catch { setTeamErr("Network error."); }
    setInviting(false);
  };

  const patchMember = async (m: TeamMember, patch: Record<string, unknown>) => {
    setBusyMember(m.id);
    const res = await apiFetch(`/users/team/${m.id}`, { method: "PATCH", body: JSON.stringify(patch) });
    setBusyMember(null);
    if (res.ok) loadTeam();
    else { const d = await res.json().catch(() => ({})); setTeamErr(d.error || "Update failed."); }
  };

  const removeMember = async (m: TeamMember) => {
    if (!confirm(`Remove ${m.email}? Their login is deleted and the email becomes free to reuse.`)) return;
    setBusyMember(m.id);
    const res = await apiFetch(`/users/team/${m.id}`, { method: "DELETE" });
    setBusyMember(null);
    if (res.ok) loadTeam();
    else { const d = await res.json().catch(() => ({})); setTeamErr(d.error || "Remove failed."); }
  };

  const regenLink = async (m: TeamMember) => {
    setBusyMember(m.id);
    const res = await apiFetch(`/users/team/${m.id}/invite-link`, { method: "POST" });
    setBusyMember(null);
    const d = await res.json().catch(() => ({}));
    if (res.ok && d.invite_url) copyLink(d.invite_url);
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

        {/* Team section — company admins only */}
        {isCompanyAdmin && (
          <div className="rounded-2xl border border-border bg-card p-6 mt-6 shadow-sm">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-lg flex items-center justify-center bg-primary/10 border border-primary/25">
                  <Users size={18} className="text-primary" />
                </div>
                <div>
                  <h2 className="font-bold">Team Members</h2>
                  <p className="text-xs text-muted-foreground">Give your staff their own logins</p>
                </div>
              </div>
              <Button size="sm" onClick={() => { setShowInvite((v) => !v); setInviteLink(""); setTeamErr(""); }}
                className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                {showInvite ? "Cancel" : <><Plus size={14} className="mr-1" /> Add Member</>}
              </Button>
            </div>

            {teamErr && (
              <div className="p-3 rounded-lg text-sm mb-4 border border-destructive/30 bg-destructive/5 text-destructive">{teamErr}</div>
            )}

            {inviteLink && (
              <div className="p-3 rounded-lg text-sm mb-4 border border-primary/30 bg-primary/5">
                <div className="flex items-center gap-2 mb-1 font-semibold text-primary">
                  <Link2 size={14} /> Invite link {copied && <span className="text-xs font-normal">· copied!</span>}
                </div>
                <p className="text-xs text-muted-foreground mb-2">Share this with your teammate — it lets them set a password and sign in. Expires in 1 hour (regenerate anytime).</p>
                <div className="flex items-center gap-2">
                  <input readOnly value={inviteLink} className="flex-1 px-2 py-1.5 rounded border border-border bg-card text-xs font-mono" />
                  <Button size="sm" variant="outline" onClick={() => copyLink(inviteLink)}><Copy size={13} /></Button>
                </div>
              </div>
            )}

            {showInvite && (
              <div className="rounded-xl border border-border p-4 mb-4 bg-surface-muted/40">
                <div className="grid sm:grid-cols-2 gap-3 mb-3">
                  <div>
                    <Label className="text-xs text-muted-foreground">First name</Label>
                    <Input className="mt-1 bg-card" value={newMember.first_name} onChange={(e) => setNewMember((m) => ({ ...m, first_name: e.target.value }))} />
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Last name</Label>
                    <Input className="mt-1 bg-card" value={newMember.last_name} onChange={(e) => setNewMember((m) => ({ ...m, last_name: e.target.value }))} />
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Email</Label>
                    <Input className="mt-1 bg-card" type="email" value={newMember.email} onChange={(e) => setNewMember((m) => ({ ...m, email: e.target.value }))} />
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Role</Label>
                    <select value={newMember.role} onChange={(e) => setNewMember((m) => ({ ...m, role: e.target.value }))}
                      className="mt-1 w-full px-3 py-2 rounded-md border border-border bg-card text-sm outline-none focus:border-primary capitalize">
                      <option value="viewer">Viewer — read only</option>
                      <option value="manager">Manager — day-to-day work</option>
                      <option value="admin">Admin — full access &amp; team management</option>
                    </select>
                  </div>
                </div>
                <Button size="sm" onClick={addMember} disabled={inviting || !newMember.email.trim() || !newMember.first_name.trim() || !newMember.last_name.trim()}
                  className="bg-primary text-primary-foreground hover:bg-[hsl(var(--primary-dim))]">
                  {inviting ? <Loader2 size={14} className="animate-spin mr-1" /> : <Plus size={14} className="mr-1" />}
                  Create member &amp; get invite link
                </Button>
              </div>
            )}

            {teamLoading ? (
              <div className="flex items-center gap-2 text-muted-foreground py-6 justify-center text-sm">
                <Loader2 className="animate-spin" size={16} /> Loading team…
              </div>
            ) : (
              <div className="space-y-2">
                {team.map((m) => (
                  <div key={m.id} className="flex items-center justify-between rounded-lg border border-border px-3 py-2.5">
                    <div className="min-w-0">
                      <div className="font-medium text-sm truncate">
                        {m.first_name} {m.last_name}
                        {m.is_self && <span className="ml-2 text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-muted text-muted-foreground">You</span>}
                        {!m.is_active && <span className="ml-2 text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-destructive/10 text-destructive">Disabled</span>}
                      </div>
                      <div className="text-xs text-muted-foreground truncate">{m.email}</div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <select value={m.role} disabled={busyMember === m.id || m.is_self}
                        onChange={(e) => patchMember(m, { role: e.target.value })}
                        className="rounded-md border border-border bg-card px-2 py-1 text-xs outline-none focus:border-primary">
                        <option value="admin">admin</option>
                        <option value="manager">manager</option>
                        <option value="viewer">viewer</option>
                      </select>
                      {!m.is_self && (
                        <>
                          <Button size="sm" variant="outline" title="Copy a fresh invite / reset link" disabled={busyMember === m.id} onClick={() => regenLink(m)}>
                            <Link2 size={13} />
                          </Button>
                          <Button size="sm" variant="outline" disabled={busyMember === m.id}
                            className={m.is_active ? "text-destructive border-destructive/40" : "text-primary border-primary/40"}
                            onClick={() => patchMember(m, { is_active: !m.is_active })}>
                            {busyMember === m.id ? <Loader2 size={13} className="animate-spin" /> : m.is_active ? "Disable" : "Enable"}
                          </Button>
                          <Button size="sm" variant="outline" className="text-destructive border-destructive/40" disabled={busyMember === m.id} onClick={() => removeMember(m)}>
                            <Trash2 size={13} />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default Settings;
