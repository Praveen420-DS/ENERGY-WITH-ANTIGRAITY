import { Building2, KeyRound, LockKeyhole, Mail, Pencil, ShieldCheck, UserRound } from "lucide-react";
import Button from "../components/Button";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";

export default function ProfilePage({ user }) {
    if (!user) return <><PageHeader eyebrow="Account" title="My profile" description="Manage your account details and security." /><section className="panel"><EmptyState icon={UserRound} title="Profile unavailable" description="We could not match this session to a user profile." /></section></>;
    const name = user.full_name || user.username;
    return (
        <>
            <PageHeader eyebrow="Account" title="My profile" description="Review your identity, access level, and account status." />
            <section className="profile-hero panel">
                <div className="avatar avatar-large">{name.charAt(0).toUpperCase()}</div>
                <div className="profile-title"><p className="eyebrow">Professional profile</p><h2>{name}</h2><p><Mail size={15} />{user.email}</p><p><Building2 size={15} />Enerlytics Organization</p><div className="badge-row"><span className="badge purple"><ShieldCheck size={14} />{user.role}</span><span className={`badge ${user.is_active ? "green" : "red"}`}><span className="status-dot" />{user.is_active ? "Active" : "Inactive"}</span></div></div>
                <div className="profile-actions"><Button variant="secondary" icon={KeyRound} disabled title="Password update endpoint unavailable">Change password</Button><Button icon={Pencil} disabled title="Profile update endpoint unavailable">Edit profile</Button></div>
            </section>
            <div className="profile-content-grid"><section className="panel account-panel"><div className="panel-heading"><div><h2>Account information</h2><p>Your authenticated organization profile.</p></div></div><dl className="account-grid"><div><dt>Full name</dt><dd>{user.full_name || "Not provided"}</dd></div><div><dt>Username</dt><dd>{user.username}</dd></div><div><dt>Email address</dt><dd>{user.email}</dd></div><div><dt>Organization</dt><dd>Enerlytics Organization</dd></div><div><dt>Access role</dt><dd className="capitalize">{user.role}</dd></div><div><dt>Account status</dt><dd>{user.is_active ? "Active" : "Inactive"}</dd></div></dl></section><section className="panel security-panel"><div className="security-icon"><LockKeyhole /></div><h2>Password & security</h2><p>Password management requires a secure account endpoint. This control will become available when organization-managed recovery is enabled.</p><Button variant="secondary" icon={KeyRound} disabled title="Password update endpoint unavailable">Update password</Button><small>Last verified through your current authenticated session.</small></section></div>
        </>
    );
}
