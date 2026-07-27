import { Eye, EyeOff, LogIn, Mail, ShieldCheck } from "lucide-react";
import { useState } from "react";
import AuthLayout from "../components/AuthLayout";
import Button from "../components/Button";
import ErrorAlert from "../components/ErrorAlert";
import FormField from "../components/FormField";
import { loginUser } from "../services/api";

export default function Login({ onLogin, onRegister, onForgot }) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [remember, setRemember] = useState(false);
    const [error, setError] = useState("");
    const [errors, setErrors] = useState({});
    const [loading, setLoading] = useState(false);
    const submit = async (event) => {
        event.preventDefault();
        const next = {};
        if (!email) next.email = "Email is required.";
        if (!password) next.password = "Password is required.";
        setErrors(next);
        if (Object.keys(next).length) return;
        setLoading(true);
        setError("");
        try {
            const data = await loginUser(email, password);
            if (!data.access_token) throw new Error("No access token received.");
            localStorage.setItem("access_token", data.access_token);
            if (remember) localStorage.setItem("remember_login", "true");
            else localStorage.removeItem("remember_login");
            onLogin?.();
        } catch (requestError) {
            setError(requestError.response?.data?.detail || (requestError.response ? "Incorrect email or password." : "Unable to connect to the server."));
        } finally {
            setLoading(false);
        }
    };
    return (
        <AuthLayout title="Welcome back" subtitle="Sign in to continue to your energy workspace.">
            <ErrorAlert title="Sign in failed" message={error} onDismiss={() => setError("")} />
            <form className="auth-form" onSubmit={submit} noValidate>
                <FormField name="login-email" label="Email address" error={errors.email} required><div className="input-with-icon"><Mail /><input id="login-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></div></FormField>
                <FormField name="login-password" label="Password" error={errors.password} required><div className="input-with-icon"><ShieldCheck /><input id="login-password" type={showPassword ? "text" : "password"} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" /><button type="button" className="password-toggle" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff /> : <Eye />}</button></div></FormField>
                <div className="auth-options"><label className="checkbox"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} /><span>Remember me</span></label><button type="button" className="link-button" onClick={onForgot}>Forgot password?</button></div>
                <Button type="submit" loading={loading} icon={LogIn} className="auth-submit">Sign in</Button>
            </form>
            <p className="auth-switch">New to Enerlytics? <button className="link-button" onClick={onRegister}>Create an account</button></p>
        </AuthLayout>
    );
}
