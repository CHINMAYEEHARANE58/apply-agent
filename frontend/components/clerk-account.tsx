"use client";

import { SignOutButton, UserButton, useUser } from "@clerk/nextjs";
import { LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";

export function AccountSync() {
  const { isLoaded, isSignedIn } = useUser();
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    let active = true;
    apiFetch("users/me").then(() => { if (active) setFailed(false); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [isLoaded, isSignedIn, attempt]);
  return failed ? <div role="alert" className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">Your account could not connect to the database. Check backend configuration and your verified email before saving data. <button className="underline" onClick={() => setAttempt(value => value + 1)}>Retry</button></div> : null;
}

export function AccountGreeting() {
  const { user } = useUser();
  return <>Welcome{user?.firstName ? `, ${user.firstName}` : ""} <span className="text-slate-300">·</span> Let&apos;s find your next opportunity.</>;
}

export function AccountAvatar() {
  return <UserButton />;
}

export function AccountSignOut() {
  return <SignOutButton redirectUrl="/login"><button className="mt-4 flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500 hover:bg-slate-800 hover:text-slate-200"><LogOut size={18} />Sign out</button></SignOutButton>;
}
