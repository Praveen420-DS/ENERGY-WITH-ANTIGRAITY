import { AlertCircle, X } from "lucide-react";

export default function ErrorAlert({ title = "Something went wrong", message, onDismiss }) {
    if (!message) return null;
    return (
        <div className="error-alert" role="alert">
            <AlertCircle size={20} />
            <div><strong>{title}</strong><p>{message}</p></div>
            {onDismiss && <button type="button" aria-label="Dismiss error" onClick={onDismiss}><X size={17} /></button>}
        </div>
    );
}
