import { ArrowLeft, Mail, ShieldAlert } from "lucide-react";
import { useState } from "react";
import AuthLayout from "../components/AuthLayout";
import Button from "../components/Button";
import FormField from "../components/FormField";

export default function ForgotPassword({ onBack }) {
    const [email, setEmail] = useState("");
    return (
        <AuthLayout title="Reset your password" subtitle="Password recovery for your Enerlytics account.">
            <div className="recovery-notice"><span><ShieldAlert size={19} /></span><div><strong>Self-service recovery is coming soon</strong><p>The secure recovery endpoint is not available yet. Contact your organization administrator to reset your password.</p></div></div>
            <form className="auth-form" onSubmit={(event) => event.preventDefault()}>
                <FormField name="recovery-email" label="Account email"><div className="input-with-icon"><Mail /><input id="recovery-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" autoComplete="email" /></div></FormField>
                <Button type="button" disabled className="auth-submit">Send recovery email</Button>
            </form>
            <p className="auth-switch"><button className="link-button" onClick={onBack}><ArrowLeft size={14} />Back to sign in</button></p>
        </AuthLayout>
    );
}
